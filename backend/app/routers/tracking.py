"""
API de Tracking — recebe lotes do gm-tracker.js.

• Assíncrona e sem I/O de banco na requisição: valida → enfileira → 202 Accepted.
• Aceita application/json (fetch keepalive) e text/plain (fallback do sendBeacon).
• user_id NUNCA vem do corpo: é extraído do cookie de sessão assinado (o script
  legado lia <meta name="user-id">, o que permitia forjar eventos em nome de outro usuário).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.models import EventType
from app.schemas import ClientEventType, TrackAccepted, TrackBatchIn
from app.security.crypto import pseudonymize_ip
from app.security.web import (
    SessionClaims,
    client_ip,
    device_from_ua,
    enforce_csrf,
    limiter,
    read_session_claims,
    user_agent,
)
from app.services.tracking_queue import TrackingEnvelope, tracking_queue

router = APIRouter(prefix="/api/v1", tags=["Tracking"])

MAX_BODY_BYTES = 64 * 1024          # mesmo limite do fetch keepalive/sendBeacon
MAX_CLOCK_SKEW = timedelta(hours=24)

_PAGE_EVENTS = {ClientEventType.PAGE_VIEW, ClientEventType.ENGAGEMENT}
_EVENT_MAP = {
    ClientEventType.CLICK: EventType.CLICK,
    ClientEventType.SEARCH: EventType.SEARCH,
    ClientEventType.FAVORITE_ADD: EventType.FAVORITE_ADD,
    ClientEventType.FAVORITE_REMOVE: EventType.FAVORITE_REMOVE,
    ClientEventType.ADD_TO_CART: EventType.ADD_TO_CART,
    ClientEventType.BEGIN_CHECKOUT: EventType.BEGIN_CHECKOUT,
}


@router.post("/track", status_code=status.HTTP_202_ACCEPTED, response_model=TrackAccepted)
@limiter.limit("240/minute")
async def ingest_tracking(request: Request) -> TrackAccepted:
    # 1) Limite de tamanho antes de ler o corpo (Nginx também deve limitar)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Lote de tracking muito grande.")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Lote de tracking muito grande.")

    # 2) Validação estrita (Pydantic) — não ecoa o payload no erro
    try:
        batch = TrackBatchIn.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(422, "Lote de tracking inválido.") from None

    # 3) CSRF: Origin + token (header no fetch, corpo no sendBeacon)
    enforce_csrf(request, body_token=batch.csrf_token)

    # 4) Normaliza e enfileira — resposta imediata, gravação em background
    envelope = build_envelope(batch, read_session_claims(request), request)
    accepted = tracking_queue.offer(envelope)
    return TrackAccepted(accepted=accepted, events=len(batch.events))


def build_envelope(batch: TrackBatchIn, claims: SessionClaims | None, request: Request) -> TrackingEnvelope:
    now = datetime.now(timezone.utc)
    user_id = claims.user_id if claims else None
    ua = user_agent(request)
    stamps = [_clamp(ev.ts, now) for ev in batch.events]

    envelope = TrackingEnvelope(
        session={
            "id": batch.session_id,
            "visitor_id": batch.visitor_id,
            "user_id": user_id,
            "started_at": min(stamps),
            "last_seen_at": max(stamps),
            "landing_path": batch.events[0].path,
            "referrer_host": batch.referrer_host,
            "device": device_from_ua(ua),
            "user_agent": ua,
            "ip_hash": pseudonymize_ip(client_ip(request)),
        }
    )

    for ev, ts in zip(batch.events, stamps, strict=True):
        if ev.type in _PAGE_EVENTS:
            envelope.page_views.append(
                {
                    "id": ev.page_view_id,
                    "session_id": batch.session_id,
                    "user_id": user_id,
                    "path": ev.path,
                    "referrer_path": ev.referrer_path,
                    "product_id": ev.product_id,
                    "started_at": ts,
                    "active_seconds": ev.active_seconds or 0,
                    "max_scroll_pct": ev.scroll_pct or 0,
                }
            )
        else:
            envelope.events.append(
                {
                    "occurred_at": ts,
                    "session_id": batch.session_id,
                    "user_id": user_id,
                    "event_type": _EVENT_MAP[ev.type],
                    "path": ev.path,
                    "product_id": ev.product_id,
                    "value": None,
                    "props": ev.props,
                }
            )
    return envelope


def emit_purchase_event(*, user_id: int, order_public_id: uuid.UUID, total: Decimal,
                        product_ids: list[int], session_id: uuid.UUID | None) -> None:
    """
    Evento 'purchase' emitido pelo SERVIDOR após o pedido ser gravado — fonte da verdade
    do funil. (Em produção, mova para o webhook de pagamento confirmado.)
    """
    tracking_queue.offer(
        TrackingEnvelope(
            events=[
                {
                    "occurred_at": datetime.now(timezone.utc),
                    "session_id": session_id,
                    "user_id": user_id,
                    "event_type": EventType.PURCHASE,
                    "path": "/checkout",
                    "product_id": product_ids[0] if len(product_ids) == 1 else None,
                    "value": total,
                    "props": {"order": str(order_public_id), "items": len(product_ids)},
                }
            ]
        )
    )


def _clamp(ts: datetime, now: datetime) -> datetime:
    """Relógio do cliente não é confiável: limita a [agora - 24h, agora]."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return min(max(ts, now - MAX_CLOCK_SKEW), now)

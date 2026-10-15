"""
Ingestão assíncrona de telemetria.

Fluxo:
    POST /api/v1/track  ──valida──►  asyncio.Queue (em memória, limitada)  ──► 202 em < 1 ms
                                              │
                         worker em background ▼  (lote: 500 linhas OU 2 s)
                        analytics_engine ──► UPSERT sessions / page_views + INSERT events

Por que não trava o e-commerce:
  • A rota de tracking não faz I/O de banco: só valida e enfileira.
  • O worker usa um pool de conexões próprio e pequeno (analytics_engine).
  • Fila cheia = descarte controlado (load shedding) em vez de acumular latência.

Escala horizontal: com vários workers do Uvicorn cada processo tem sua fila. Para
volumes de milhões de eventos/dia, troque `TrackingQueue` por um produtor Redis
Streams/Kafka com a MESMA interface `offer()` — as rotas não mudam.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.database import analytics_engine
from app.models import AnalyticsEvent, AnalyticsSession, PageView

log = logging.getLogger("gamemania.tracking")


@dataclass(slots=True)
class TrackingEnvelope:
    """Tudo o que uma requisição de tracking produziu, já normalizado em linhas."""
    session: dict[str, Any] | None = None
    page_views: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return (1 if self.session else 0) + len(self.page_views) + len(self.events)


class TrackingQueue:
    def __init__(self, engine: AsyncEngine, *, maxsize: int, batch_size: int, flush_seconds: float) -> None:
        self._engine = engine
        self._maxsize = maxsize
        self._queue: asyncio.Queue[TrackingEnvelope] | None = None   # criada no loop do servidor (start)
        self._batch_size = batch_size
        self._flush_seconds = flush_seconds
        self._pending: list[TrackingEnvelope] = []
        self._task: asyncio.Task | None = None
        self.stats = {"accepted": 0, "dropped": 0, "rows_written": 0, "failed_batches": 0}

    # ------------------------------------------------------------------ API
    def offer(self, envelope: TrackingEnvelope) -> bool:
        """Não bloqueante. Retorna False se a fila estiver cheia (evento descartado)."""
        if self._queue is None:
            self.stats["dropped"] += 1
            return False
        try:
            self._queue.put_nowait(envelope)
        except asyncio.QueueFull:
            self.stats["dropped"] += 1
            return False
        self.stats["accepted"] += 1
        return True

    async def start(self) -> None:
        if self._task is None:
            self._queue = asyncio.Queue(maxsize=self._maxsize)
            self._task = asyncio.create_task(self._run(), name="gm-tracking-writer")

    async def stop(self) -> None:
        """Encerramento gracioso: grava o que estiver pendente antes de sair."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            self._queue = None

    # --------------------------------------------------------------- worker
    async def _run(self) -> None:
        assert self._queue is not None
        loop = asyncio.get_running_loop()
        try:
            while True:
                self._pending.append(await self._queue.get())
                rows = self._pending[0].row_count
                deadline = loop.time() + self._flush_seconds
                while rows < self._batch_size and (remaining := deadline - loop.time()) > 0:
                    try:
                        env = await asyncio.wait_for(self._queue.get(), remaining)
                    except asyncio.TimeoutError:
                        break
                    self._pending.append(env)
                    rows += env.row_count
                await self._flush(self._pending)
                self._pending = []
        except asyncio.CancelledError:
            while not self._queue.empty():
                self._pending.append(self._queue.get_nowait())
            if self._pending:
                await self._flush(self._pending)
                self._pending = []
            raise

    async def _flush(self, batch: list[TrackingEnvelope]) -> None:
        sessions, page_views, events = _merge(batch)
        try:
            async with self._engine.begin() as conn:  # uma transação por lote
                if sessions:
                    await conn.execute(_UPSERT_SESSIONS, sessions)
                if page_views:
                    await conn.execute(_UPSERT_PAGE_VIEWS, page_views)
                if events:
                    await conn.execute(insert(AnalyticsEvent), events)
            self.stats["rows_written"] += len(sessions) + len(page_views) + len(events)
        except Exception:  # noqa: BLE001 — telemetria nunca derruba o worker
            self.stats["failed_batches"] += 1
            log.exception("Falha ao gravar lote de tracking (%d linhas descartadas)", len(sessions) + len(page_views) + len(events))


# =============================================================================
# Consolidação do lote em memória
# (o Postgres não aceita a mesma chave duas vezes num único ON CONFLICT DO UPDATE)
# =============================================================================
def _merge(batch: list[TrackingEnvelope]) -> tuple[list[dict], list[dict], list[dict]]:
    sessions: dict[Any, dict] = {}
    views: dict[Any, dict] = {}
    events: list[dict] = []

    for env in batch:
        if (s := env.session) is not None:
            cur = sessions.get(s["id"])
            if cur is None:
                sessions[s["id"]] = dict(s)
            else:
                cur["started_at"] = min(cur["started_at"], s["started_at"])
                cur["last_seen_at"] = max(cur["last_seen_at"], s["last_seen_at"])
                cur["user_id"] = s["user_id"] or cur["user_id"]

        for pv in env.page_views:
            cur = views.get(pv["id"])
            if cur is None:
                views[pv["id"]] = dict(pv)
            else:
                cur["active_seconds"] = max(cur["active_seconds"], pv["active_seconds"])
                cur["max_scroll_pct"] = max(cur["max_scroll_pct"], pv["max_scroll_pct"])
                cur["started_at"] = min(cur["started_at"], pv["started_at"])
                cur["referrer_path"] = cur["referrer_path"] or pv["referrer_path"]
                cur["product_id"] = cur["product_id"] or pv["product_id"]

        events.extend(env.events)

    return list(sessions.values()), list(views.values()), events


# =============================================================================
# Statements (compilados uma única vez)
# =============================================================================
def _build_session_upsert():
    stmt = pg_insert(AnalyticsSession)
    return stmt.on_conflict_do_update(
        index_elements=[AnalyticsSession.id],
        set_={
            "last_seen_at": func.greatest(AnalyticsSession.last_seen_at, stmt.excluded.last_seen_at),
            "user_id": func.coalesce(stmt.excluded.user_id, AnalyticsSession.user_id),
            "visitor_id": func.coalesce(AnalyticsSession.visitor_id, stmt.excluded.visitor_id),
        },
    )


def _build_page_view_upsert():
    stmt = pg_insert(PageView)
    return stmt.on_conflict_do_update(
        index_elements=[PageView.id],
        set_={
            # GREATEST torna o upsert idempotente e imune a heartbeats fora de ordem
            "active_seconds": func.greatest(PageView.active_seconds, stmt.excluded.active_seconds),
            "max_scroll_pct": func.greatest(PageView.max_scroll_pct, stmt.excluded.max_scroll_pct),
            "user_id": func.coalesce(stmt.excluded.user_id, PageView.user_id),
        },
        # um cliente não consegue alterar page view de outra sessão
        where=(PageView.session_id == stmt.excluded.session_id),
    )


_UPSERT_SESSIONS = _build_session_upsert()
_UPSERT_PAGE_VIEWS = _build_page_view_upsert()

_settings = get_settings()
tracking_queue = TrackingQueue(
    analytics_engine,
    maxsize=_settings.tracking_queue_max,
    batch_size=_settings.tracking_batch_size,
    flush_seconds=_settings.tracking_flush_seconds,
)

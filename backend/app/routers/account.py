"""
Painel do usuário (/dashboard.html) — mostra como os dados de tracking viram produto:
estatísticas, pedidos, favoritos, perfil de interesse e histórico de acessos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AnalyticsSession, Favorite, Order, OrderItem, OrderStatus, PageView, Product, User, UserAccessLog
from app.routers.auth import _user_out
from app.schemas import (
    AccessOut,
    DashboardOut,
    DashboardStatsOut,
    InterestOut,
    OrderSummaryOut,
    ProductCardOut,
)
from app.security.web import get_current_user

router = APIRouter(prefix="/api/v1/me", tags=["Conta"])

_PAID = (OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED)

# Consulta à materialized view (sql/analytics.sql) — parâmetro vinculado, nunca f-string
_INTERESTS_SQL = text(
    "SELECT category, score FROM mv_user_interest WHERE user_id = :uid ORDER BY score DESC LIMIT 5"
)


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> DashboardOut:
    uid = user.id
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # 1) Estatísticas em UMA ida ao banco (subconsultas escalares)
    stats = (
        await db.execute(
            select(
                select(func.count(Order.id)).where(Order.user_id == uid, Order.status != OrderStatus.CANCELLED).scalar_subquery(),
                select(func.coalesce(func.sum(Order.total), 0)).where(Order.user_id == uid, Order.status.in_(_PAID)).scalar_subquery(),
                select(func.count(Favorite.id)).where(Favorite.user_id == uid).scalar_subquery(),
                select(func.coalesce(func.sum(PageView.active_seconds), 0)).where(PageView.user_id == uid, PageView.started_at >= since).scalar_subquery(),
                select(func.count(AnalyticsSession.id)).where(AnalyticsSession.user_id == uid, AnalyticsSession.started_at >= since).scalar_subquery(),
            )
        )
    ).one()

    # 2) Últimos pedidos com itens
    orders = (
        await db.scalars(
            select(Order)
            .where(Order.user_id == uid)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .order_by(Order.created_at.desc())
            .limit(5)
        )
    ).all()

    # 3) Favoritos mais recentes
    favorites = (
        await db.scalars(
            select(Product)
            .join(Favorite, Favorite.product_id == Product.id)
            .where(Favorite.user_id == uid)
            .order_by(Favorite.created_at.desc())
            .limit(6)
        )
    ).all()

    # 4) Perfil de interesse (score ponderado por categoria)
    interest_rows = (await db.execute(_INTERESTS_SQL, {"uid": uid})).all()
    top_score = max((float(r.score) for r in interest_rows), default=0.0) or 1.0

    # 5) Histórico de acessos
    accesses = (
        await db.scalars(
            select(UserAccessLog).where(UserAccessLog.user_id == uid).order_by(UserAccessLog.occurred_at.desc()).limit(8)
        )
    ).all()

    return DashboardOut(
        user=_user_out(user),
        stats=DashboardStatsOut(
            orders=stats[0],
            total_spent=Decimal(stats[1]),
            favorites=stats[2],
            active_minutes_30d=int(stats[3]) // 60,
            visits_30d=stats[4],
        ),
        recent_orders=[_order_summary(o) for o in orders],
        favorites=[
            ProductCardOut(
                id=p.id, name=p.name, price=p.price, image_path=p.image_path, slug=p.slug, page_path=p.page_path
            )
            for p in favorites
        ],
        interests=[
            InterestOut(category=r.category, score_pct=round(float(r.score) / top_score * 100)) for r in interest_rows
        ],
        access_history=[
            AccessOut(occurred_at=a.occurred_at, success=a.success, device=describe_device(a.user_agent)) for a in accesses
        ],
    )


def _order_summary(order: Order) -> OrderSummaryOut:
    names = [item.product.name for item in order.items]
    label = names[0] if len(names) == 1 else f"{names[0]} + {len(names) - 1} item(ns)"
    return OrderSummaryOut(
        public_id=order.public_id,
        code="GM-" + order.public_id.hex[:8].upper(),
        created_at=order.created_at,
        status=order.status,
        total=order.total,
        items_label=label,
    )


def describe_device(ua: str | None) -> str:
    ua = (ua or "").lower()
    browser = next((name for key, name in (("edg/", "Edge"), ("opr/", "Opera"), ("firefox", "Firefox"),
                                           ("chrome", "Chrome"), ("safari", "Safari")) if key in ua), "Navegador")
    system = next((name for key, name in (("android", "Android"), ("iphone", "iPhone"), ("ipad", "iPad"),
                                          ("windows", "Windows"), ("mac os", "macOS"), ("linux", "Linux")) if key in ua), "")
    return f"{browser} no {system}" if system else browser

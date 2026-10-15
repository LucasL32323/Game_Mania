"""
E-commerce: favoritos (perfil de interesse) e criação de pedidos.

Anti-injeção de SQL: todas as consultas usam o ORM/Core com parâmetros vinculados;
IDs chegam tipados (int > 0) pelo Pydantic/Path. Nenhuma string vira SQL.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Favorite, Order, OrderItem, Product, User
from app.routers.tracking import emit_purchase_event
from app.schemas import OrderIn, OrderOut
from app.security.web import csrf_protect, get_current_user, limiter

router = APIRouter(prefix="/api/v1", tags=["E-commerce"])

ProductIdPath = Annotated[int, Path(gt=0, lt=2_147_483_647)]


# =============================================================================
# Favoritos
# =============================================================================
@router.get("/favorites")
async def list_favorite_ids(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """IDs favoritados — usado pelo gm-ui.js para pintar o estado inicial dos botões."""
    ids = (await db.scalars(select(Favorite.product_id).where(Favorite.user_id == user.id))).all()
    return {"product_ids": list(ids)}


@router.post("/favorites/{product_id}", status_code=status.HTTP_201_CREATED, dependencies=[Depends(csrf_protect)])
async def add_favorite(product_id: ProductIdPath, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)) -> dict:
    if not await db.scalar(select(Product.id).where(Product.id == product_id, Product.is_active.is_(True))):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado.")
    # Idempotente: favoritar duas vezes não gera erro nem duplicata
    await db.execute(
        pg_insert(Favorite)
        .values(user_id=user.id, product_id=product_id)
        .on_conflict_do_nothing(constraint="uq_favorites_user_product")
    )
    await db.commit()
    return {"product_id": product_id, "favorited": True}


@router.delete("/favorites/{product_id}", dependencies=[Depends(csrf_protect)])
async def remove_favorite(product_id: ProductIdPath, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.product_id == product_id))
    await db.commit()
    return {"product_id": product_id, "favorited": False}


# =============================================================================
# Pedidos
# =============================================================================
@router.post("/orders", status_code=status.HTTP_201_CREATED, response_model=OrderOut,
             dependencies=[Depends(csrf_protect)])
@limiter.limit("10/minute")
async def create_order(request: Request, body: OrderIn, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)) -> OrderOut:
    # Consolida itens repetidos do carrinho
    wanted: dict[int, int] = {}
    for item in body.items:
        wanted[item.product_id] = wanted.get(item.product_id, 0) + item.quantity

    # SELECT ... FOR UPDATE em ordem fixa de ID: impede overselling e deadlocks
    products = (
        await db.scalars(
            select(Product)
            .where(Product.id.in_(sorted(wanted)), Product.is_active.is_(True))
            .order_by(Product.id)
            .with_for_update()
        )
    ).all()
    if len(products) != len(wanted):
        raise HTTPException(422, "Um ou mais produtos não estão disponíveis.")

    order = Order(user_id=user.id, payment_method=body.payment_method, total=Decimal("0.00"))
    total = Decimal("0.00")
    for product in products:
        qty = wanted[product.id]
        if product.stock < qty:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Estoque insuficiente para {product.name}.")
        product.stock -= qty
        order.items.append(OrderItem(product_id=product.id, quantity=qty, unit_price=product.price))
        total += product.price * qty  # preço SEMPRE do banco, nunca do cliente
    order.total = total

    db.add(order)
    await db.commit()
    await db.refresh(order, ["created_at", "status"])

    emit_purchase_event(
        user_id=user.id,
        order_public_id=order.public_id,
        total=order.total,
        product_ids=list(wanted),
        session_id=_parse_uuid(request.headers.get("X-GM-Session")),
    )
    return OrderOut(public_id=order.public_id, status=order.status, total=order.total, created_at=order.created_at)


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None

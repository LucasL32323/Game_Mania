"""
Contratos de entrada/saída da API (Pydantic v2).

Primeira linha de defesa contra XSS e injeção:
  • extra="forbid"      → campos desconhecidos são rejeitados
  • tamanhos máximos    → nada de payload gigante
  • regex de caminho    → só caminhos relativos ("/..."); bloqueia "javascript:", "<script>" etc.
  • tipos fortes        → IDs são int/UUID, nunca string concatenada em SQL
"""
from __future__ import annotations

import enum
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.models import OrderStatus, PaymentMethod

# -----------------------------------------------------------------------------
# Tipos reutilizáveis
# -----------------------------------------------------------------------------
PATH_PATTERN = r"^/[A-Za-z0-9\-._~/%]{0,511}$"
SafePath = Annotated[str, Field(pattern=PATH_PATTERN, max_length=512)]
ProductId = Annotated[int, Field(gt=0, lt=2_147_483_647)]
PropValue = Annotated[str, Field(max_length=120)] | int | float | bool

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# -----------------------------------------------------------------------------
# Autenticação
# -----------------------------------------------------------------------------
class RegisterIn(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=10, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = _CONTROL_CHARS.sub("", unicodedata.normalize("NFKC", v))
        if any(ch in v for ch in "<>\"'`"):
            raise ValueError("O nome contém caracteres não permitidos.")
        return v


class LoginIn(StrictModel):
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    public_id: UUID
    name: str
    email: str
    created_at: datetime


# -----------------------------------------------------------------------------
# Tracking (enviado pelo gm-tracker.js)
# -----------------------------------------------------------------------------
class ClientEventType(str, enum.Enum):
    """Eventos aceitos do navegador. 'purchase' NÃO está aqui: só o servidor emite."""
    PAGE_VIEW = "page_view"            # início da visualização
    ENGAGEMENT = "engagement"          # heartbeat / saída: tempo ativo + scroll
    CLICK = "click"
    SEARCH = "search"
    FAVORITE_ADD = "favorite_add"
    FAVORITE_REMOVE = "favorite_remove"
    ADD_TO_CART = "add_to_cart"
    BEGIN_CHECKOUT = "begin_checkout"


class TrackEventIn(StrictModel):
    type: ClientEventType
    ts: datetime
    page_view_id: UUID
    path: SafePath
    referrer_path: SafePath | None = None
    product_id: ProductId | None = None
    active_seconds: int | None = Field(default=None, ge=0, le=86_400)
    scroll_pct: int | None = Field(default=None, ge=0, le=100)
    props: dict[Annotated[str, Field(pattern=r"^[a-z_]{1,32}$")], PropValue] | None = Field(
        default=None, max_length=8
    )


class TrackBatchIn(StrictModel):
    session_id: UUID
    visitor_id: UUID | None = None
    referrer_host: str | None = Field(default=None, max_length=255, pattern=r"^[A-Za-z0-9.\-:]+$")
    csrf_token: str | None = Field(default=None, max_length=128)   # fallback do sendBeacon
    events: list[TrackEventIn] = Field(min_length=1, max_length=50)


class TrackAccepted(BaseModel):
    accepted: bool
    events: int


# -----------------------------------------------------------------------------
# E-commerce
# -----------------------------------------------------------------------------
class OrderItemIn(StrictModel):
    product_id: ProductId
    quantity: int = Field(ge=1, le=10)


class OrderIn(StrictModel):
    # Preço NUNCA vem do cliente: o servidor busca no banco.
    items: list[OrderItemIn] = Field(min_length=1, max_length=30)
    payment_method: PaymentMethod


class OrderOut(BaseModel):
    public_id: UUID
    status: OrderStatus
    total: Decimal
    created_at: datetime


# -----------------------------------------------------------------------------
# Painel do usuário
# -----------------------------------------------------------------------------
class ProductCardOut(BaseModel):
    id: int
    name: str
    price: Decimal
    image_path: str
    slug: str
    page_path: str | None = None   # página de detalhes relativa (validada por CHECK no banco)


class OrderSummaryOut(BaseModel):
    public_id: UUID
    code: str
    created_at: datetime
    status: OrderStatus
    total: Decimal
    items_label: str


class InterestOut(BaseModel):
    category: str
    score_pct: int


class AccessOut(BaseModel):
    occurred_at: datetime
    success: bool
    device: str


class DashboardStatsOut(BaseModel):
    orders: int
    total_spent: Decimal
    favorites: int
    active_minutes_30d: int
    visits_30d: int


class DashboardOut(BaseModel):
    user: UserOut
    stats: DashboardStatsOut
    recent_orders: list[OrderSummaryOut]
    favorites: list[ProductCardOut]
    interests: list[InterestOut]
    access_history: list[AccessOut]

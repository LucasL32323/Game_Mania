"""
Modelagem relacional da GameMania 2.0 (PostgreSQL 15+ / SQLAlchemy 2.0).

Domínios:
  • Identidade ........ users, user_access_log
  • Catálogo .......... products
  • E-commerce ........ orders, order_items           (substitui a tabela única Purchases:
                                                        um pedido pode ter vários itens do carrinho)
  • Interesses ........ favorites (+ mv_user_interest em sql/analytics.sql)
  • Telemetria ........ analytics_sessions, page_views, analytics_events (particionada por mês)

Regras de integridade:
  • Excluir usuário   → favoritos/histórico em CASCADE; telemetria em SET NULL (anonimiza).
  • Pedidos           → RESTRICT em usuário e produto (auditoria fiscal). Para atender
                        pedido de exclusão (LGPD), a conta é anonimizada, não apagada.
  • Telemetria        → sem FK para produto: dado sujo do cliente nunca derruba um lote.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    PrimaryKeyConstraint,
    Sequence,
    SmallInteger,
    String,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates

from app.security.crypto import get_email_cipher, normalize_email


# =============================================================================
# Base e tipos customizados
# =============================================================================
class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


class EncryptedEmail(TypeDecorator):
    """
    Coluna BYTEA com cifragem transparente AES-256-GCM.

    Gravação: str → EmailCipher.encrypt()  → bytes no banco
    Leitura : bytes → EmailCipher.decrypt() → str na aplicação

    ⚠ Nunca filtre por esta coluna (WHERE email = ...): o nonce aleatório faz cada
      cifragem ser diferente. Use sempre User.email_bidx (blind index).
    """
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> bytes | None:
        return None if value is None else get_email_cipher().encrypt(value)

    def process_result_value(self, value: bytes | None, dialect) -> str | None:
        return None if value is None else get_email_cipher().decrypt(bytes(value))


def _str_enum(enum_cls: type[enum.Enum], length: int) -> Enum:
    """Enum como VARCHAR + CHECK (evolui sem ALTER TYPE, ao contrário do ENUM nativo)."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")


# =============================================================================
# Enums de domínio
# =============================================================================
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    PIX = "pix"
    CARD = "card"
    BOLETO = "boleto"


class EventType(str, enum.Enum):
    """Eventos do funil e de engajamento ativo (page views ficam em page_views)."""
    CLICK = "click"
    SEARCH = "search"
    FAVORITE_ADD = "favorite_add"
    FAVORITE_REMOVE = "favorite_remove"
    ADD_TO_CART = "add_to_cart"
    BEGIN_CHECKOUT = "begin_checkout"
    PURCHASE = "purchase"        # emitido SOMENTE pelo servidor (rota de pedidos)


# =============================================================================
# Identidade
# =============================================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # ID público (UUID) exposto em URLs/JWT: evita enumeração de IDs sequenciais.
    public_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # E-mail cifrado (AES-256-GCM) + índice cego (HMAC-SHA256) para login e UNIQUE.
    email: Mapped[str] = mapped_column("email_encrypted", EncryptedEmail(), nullable=False)
    email_bidx: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)

    # Argon2id (ou bcrypt legado até o próximo login).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[datetime | None]

    orders: Mapped[list[Order]] = relationship(back_populates="user")
    favorites: Mapped[list[Favorite]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    access_log: Mapped[list[UserAccessLog]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

    @validates("email")
    def _sync_blind_index(self, _key: str, value: str) -> str:
        """Toda atribuição de e-mail recalcula o blind index automaticamente."""
        normalized = normalize_email(value)
        self.email_bidx = get_email_cipher().blind_index(normalized)
        return normalized


class UserAccessLog(Base):
    """Histórico de acessos (sucesso e falha) — base do painel e do bloqueio anti força bruta."""
    __tablename__ = "user_access_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(40))
    ip_hash: Mapped[str | None] = mapped_column(String(32))       # IP pseudonimizado
    user_agent: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship(back_populates="access_log")

    # btree composto atende ORDER BY occurred_at DESC via leitura reversa
    __table_args__ = (Index("ix_access_log_user_time", "user_id", "occurred_at"),)


# =============================================================================
# Catálogo
# =============================================================================
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)   # hardware, computadores, perifericos, escritorio, consoles
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    # Página de detalhes (relativa, ex.: "pcgamerrtx3060.html"). NULL = produto sem página própria ainda.
    page_path: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_positive"),
        CheckConstraint("stock >= 0", name="ck_products_stock_positive"),
        # Regra de front-end garantida no banco: todo asset vive em /img
        CheckConstraint("image_path LIKE '/img/%'", name="ck_products_image_in_img"),
        # Só nome de arquivo .html: impede javascript:, URLs externas e ../ (open redirect / XSS via href)
        CheckConstraint(r"page_path ~ '^[A-Za-z0-9._-]+\.html$'", name="ck_products_page_path"),
        Index("ix_products_category_active", "category", postgresql_where=text("is_active")),
    )


# =============================================================================
# E-commerce
# =============================================================================
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(_str_enum(OrderStatus, 20), default=OrderStatus.PENDING)
    payment_method: Mapped[PaymentMethod] = mapped_column(_str_enum(PaymentMethod, 10), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    paid_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_orders_total_positive"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # snapshot do preço na compra

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
        CheckConstraint("quantity > 0", name="ck_order_items_qty_positive"),
        Index("ix_order_items_product", "product_id"),   # "itens mais comprados"
    )


# =============================================================================
# Interesses
# =============================================================================
class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="favorites")
    product: Mapped[Product] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_favorites_user_product"),
        Index("ix_favorites_product", "product_id"),
    )


# =============================================================================
# Telemetria (alto volume — gravada pelo worker em lote, nunca na requisição)
# =============================================================================
class AnalyticsSession(Base):
    """Uma visita. Base para frequência de retorno e visitantes únicos."""
    __tablename__ = "analytics_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)               # gerado no navegador
    visitor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)                  # persistente (só com consentimento)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    landing_path: Mapped[str] = mapped_column(String(512), nullable=False)
    referrer_host: Mapped[str | None] = mapped_column(String(255))
    device: Mapped[str | None] = mapped_column(String(10))                      # mobile | tablet | desktop
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip_hash: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        Index("ix_sessions_visitor", "visitor_id", "started_at"),
        Index("ix_sessions_user", "user_id", "started_at"),
        Index("brin_sessions_started", "started_at", postgresql_using="brin"),
    )


class PageView(Base):
    """Uma visualização de página: tempo ativo real, profundidade de rolagem e origem."""
    __tablename__ = "page_views"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)               # page_view_id do navegador
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analytics_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    referrer_path: Mapped[str | None] = mapped_column(String(512))              # histórico de navegação
    product_id: Mapped[int | None] = mapped_column(Integer)                     # sem FK de propósito
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    max_scroll_pct: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))

    __table_args__ = (
        CheckConstraint("active_seconds BETWEEN 0 AND 86400", name="ck_page_views_active"),
        CheckConstraint("max_scroll_pct BETWEEN 0 AND 100", name="ck_page_views_scroll"),
        Index("ix_page_views_session", "session_id", "started_at"),
        Index("ix_page_views_path_time", "path", "started_at"),
        Index("ix_page_views_product", "product_id", postgresql_where=text("product_id IS NOT NULL")),
        Index("ix_page_views_user", "user_id", postgresql_where=text("user_id IS NOT NULL")),
    )


_events_id_seq = Sequence("analytics_events_id_seq")


class AnalyticsEvent(Base):
    """
    Eventos ativos (cliques, favoritos, carrinho, checkout, compra).
    Tabela PARTICIONADA por mês (RANGE occurred_at): partições antigas podem ser
    arquivadas/descartadas em O(1) com DETACH/DROP, sem VACUUM pesado.
    """
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(BigInteger, _events_id_seq, server_default=_events_id_seq.next_value())
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[EventType] = mapped_column(_str_enum(EventType, 24), nullable=False)
    path: Mapped[str | None] = mapped_column(String(512))
    product_id: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))              # ex.: total do pedido
    props: Mapped[dict | None] = mapped_column(JSON_VARIANT)

    __table_args__ = (
        PrimaryKeyConstraint("id", "occurred_at", name="pk_analytics_events"),   # chave de partição no PK
        Index("ix_events_type_time", "event_type", "occurred_at"),
        Index("ix_events_session", "session_id"),
        Index("ix_events_product", "product_id", postgresql_where=text("product_id IS NOT NULL")),
        Index("ix_events_user", "user_id", postgresql_where=text("user_id IS NOT NULL")),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

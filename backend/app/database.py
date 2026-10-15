"""
Conexões assíncronas com PostgreSQL (driver asyncpg).

Dois pools isolados:
  • engine            → e-commerce, auth, favoritos (baixa latência, prioridade alta)
  • analytics_engine  → gravação em lote da telemetria (pode saturar sem afetar o checkout)
"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)

analytics_engine = create_async_engine(
    _settings.analytics_database_url or _settings.database_url,
    pool_size=4,          # poucas conexões: o worker grava em lotes grandes
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency do FastAPI: uma sessão por requisição, sempre fechada."""
    async with SessionLocal() as session:
        yield session

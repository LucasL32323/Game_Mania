"""
Cria as tabelas a partir dos models (idempotente: só cria o que não existe).

Uso (dentro de backend/):  python -m scripts.init_db
Em produção, prefira migrações versionadas com Alembic:
    alembic init migrations  →  alembic revision --autogenerate -m "schema inicial"  →  alembic upgrade head
Depois rode sql/analytics.sql (partições, views, MV, roles) e sql/seed_products.sql.
"""
import asyncio

from app.database import analytics_engine, engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    await analytics_engine.dispose()
    print("Schema criado/atualizado.")


if __name__ == "__main__":
    asyncio.run(main())

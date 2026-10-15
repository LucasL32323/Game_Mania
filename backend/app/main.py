"""
GameMania 2.0 — ponto de entrada da API.

Rodar (dev):   uvicorn app.main:app --reload
Rodar (prod):  uvicorn app.main:app --workers 4 --proxy-headers --forwarded-allow-ips=127.0.0.1
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import analytics_engine, engine
from app.frontend import FrontendEstatico
from app.routers import account, auth, commerce, tracking
from app.security.web import issue_csrf_cookie, limiter, security_headers_middleware
from app.services.tracking_queue import tracking_queue

settings = get_settings()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await tracking_queue.start()          # worker de gravação em lote
    yield
    await tracking_queue.stop()           # drena a fila antes de desligar
    await engine.dispose()
    await analytics_engine.dispose()


app = FastAPI(
    title="GameMania API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,   # Swagger só em desenvolvimento
    redoc_url=None,
    openapi_url="/openapi.json" if settings.is_dev else None,
)

# --- Middlewares (a ordem importa: o último adicionado roda primeiro) --------
app.middleware("http")(security_headers_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,          # nunca "*" com credenciais (erro do server.js)
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-GM-Session"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Rotas -------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(tracking.router)
app.include_router(commerce.router)
app.include_router(account.router)


@app.get("/api/v1/csrf", status_code=status.HTTP_204_NO_CONTENT, tags=["Segurança"])
async def csrf_bootstrap(response: Response) -> Response:
    """Entrega o cookie CSRF para páginas estáticas (chamado pelo gm-tracker.js / gm-ui.js)."""
    issue_csrf_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/healthz", tags=["Infra"])
async def healthz() -> dict:
    return {"status": "ok", "tracking": tracking_queue.stats}


# --- Front-end estático (apenas dev; em produção o Nginx serve com cache longo) ---
if settings.serve_frontend:
    frontend = Path(settings.frontend_dir).resolve()
    # Rotas inexistentes: site → frontend/404.html (status 404) · /api/... → JSON 404
    app.mount("/", FrontendEstatico(directory=frontend, html=True), name="frontend")

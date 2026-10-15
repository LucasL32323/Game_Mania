"""
Defesas HTTP da API GameMania 2.0.

  XSS   → CSP restritiva + nosniff + cookies HttpOnly (JS não lê a sessão)
          + front-end só renderiza dados via textContent / <template>.
  CSRF  → 3 camadas: cookie de sessão SameSite=Lax, verificação de Origin/Referer
          e double-submit token com prefixo __Host- (imune a injeção por subdomínio).
  SQLi  → nenhuma SQL concatenada: ORM/Core com parâmetros vinculados (ver routers).
  Brute → rate limit por IP (slowapi) + bloqueio por falhas no histórico de acesso.
"""
from __future__ import annotations

import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()

# Prefixo __Host- exige Secure + Path=/ + sem Domain → cookie não pode ser
# sobrescrito por um subdomínio comprometido. Em dev (HTTP) usamos nome simples.
_PREFIX = "__Host-" if settings.cookie_secure else ""
SESSION_COOKIE = f"{_PREFIX}gm_session"
CSRF_COOKIE = f"{_PREFIX}gm_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

limiter = Limiter(key_func=get_remote_address, headers_enabled=False)


# =============================================================================
# Headers de segurança (aplicados a TODA resposta)
# =============================================================================
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net",           # sem 'unsafe-inline'
        "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",                                  # só /img do próprio domínio
        "connect-src 'self'",                                    # tracker só fala com a API
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ]
)


async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# =============================================================================
# CSRF
# =============================================================================
def issue_csrf_cookie(response: Response) -> str:
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=60 * 60 * 12,
        secure=settings.cookie_secure,
        httponly=False,          # o JS precisa ler para ecoar no header
        samesite="strict",
        path="/",
    )
    return token


def _origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer is None:
            return False
        parts = urlsplit(referer)
        origin = f"{parts.scheme}://{parts.netloc}"
    return origin in settings.allowed_origins


def enforce_csrf(request: Request, body_token: str | None = None) -> None:
    """Valida Origin + double-submit token (header ou, no sendBeacon, corpo)."""
    if request.method in SAFE_METHODS:
        return
    if not _origin_allowed(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origem não permitida.")
    cookie_token = request.cookies.get(CSRF_COOKIE)
    sent_token = request.headers.get(CSRF_HEADER) or body_token
    if not cookie_token or not sent_token or not hmac.compare_digest(cookie_token, sent_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token CSRF inválido.")


async def csrf_protect(request: Request) -> None:
    """Dependency para rotas com corpo JSON padrão."""
    enforce_csrf(request)


# =============================================================================
# Sessão (JWT em cookie HttpOnly — nunca em localStorage como no login.js legado)
# =============================================================================
@dataclass(frozen=True, slots=True)
class SessionClaims:
    user_id: int
    public_id: uuid.UUID


def set_session_cookie(response: Response, user: User) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user.public_id),
            "uid": user.id,
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
            "jti": secrets.token_hex(8),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.jwt_ttl_minutes * 60,
        secure=settings.cookie_secure,
        httponly=True,           # inacessível ao JavaScript → XSS não rouba sessão
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


def read_session_claims(request: Request) -> SessionClaims | None:
    """Decodifica o JWT sem tocar no banco (usado no tracking de alta vazão)."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],               # fixa o algoritmo (evita ataque "alg: none")
            options={"require": ["exp", "sub", "uid"]},
        )
        return SessionClaims(user_id=int(data["uid"]), public_id=uuid.UUID(data["sub"]))
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    claims = read_session_claims(request)
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    user = await db.scalar(
        select(User).where(User.id == claims.user_id, User.public_id == claims.public_id, User.is_active.is_(True))
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente.")
    return user


# =============================================================================
# Utilidades de requisição
# =============================================================================
def client_ip(request: Request) -> str | None:
    # Atrás de proxy, rode o uvicorn com --proxy-headers --forwarded-allow-ips=<IP do Nginx>
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:300] if ua else None


def device_from_ua(ua: str | None) -> str:
    ua = (ua or "").lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobi" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    return "desktop"

"""
Autenticação: cadastro, login, logout e perfil.

• Hash de senha roda em threadpool (Argon2 usa 64 MiB/CPU; não pode bloquear o event loop).
• Mensagens genéricas + verificação falsa → sem enumeração de e-mails (o server.js
  legado respondia 404 "Usuário não encontrado" x 401 "Senha incorreta").
• Toda tentativa em conta existente vai para user_access_log (histórico + anti força bruta).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.models import User, UserAccessLog
from app.schemas import LoginIn, RegisterIn, UserOut
from app.security.crypto import burn_password_check, get_email_cipher, hash_password, pseudonymize_ip, verify_password
from app.security.web import (
    clear_session_cookie,
    client_ip,
    csrf_protect,
    get_current_user,
    issue_csrf_cookie,
    limiter,
    set_session_cookie,
    user_agent,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

LOCKOUT_FAILURES = 10
LOCKOUT_WINDOW = timedelta(minutes=15)


def _user_out(user: User) -> UserOut:
    return UserOut(public_id=user.public_id, name=user.name, email=user.email, created_at=user.created_at)


def _invalid_credentials() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut,
             dependencies=[Depends(csrf_protect)])
@limiter.limit("5/minute")
async def register(request: Request, response: Response, body: RegisterIn,
                   db: AsyncSession = Depends(get_db)) -> UserOut:
    bidx = get_email_cipher().blind_index(body.email)
    if await db.scalar(select(User.id).where(User.email_bidx == bidx)):
        # Mensagem neutra. Em produção: fluxo de confirmação por e-mail em ambos os casos.
        raise HTTPException(status.HTTP_409_CONFLICT, "Não foi possível concluir o cadastro com esses dados.")

    password_hash = await run_in_threadpool(hash_password, body.password.get_secret_value())
    user = User(name=body.name, email=body.email, password_hash=password_hash)  # e-mail cifrado no flush
    db.add(user)
    try:
        await db.flush()  # INSERT agora: gera o id e dispara a UNIQUE do blind index
    except IntegrityError:  # corrida entre dois cadastros simultâneos
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Não foi possível concluir o cadastro com esses dados.") from None

    # O cadastro já abre sessão → entra no histórico como primeiro acesso
    db.add(
        UserAccessLog(
            user_id=user.id,
            success=True,
            ip_hash=pseudonymize_ip(client_ip(request)),
            user_agent=user_agent(request),
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    set_session_cookie(response, user)
    issue_csrf_cookie(response)
    return _user_out(user)


@router.post("/login", response_model=UserOut, dependencies=[Depends(csrf_protect)])
@limiter.limit("5/minute")
async def login(request: Request, response: Response, body: LoginIn,
                db: AsyncSession = Depends(get_db)) -> UserOut:
    password = body.password.get_secret_value()
    bidx = get_email_cipher().blind_index(body.email)
    user = await db.scalar(select(User).where(User.email_bidx == bidx))

    if user is None or not user.is_active:
        await run_in_threadpool(burn_password_check, password)  # tempo igual ao de senha errada
        raise _invalid_credentials()

    recent_failures = await db.scalar(
        select(func.count(UserAccessLog.id)).where(
            UserAccessLog.user_id == user.id,
            UserAccessLog.success.is_(False),
            UserAccessLog.occurred_at > datetime.now(timezone.utc) - LOCKOUT_WINDOW,
        )
    )
    if recent_failures >= LOCKOUT_FAILURES:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Tente de novo em 15 minutos.")

    ok, upgraded_hash = await run_in_threadpool(verify_password, password, user.password_hash)
    db.add(
        UserAccessLog(
            user_id=user.id,
            success=ok,
            failure_reason=None if ok else "invalid_password",
            ip_hash=pseudonymize_ip(client_ip(request)),
            user_agent=user_agent(request),
        )
    )
    if not ok:
        await db.commit()
        raise _invalid_credentials()

    if upgraded_hash:  # bcrypt legado → Argon2id, transparente para o usuário
        user.password_hash = upgraded_hash
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    set_session_cookie(response, user)
    issue_csrf_cookie(response)  # rotaciona o token CSRF a cada login
    return _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(csrf_protect)])
async def logout(response: Response) -> Response:
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)

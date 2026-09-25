import hashlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from veille.config import Settings
from veille.db import utcnow
from veille.errors import DomainError, forbidden, unauthorized
from veille.security import TotpCipher, constant_time_equals, sha256
from veille.services import sessions
from veille.services.sessions import AuthContext
from veille.url_policy import Resolver

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "x-csrf-token"
_ROLE_RANK = {"viewer": 0, "editor": 1, "admin": 2}


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_cipher(request: Request) -> TotpCipher:
    return request.app.state.totp_cipher


def get_resolver(request: Request) -> Resolver:
    return request.app.state.resolver


def client_ip(request: Request) -> str | None:
    # Derrière nginx : uvicorn réécrit request.client via --proxy-headers, uniquement
    # pour les proxys listés dans FORWARDED_ALLOW_IPS.
    return request.client.host if request.client else None


Db = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Cipher = Annotated[TotpCipher, Depends(get_cipher)]
UrlResolver = Annotated[Resolver, Depends(get_resolver)]
ClientIp = Annotated[str | None, Depends(client_ip)]


def _check_csrf(request: Request, ctx: AuthContext) -> None:
    if request.method in SAFE_METHODS:
        return
    header = request.headers.get(CSRF_HEADER, "")
    if not header or not constant_time_equals(sha256(header), ctx.session.csrf_hash):
        raise DomainError(403, "Jeton CSRF invalide", None, "csrf")


async def _context(request: Request, db: AsyncSession, settings: Settings) -> AuthContext:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise unauthorized()
    ctx = await sessions.resolve(db, token, settings, utcnow())
    if ctx is None:
        raise unauthorized("Session expirée ou révoquée.")
    _check_csrf(request, ctx)
    return ctx


async def any_session(request: Request, db: Db, settings: AppSettings) -> AuthContext:
    return await _context(request, db, settings)


async def pre_mfa_session(request: Request, db: Db, settings: AppSettings) -> AuthContext:
    ctx = await _context(request, db, settings)
    if ctx.session.mfa_verified:
        raise DomainError(409, "Conflit", "Second facteur déjà validé.", "mfa-done")
    return ctx


def require_role(minimum: str) -> Callable[..., Awaitable[AuthContext]]:
    async def dependency(request: Request, db: Db, settings: AppSettings) -> AuthContext:
        ctx = await _context(request, db, settings)
        if not ctx.session.mfa_verified:
            raise DomainError(401, "Second facteur requis", None, "mfa-required")
        if _ROLE_RANK[ctx.user.role] < _ROLE_RANK[minimum]:
            raise forbidden()
        return ctx

    return dependency


async def require_service(request: Request, settings: AppSettings) -> None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not hmac.compare_digest(digest, settings.internal_token_sha256):
        raise unauthorized("Jeton de service invalide.")


AnySession = Annotated[AuthContext, Depends(any_session)]
PreMfa = Annotated[AuthContext, Depends(pre_mfa_session)]
Viewer = Annotated[AuthContext, Depends(require_role("viewer"))]
Editor = Annotated[AuthContext, Depends(require_role("editor"))]
Admin = Annotated[AuthContext, Depends(require_role("admin"))]

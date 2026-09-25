from fastapi import APIRouter, Request, Response, status

from veille.config import Settings
from veille.db import utcnow
from veille.deps import AnySession, AppSettings, Cipher, ClientIp, Db, PreMfa, Viewer
from veille.schemas import LoginIn, LoginOut, MeOut, MfaCodeIn, MfaEnrollOut, PasswordChangeIn
from veille.services import auth
from veille.services.sessions import IssuedSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookies(response: Response, settings: Settings, issued: IssuedSession) -> None:
    common = {
        "secure": settings.cookie_secure,
        "samesite": "strict",
        "path": "/",
        "max_age": issued.max_age_seconds,
    }
    response.set_cookie(settings.session_cookie_name, issued.token, httponly=True, **common)  # type: ignore[arg-type]
    # Lisible par le front (pas HttpOnly) : c'est lui qui le recopie dans X-CSRF-Token.
    response.set_cookie(settings.csrf_cookie_name, issued.csrf, httponly=False, **common)  # type: ignore[arg-type]


def _clear_cookies(response: Response, settings: Settings) -> None:
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="strict")


@router.post("/login", response_model=LoginOut)
async def login(
    data: LoginIn, request: Request, response: Response, db: Db, settings: AppSettings, ip: ClientIp
) -> LoginOut:
    issued, user = await auth.login(
        db, data, settings, ip=ip, user_agent=request.headers.get("user-agent"), now=utcnow()
    )
    _set_cookies(response, settings, issued)
    return LoginOut(mfa_enrolled=user.totp_confirmed)


@router.post("/mfa/enroll", response_model=MfaEnrollOut)
async def mfa_enroll(ctx: PreMfa, db: Db, cipher: Cipher, settings: AppSettings) -> MfaEnrollOut:
    return await auth.enroll_mfa(db, ctx, cipher, settings)


@router.post("/mfa/verify", response_model=MeOut)
async def mfa_verify(
    data: MfaCodeIn,
    ctx: PreMfa,
    request: Request,
    response: Response,
    db: Db,
    cipher: Cipher,
    settings: AppSettings,
    ip: ClientIp,
) -> MeOut:
    issued = await auth.verify_mfa(
        db,
        ctx,
        data.code,
        cipher,
        settings,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        now=utcnow(),
    )
    _set_cookies(response, settings, issued)
    return MeOut.model_validate(ctx.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(ctx: AnySession, db: Db, settings: AppSettings, ip: ClientIp) -> Response:
    await auth.logout(db, ctx, ip=ip)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookies(response, settings)
    return response


@router.get("/me", response_model=MeOut)
async def me(ctx: Viewer) -> MeOut:
    return MeOut.model_validate(ctx.user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: PasswordChangeIn, ctx: Viewer, db: Db, ip: ClientIp) -> None:
    await auth.change_password(db, ctx, data, ip=ip)

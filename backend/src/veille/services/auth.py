from datetime import datetime, timedelta

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from veille.config import Settings
from veille.errors import DomainError, conflict, unauthorized
from veille.models import User
from veille.schemas import LoginIn, MfaEnrollOut, PasswordChangeIn
from veille.security import (
    TotpCipher,
    hash_password_async,
    match_totp_step,
    new_totp_secret,
    password_needs_rehash,
    totp_uri,
    verify_password_async,
)
from veille.services import audit, sessions
from veille.services.sessions import AuthContext, IssuedSession

MAX_FAILED_LOGINS = 5
MAX_MFA_ATTEMPTS = 5
# Message unique : distinguer "compte inconnu", "mauvais mot de passe" ou "verrouillé"
# permettrait d'énumérer les comptes.
GENERIC_LOGIN_ERROR = "Identifiants invalides ou compte temporairement verrouillé."
# Durée fixe, pas exponentielle : n'importe qui connaissant l'email peut déclencher le
# verrou, un verrou long deviendrait un déni de service sur le compte admin. Le compteur
# n'est remis à zéro que par un succès : après le premier verrou, chaque échec re-verrouille,
# soit un essai par tranche de 15 min.
LOCK_DURATION = timedelta(minutes=15)


async def login(
    db: AsyncSession,
    data: LoginIn,
    settings: Settings,
    *,
    ip: str | None,
    user_agent: str | None,
    now: datetime,
) -> tuple[IssuedSession, User]:
    user = await db.scalar(select(User).where(User.email == data.email))
    # Rend la connexion au pool avant argon2 : sinon les logins en attente d'un créneau de
    # hachage monopolisent le petit pool et bloquent tout le site.
    await db.commit()

    locked = user is not None and user.locked_until is not None and user.locked_until > now
    usable_hash = user.password_hash if user is not None and user.is_active else None
    # Compte verrouillé : on paie quand même le coût argon2 pour ne rien révéler par le temps.
    password_ok = await verify_password_async(None if locked else usable_hash, data.password)

    if locked:
        audit.record(db, action="login.locked", target=data.email, ip=ip)
        await db.commit()
        raise unauthorized(GENERIC_LOGIN_ERROR)

    if not password_ok:
        if user is not None:
            # Incrément atomique en base : un read-modify-write en Python perdrait des échecs
            # sous requêtes parallèles et permettrait de dépasser MAX_FAILED_LOGINS essais.
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(
                    failed_logins=User.failed_logins + 1,
                    locked_until=case(
                        (User.failed_logins + 1 >= MAX_FAILED_LOGINS, now + LOCK_DURATION),
                        else_=User.locked_until,
                    ),
                )
                .execution_options(synchronize_session=False)
            )
        audit.record(db, action="login.failed", target=data.email, ip=ip)
        await db.commit()
        raise unauthorized(GENERIC_LOGIN_ERROR)

    assert user is not None
    # Remise à zéro explicite : l'objet chargé peut porter un compteur périmé, et l'ORM
    # n'émettrait aucun UPDATE s'il valait déjà 0.
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(failed_logins=0, locked_until=None)
        .execution_options(synchronize_session=False)
    )
    if password_needs_rehash(user.password_hash):
        user.password_hash = await hash_password_async(data.password)
    await sessions.purge_expired(db, now)
    issued = sessions.issue(
        db, user, mfa_verified=False, settings=settings, ip=ip, user_agent=user_agent, now=now
    )
    audit.record(db, action="login.password_ok", actor=user, ip=ip)
    await db.commit()
    return issued, user


async def enroll_mfa(
    db: AsyncSession, ctx: AuthContext, cipher: TotpCipher, settings: Settings
) -> MfaEnrollOut:
    if ctx.user.totp_confirmed:
        raise conflict("Le second facteur est déjà configuré.")
    secret = new_totp_secret()
    ctx.user.totp_secret_enc = cipher.encrypt(secret)
    await db.commit()
    return MfaEnrollOut(
        otpauth_uri=totp_uri(secret, ctx.user.email, settings.totp_issuer), secret=secret
    )


async def verify_mfa(
    db: AsyncSession,
    ctx: AuthContext,
    code: str,
    cipher: TotpCipher,
    settings: Settings,
    *,
    ip: str | None,
    user_agent: str | None,
    now: datetime,
) -> IssuedSession:
    user, pending = ctx.user, ctx.session
    if not user.totp_secret_enc:
        raise conflict("Configurez d'abord votre application d'authentification.")

    step = match_totp_step(
        cipher.decrypt(user.totp_secret_enc), code, user.totp_last_step, now.timestamp()
    )
    if step is None:
        pending.mfa_attempts += 1
        if pending.mfa_attempts >= MAX_MFA_ATTEMPTS:
            await db.delete(pending)
            audit.record(db, action="mfa.too_many_attempts", actor=user, ip=ip)
            await db.commit()
            raise unauthorized("Trop d'essais. Reconnectez-vous.")
        audit.record(db, action="mfa.failed", actor=user, ip=ip)
        await db.commit()
        raise DomainError(401, "Code invalide", "Code invalide ou déjà utilisé.", "mfa-invalid")

    first_enrollment = not user.totp_confirmed
    user.totp_last_step = step
    user.totp_confirmed = True
    # Rotation : le jeton pré-MFA, potentiellement exposé, ne devient jamais un jeton complet.
    await db.delete(pending)
    issued = sessions.issue(
        db, user, mfa_verified=True, settings=settings, ip=ip, user_agent=user_agent, now=now
    )
    audit.record(
        db, action="mfa.enrolled" if first_enrollment else "login.success", actor=user, ip=ip
    )
    await db.commit()
    return issued


async def logout(db: AsyncSession, ctx: AuthContext, *, ip: str | None) -> None:
    await db.delete(ctx.session)
    audit.record(db, action="logout", actor=ctx.user, ip=ip)
    await db.commit()


async def change_password(
    db: AsyncSession, ctx: AuthContext, data: PasswordChangeIn, *, ip: str | None
) -> None:
    if not await verify_password_async(ctx.user.password_hash, data.current_password):
        raise DomainError(422, "Mot de passe actuel incorrect", None, "wrong-password")
    if data.new_password.lower() == ctx.user.email:
        raise DomainError(422, "Mot de passe refusé", "Identique à l'email.", "weak-password")
    ctx.user.password_hash = await hash_password_async(data.new_password)
    await sessions.revoke_all(db, ctx.user.id, keep=ctx.session.id)
    audit.record(db, action="password.changed", actor=ctx.user, ip=ip)
    await db.commit()

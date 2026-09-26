import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from veille.errors import DomainError, conflict, constraint_name, not_found
from veille.models import AuditEvent, User
from veille.schemas import AuditOut, UserIn, UserOut, UserPatch
from veille.security import hash_password_async
from veille.services import audit, sessions


async def list_users(db: AsyncSession) -> list[UserOut]:
    rows = await db.scalars(select(User).order_by(User.email))
    return [UserOut.model_validate(u) for u in rows]


async def create_user(
    db: AsyncSession, data: UserIn, actor: User | None, ip: str | None
) -> UserOut:
    if data.password.lower() == data.email:
        raise DomainError(422, "Mot de passe refusé", "Identique à l'email.", "weak-password")
    user = User(
        email=data.email, password_hash=await hash_password_async(data.password), role=data.role
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if constraint_name(exc) == "uq_users_email":
            raise conflict("Un compte existe déjà avec cet email.") from exc
        raise
    audit.record(
        db,
        action="user.created",
        actor=actor,
        target=str(user.id),
        ip=ip,
        details={"role": data.role},
    )
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


async def _get(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("Utilisateur")
    return user


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, patch: UserPatch, actor: User, ip: str | None
) -> UserOut:
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    if user_id == actor.id and changes:
        # Empêche un admin de se retirer ses propres droits et de verrouiller l'instance.
        raise DomainError(409, "Conflit", "Modifiez votre compte via un autre admin.", "self-edit")
    user = await _get(db, user_id)
    for field, value in changes.items():
        setattr(user, field, value)
    if changes.get("is_active") is False or "role" in changes:
        await sessions.revoke_all(db, user.id)
    audit.record(
        db,
        action="user.updated",
        actor=actor,
        target=str(user_id),
        ip=ip,
        details={k: str(v) for k, v in changes.items()},
    )
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


async def reset_mfa(db: AsyncSession, user_id: uuid.UUID, actor: User, ip: str | None) -> UserOut:
    user = await _get(db, user_id)
    user.totp_secret_enc = None
    user.totp_confirmed = False
    user.totp_last_step = None
    await sessions.revoke_all(db, user.id)
    audit.record(db, action="user.mfa_reset", actor=actor, target=str(user_id), ip=ip)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


async def unlock(db: AsyncSession, user_id: uuid.UUID, actor: User, ip: str | None) -> UserOut:
    user = await _get(db, user_id)
    user.failed_logins = 0
    user.locked_until = None
    audit.record(db, action="user.unlocked", actor=actor, target=str(user_id), ip=ip)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


async def list_audit(db: AsyncSession, limit: int) -> list[AuditOut]:
    rows = await db.scalars(
        select(AuditEvent).order_by(AuditEvent.at.desc(), AuditEvent.id.desc()).limit(limit)
    )
    return [AuditOut.model_validate(e) for e in rows]

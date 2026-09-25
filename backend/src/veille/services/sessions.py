import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from veille.config import Settings
from veille.models import User, UserSession
from veille.security import new_token, sha256

_LAST_SEEN_WRITE_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession


@dataclass(frozen=True)
class IssuedSession:
    session: UserSession
    token: str
    csrf: str
    max_age_seconds: int


def issue(
    db: AsyncSession,
    user: User,
    *,
    mfa_verified: bool,
    settings: Settings,
    ip: str | None,
    user_agent: str | None,
    now: datetime,
) -> IssuedSession:
    token, csrf = new_token(), new_token()
    lifetime = (
        timedelta(hours=settings.session_absolute_hours)
        if mfa_verified
        else timedelta(minutes=settings.pre_mfa_minutes)
    )
    session = UserSession(
        token_hash=sha256(token),
        csrf_hash=sha256(csrf),
        user_id=user.id,
        mfa_verified=mfa_verified,
        mfa_attempts=0,
        last_seen_at=now,
        expires_at=now + lifetime,
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    return IssuedSession(session, token, csrf, int(lifetime.total_seconds()))


async def resolve(
    db: AsyncSession, token: str, settings: Settings, now: datetime
) -> AuthContext | None:
    row = (
        await db.execute(
            select(UserSession, User)
            .join(User, UserSession.user_id == User.id)
            .where(UserSession.token_hash == sha256(token))
        )
    ).one_or_none()
    if row is None:
        return None
    session, user = row
    idle_deadline = session.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
    if now >= session.expires_at or now >= idle_deadline or not user.is_active:
        await db.delete(session)
        await db.commit()
        return None
    if now - session.last_seen_at >= _LAST_SEEN_WRITE_INTERVAL:
        session.last_seen_at = now
        await db.commit()
    return AuthContext(user, session)


async def revoke_all(
    db: AsyncSession, user_id: uuid.UUID, *, keep: uuid.UUID | None = None
) -> None:
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep is not None:
        stmt = stmt.where(UserSession.id != keep)
    await db.execute(stmt)


async def purge_expired(db: AsyncSession, now: datetime) -> None:
    # Appelée à chaque login : la table reste bornée sans tâche planifiée à maintenir.
    await db.execute(delete(UserSession).where(UserSession.expires_at < now))

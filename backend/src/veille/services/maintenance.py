from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from veille.config import Settings
from veille.models import Article, AuditEvent, UserSession
from veille.schemas import PurgeOut
from veille.services import audit


async def purge(db: AsyncSession, settings: Settings, *, ip: str | None, now: datetime) -> PurgeOut:
    # Sur fetched_at, pas published_at : un article ancien encore présent dans un flux serait
    # sinon supprimé puis réinséré à chaque relevé, la contrainte unique ne le retenant plus.
    articles = await db.execute(
        delete(Article).where(
            Article.fetched_at < now - timedelta(days=settings.article_retention_days)
        )
    )
    events = await db.execute(
        delete(AuditEvent).where(
            AuditEvent.at < now - timedelta(days=settings.audit_retention_days)
        )
    )
    expired = await db.execute(delete(UserSession).where(UserSession.expires_at < now))
    result = PurgeOut(
        articles=articles.rowcount,  # type: ignore[attr-defined]
        audit_events=events.rowcount,  # type: ignore[attr-defined]
        sessions=expired.rowcount,  # type: ignore[attr-defined]
    )
    # Écrit après la purge : l'événement survit à sa propre exécution.
    audit.record(db, action="maintenance.purge", service=True, ip=ip, details=result.model_dump())
    await db.commit()
    return result

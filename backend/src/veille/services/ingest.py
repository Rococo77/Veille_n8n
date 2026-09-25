"""Réception des résultats n8n.

Tout ce qui arrive ici vient de flux RSS tiers relayés par n8n : c'est de la donnée
non fiable. Chaque article est nettoyé et validé individuellement ; un article
invalide est écarté sans faire échouer le lot.
"""

import html
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from veille.errors import not_found
from veille.models import Article, Source, VeilleGroup
from veille.schemas import IngestArticleIn, IngestIn, IngestOut, InternalSourceOut
from veille.services import audit

_TAG_RE = re.compile(r"<[^>]{0,2000}>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SPACE_RE = re.compile(r"\s+")
_MAX_FUTURE = timedelta(days=1)


async def enabled_sources(db: AsyncSession) -> list[InternalSourceOut]:
    rows = await db.scalars(
        select(Source)
        .join(VeilleGroup, Source.group_id == VeilleGroup.id)
        .where(Source.enabled.is_(True), VeilleGroup.enabled.is_(True))
        .order_by(Source.id)
    )
    return [InternalSourceOut(id=s.id, url=s.url) for s in rows]


def clean_text(value: str | None, limit: int) -> str:
    if not value:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", value))
    text = _SPACE_RE.sub(" ", _CONTROL_RE.sub("", text)).strip()
    return text[:limit]


def clean_link(value: str | None) -> str | None:
    if not value:
        return None
    link = value.strip()
    if len(link) > 2048 or _CONTROL_RE.search(link) or any(c.isspace() for c in link):
        return None
    parts = urlsplit(link)
    # Bloque javascript:, data:, etc. : le lien sera rendu dans un <a href>.
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    return link


def parse_date(value: str | None, now: datetime) -> datetime:
    parsed: datetime | None = None
    if value:
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError, IndexError):
                parsed = None
    if parsed is None:
        return now
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    # Une date dans le futur épinglerait l'article en tête de liste indéfiniment.
    return now if parsed > now + _MAX_FUTURE else parsed


def _prepare(
    items: list[IngestArticleIn], source_id: object, now: datetime
) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    rejected = 0
    for item in items:
        link = clean_link(item.link)
        if link is None:
            rejected += 1
            continue
        if link in seen:
            continue
        seen.add(link)
        rows.append(
            {
                "source_id": source_id,
                "link": link,
                "title": clean_text(item.title, 500) or link[:500],
                "snippet": clean_text(item.snippet, 1000),
                "published_at": parse_date(item.published_at, now),
            }
        )
    return rows, rejected


async def ingest(
    db: AsyncSession, payload: IngestIn, *, ip: str | None, now: datetime
) -> IngestOut:
    source = await db.get(Source, payload.source_id, with_for_update=True)
    if source is None:
        raise not_found("Source")

    source.last_fetch_at = now
    if not payload.ok:
        source.last_status = "error"
        source.last_error = clean_text(payload.error, 500) or "Erreur inconnue"
        source.consecutive_failures += 1
        audit.record(db, action="ingest.failed", service=True, target=str(source.id), ip=ip)
        await db.commit()
        return IngestOut(inserted=0, rejected=0)

    rows, rejected = _prepare(payload.articles, source.id, now)
    inserted = 0
    if rows:
        # L'unicité (source_id, link) en base est le vrai mécanisme de dédoublonnage :
        # rejouer une exécution n8n est sans effet.
        stmt = (
            pg_insert(Article)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_articles_source_link")
            .returning(Article.id)
        )
        inserted = len((await db.execute(stmt)).all())

    source.last_status = "ok"
    source.last_error = None
    source.consecutive_failures = 0
    await db.commit()
    return IngestOut(inserted=inserted, rejected=rejected)

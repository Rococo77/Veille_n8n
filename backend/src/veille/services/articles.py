import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from veille.errors import DomainError
from veille.models import Article, Source, Theme, VeilleGroup
from veille.schemas import (
    ArticleGroupRef,
    ArticleOut,
    ArticlePage,
    ArticleSourceRef,
    ThemeOut,
)


@dataclass(frozen=True)
class ArticleFilters:
    group_id: uuid.UUID | None = None
    veille_type: str | None = None
    theme_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    q: str | None = None


def encode_cursor(published_at: datetime, article_id: int) -> str:
    raw = json.dumps([published_at.isoformat(), article_id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        published, article_id = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(published), int(article_id)
    except (binascii.Error, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise DomainError(422, "Curseur invalide", None, "invalid-cursor") from exc


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_articles(
    db: AsyncSession, filters: ArticleFilters, *, cursor: str | None, limit: int
) -> ArticlePage:
    stmt = (
        select(Article, Source, VeilleGroup, Theme)
        .join(Source, Article.source_id == Source.id)
        .join(VeilleGroup, Source.group_id == VeilleGroup.id)
        .join(Theme, VeilleGroup.theme_id == Theme.id)
    )
    if filters.group_id is not None:
        stmt = stmt.where(VeilleGroup.id == filters.group_id)
    if filters.veille_type is not None:
        stmt = stmt.where(VeilleGroup.veille_type == filters.veille_type)
    if filters.theme_id is not None:
        stmt = stmt.where(VeilleGroup.theme_id == filters.theme_id)
    if filters.source_id is not None:
        stmt = stmt.where(Article.source_id == filters.source_id)
    if filters.q:
        stmt = stmt.where(Article.title.ilike(f"%{_escape_like(filters.q)}%", escape="\\"))
    if cursor:
        published_at, article_id = decode_cursor(cursor)
        # Pagination par curseur : stable pendant qu'n8n insère, et pas d'OFFSET qui se dégrade.
        stmt = stmt.where(tuple_(Article.published_at, Article.id) < (published_at, article_id))

    stmt = stmt.order_by(Article.published_at.desc(), Article.id.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).all()

    items = [
        ArticleOut(
            id=a.id,
            link=a.link,
            title=a.title,
            snippet=a.snippet,
            published_at=a.published_at,
            source=ArticleSourceRef(id=s.id, name=s.name),
            group=ArticleGroupRef(id=g.id, name=g.name, veille_type=g.veille_type),  # type: ignore[arg-type]
            theme=ThemeOut.model_validate(t),
        )
        for a, s, g, t in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1][0]
        next_cursor = encode_cursor(last.published_at, last.id)
    return ArticlePage(items=items, next_cursor=next_cursor)

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from veille.deps import Db, Viewer
from veille.schemas import ArticlePage, VeilleType
from veille.services import articles
from veille.services.articles import ArticleFilters

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=ArticlePage)
async def list_articles(
    _: Viewer,
    db: Db,
    group_id: Annotated[uuid.UUID | None, Query()] = None,
    veille_type: Annotated[VeilleType | None, Query()] = None,
    theme_id: Annotated[uuid.UUID | None, Query()] = None,
    source_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ArticlePage:
    filters = ArticleFilters(
        group_id=group_id, veille_type=veille_type, theme_id=theme_id, source_id=source_id, q=q
    )
    return await articles.list_articles(db, filters, cursor=cursor, limit=limit)

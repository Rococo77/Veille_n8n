import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from veille.deps import ClientIp, Db, Editor, UrlResolver, Viewer
from veille.schemas import (
    GroupDetailOut,
    GroupIn,
    GroupOut,
    GroupPatch,
    SourceIn,
    SourceOut,
    SourcePatch,
    ThemeIn,
    ThemeOut,
    ThemePatch,
    VeilleType,
)
from veille.services import catalog

router = APIRouter(prefix="/api", tags=["catalogue"])


@router.get("/themes", response_model=list[ThemeOut])
async def list_themes(_: Viewer, db: Db) -> list[ThemeOut]:
    return await catalog.list_themes(db)


@router.post("/themes", response_model=ThemeOut, status_code=status.HTTP_201_CREATED)
async def create_theme(data: ThemeIn, ctx: Editor, db: Db, ip: ClientIp) -> ThemeOut:
    return await catalog.create_theme(db, data, ctx.user, ip)


@router.patch("/themes/{theme_id}", response_model=ThemeOut)
async def update_theme(
    theme_id: uuid.UUID, data: ThemePatch, ctx: Editor, db: Db, ip: ClientIp
) -> ThemeOut:
    return await catalog.update_theme(db, theme_id, data, ctx.user, ip)


@router.delete("/themes/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_theme(theme_id: uuid.UUID, ctx: Editor, db: Db, ip: ClientIp) -> None:
    await catalog.delete_theme(db, theme_id, ctx.user, ip)


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(
    _: Viewer,
    db: Db,
    veille_type: Annotated[VeilleType | None, Query()] = None,
    theme_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[GroupOut]:
    return await catalog.list_groups(db, veille_type=veille_type, theme_id=theme_id)


@router.post("/groups", response_model=GroupDetailOut, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupIn, ctx: Editor, db: Db, ip: ClientIp) -> GroupDetailOut:
    return await catalog.create_group(db, data, ctx.user, ip)


@router.get("/groups/{group_id}", response_model=GroupDetailOut)
async def get_group(group_id: uuid.UUID, _: Viewer, db: Db) -> GroupDetailOut:
    return await catalog.get_group(db, group_id)


@router.patch("/groups/{group_id}", response_model=GroupDetailOut)
async def update_group(
    group_id: uuid.UUID, data: GroupPatch, ctx: Editor, db: Db, ip: ClientIp
) -> GroupDetailOut:
    return await catalog.update_group(db, group_id, data, ctx.user, ip)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, ctx: Editor, db: Db, ip: ClientIp) -> None:
    await catalog.delete_group(db, group_id, ctx.user, ip)


@router.post(
    "/groups/{group_id}/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED
)
async def create_source(
    group_id: uuid.UUID,
    data: SourceIn,
    ctx: Editor,
    db: Db,
    resolver: UrlResolver,
    ip: ClientIp,
) -> SourceOut:
    return await catalog.create_source(db, group_id, data, resolver, ctx.user, ip)


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: uuid.UUID,
    data: SourcePatch,
    ctx: Editor,
    db: Db,
    resolver: UrlResolver,
    ip: ClientIp,
) -> SourceOut:
    return await catalog.update_source(db, source_id, data, resolver, ctx.user, ip)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: uuid.UUID, ctx: Editor, db: Db, ip: ClientIp) -> None:
    await catalog.delete_source(db, source_id, ctx.user, ip)

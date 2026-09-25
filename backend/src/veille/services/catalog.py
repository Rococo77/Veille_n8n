import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from veille.errors import DomainError, conflict, constraint_name, not_found
from veille.models import Source, Theme, User, VeilleGroup
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
)
from veille.services import audit
from veille.url_policy import Resolver, normalize_source_url

_CONSTRAINT_ERRORS: dict[str, DomainError] = {
    "uq_themes_name": conflict("Un thème porte déjà ce nom."),
    "uq_veille_groups_name": conflict("Un groupe porte déjà ce nom."),
    "uq_sources_group_url": conflict("Cette URL existe déjà dans ce groupe."),
    "fk_veille_groups_theme": DomainError(
        409, "Conflit", "Thème inexistant ou encore utilisé par un groupe.", "theme-in-use"
    ),
}


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        mapped = _CONSTRAINT_ERRORS.get(constraint_name(exc) or "")
        if mapped is None:
            raise
        raise mapped from exc


def _changes(patch: GroupPatch | SourcePatch | ThemePatch) -> dict[str, Any]:
    # exclude_none : un null explicite sur une colonne NOT NULL = "pas de changement".
    return patch.model_dump(exclude_unset=True, exclude_none=True)


# --- Thèmes -----------------------------------------------------------------------------


async def list_themes(db: AsyncSession) -> list[ThemeOut]:
    rows = await db.scalars(select(Theme).order_by(Theme.name))
    return [ThemeOut.model_validate(t) for t in rows]


async def create_theme(db: AsyncSession, data: ThemeIn, actor: User, ip: str | None) -> ThemeOut:
    theme = Theme(name=data.name, color=data.color)
    db.add(theme)
    await db.flush()
    audit.record(db, action="theme.created", actor=actor, target=str(theme.id), ip=ip)
    await _commit(db)
    return ThemeOut.model_validate(theme)


async def update_theme(
    db: AsyncSession, theme_id: uuid.UUID, patch: ThemePatch, actor: User, ip: str | None
) -> ThemeOut:
    theme = await db.get(Theme, theme_id)
    if theme is None:
        raise not_found("Thème")
    for field, value in _changes(patch).items():
        setattr(theme, field, value)
    audit.record(db, action="theme.updated", actor=actor, target=str(theme_id), ip=ip)
    await _commit(db)
    return ThemeOut.model_validate(theme)


async def delete_theme(db: AsyncSession, theme_id: uuid.UUID, actor: User, ip: str | None) -> None:
    theme = await db.get(Theme, theme_id)
    if theme is None:
        raise not_found("Thème")
    await db.delete(theme)
    audit.record(db, action="theme.deleted", actor=actor, target=str(theme_id), ip=ip)
    await _commit(db)


# --- Groupes ----------------------------------------------------------------------------


def _group_out(group: VeilleGroup, theme: Theme, count: int, failing: int) -> GroupOut:
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        veille_type=group.veille_type,  # type: ignore[arg-type]
        theme=ThemeOut.model_validate(theme),
        enabled=group.enabled,
        source_count=count,
        failing_source_count=failing,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


async def list_groups(
    db: AsyncSession, *, veille_type: str | None = None, theme_id: uuid.UUID | None = None
) -> list[GroupOut]:
    # Une seule requête agrégée : pas de comptage par groupe (N+1).
    failing = func.count(Source.id).filter(Source.last_status == "error")
    stmt = (
        select(VeilleGroup, Theme, func.count(Source.id), failing)
        .join(Theme, VeilleGroup.theme_id == Theme.id)
        .outerjoin(Source, Source.group_id == VeilleGroup.id)
        .group_by(VeilleGroup.id, Theme.id)
        .order_by(VeilleGroup.name)
    )
    if veille_type is not None:
        stmt = stmt.where(VeilleGroup.veille_type == veille_type)
    if theme_id is not None:
        stmt = stmt.where(VeilleGroup.theme_id == theme_id)
    rows = (await db.execute(stmt)).all()
    return [_group_out(g, t, c, f) for g, t, c, f in rows]


async def _load_group(db: AsyncSession, group_id: uuid.UUID) -> VeilleGroup:
    group = await db.scalar(
        select(VeilleGroup)
        .options(joinedload(VeilleGroup.theme), selectinload(VeilleGroup.sources))
        .where(VeilleGroup.id == group_id)
        .execution_options(populate_existing=True)
    )
    if group is None:
        raise not_found("Groupe")
    return group


async def get_group(db: AsyncSession, group_id: uuid.UUID) -> GroupDetailOut:
    group = await _load_group(db, group_id)
    base = _group_out(
        group,
        group.theme,
        len(group.sources),
        sum(1 for s in group.sources if s.last_status == "error"),
    )
    return GroupDetailOut(
        **base.model_dump(), sources=[SourceOut.model_validate(s) for s in group.sources]
    )


async def create_group(
    db: AsyncSession, data: GroupIn, actor: User, ip: str | None
) -> GroupDetailOut:
    group = VeilleGroup(**data.model_dump())
    db.add(group)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _CONSTRAINT_ERRORS.get(
            constraint_name(exc) or "", conflict("Groupe invalide.")
        ) from exc
    audit.record(db, action="group.created", actor=actor, target=str(group.id), ip=ip)
    await _commit(db)
    return await get_group(db, group.id)


async def update_group(
    db: AsyncSession, group_id: uuid.UUID, patch: GroupPatch, actor: User, ip: str | None
) -> GroupDetailOut:
    group = await db.get(VeilleGroup, group_id)
    if group is None:
        raise not_found("Groupe")
    changes = _changes(patch)
    for field, value in changes.items():
        setattr(group, field, value)
    audit.record(
        db,
        action="group.updated",
        actor=actor,
        target=str(group_id),
        ip=ip,
        details={"fields": sorted(changes)},
    )
    await _commit(db)
    return await get_group(db, group_id)


async def delete_group(db: AsyncSession, group_id: uuid.UUID, actor: User, ip: str | None) -> None:
    group = await db.get(VeilleGroup, group_id)
    if group is None:
        raise not_found("Groupe")
    await db.delete(group)
    audit.record(
        db,
        action="group.deleted",
        actor=actor,
        target=str(group_id),
        ip=ip,
        details={"name": group.name},
    )
    await _commit(db)


# --- Sources ----------------------------------------------------------------------------


async def create_source(
    db: AsyncSession,
    group_id: uuid.UUID,
    data: SourceIn,
    resolver: Resolver,
    actor: User,
    ip: str | None,
) -> SourceOut:
    if await db.get(VeilleGroup, group_id) is None:
        raise not_found("Groupe")
    url = await normalize_source_url(data.url, resolver)
    source = Source(group_id=group_id, name=data.name, url=url, enabled=data.enabled)
    db.add(source)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _CONSTRAINT_ERRORS.get(
            constraint_name(exc) or "", conflict("Source invalide.")
        ) from exc
    audit.record(
        db,
        action="source.created",
        actor=actor,
        target=str(source.id),
        ip=ip,
        details={"group_id": str(group_id), "url": url},
    )
    await _commit(db)
    await db.refresh(source)
    return SourceOut.model_validate(source)


async def update_source(
    db: AsyncSession,
    source_id: uuid.UUID,
    patch: SourcePatch,
    resolver: Resolver,
    actor: User,
    ip: str | None,
) -> SourceOut:
    source = await db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    changes = _changes(patch)
    if "url" in changes:
        changes["url"] = await normalize_source_url(changes["url"], resolver)
        if changes["url"] != source.url:
            # L'état de santé concernait l'ancienne URL.
            source.last_status = None
            source.last_error = None
            source.consecutive_failures = 0
    for field, value in changes.items():
        setattr(source, field, value)
    audit.record(
        db,
        action="source.updated",
        actor=actor,
        target=str(source_id),
        ip=ip,
        details={"fields": sorted(changes)},
    )
    await _commit(db)
    await db.refresh(source)
    return SourceOut.model_validate(source)


async def delete_source(
    db: AsyncSession, source_id: uuid.UUID, actor: User, ip: str | None
) -> None:
    source = await db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    await db.delete(source)
    audit.record(
        db,
        action="source.deleted",
        actor=actor,
        target=str(source_id),
        ip=ip,
        details={"url": source.url},
    )
    await _commit(db)

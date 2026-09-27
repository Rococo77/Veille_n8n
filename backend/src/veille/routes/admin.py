import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from veille.db import utcnow
from veille.deps import Admin, AppMailer, AppSettings, ClientIp, Db
from veille.schemas import AuditOut, InvitationOut, UserInviteIn, UserOut, UserPatch
from veille.services import invitations, users

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(_: Admin, db: Db) -> list[UserOut]:
    return await users.list_users(db)


@router.post("/users", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def invite_user(
    data: UserInviteIn,
    ctx: Admin,
    db: Db,
    settings: AppSettings,
    mailer: AppMailer,
    ip: ClientIp,
) -> InvitationOut:
    return await invitations.invite_user(db, data, ctx.user, settings, mailer, ip=ip, now=utcnow())


@router.post("/users/{user_id}/invitation", response_model=InvitationOut)
async def reinvite(
    user_id: uuid.UUID,
    ctx: Admin,
    db: Db,
    settings: AppSettings,
    mailer: AppMailer,
    ip: ClientIp,
) -> InvitationOut:
    return await invitations.reinvite(db, user_id, ctx.user, settings, mailer, ip=ip, now=utcnow())


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, data: UserPatch, ctx: Admin, db: Db, ip: ClientIp
) -> UserOut:
    return await users.update_user(db, user_id, data, ctx.user, ip)


@router.post("/users/{user_id}/reset-mfa", response_model=UserOut)
async def reset_mfa(user_id: uuid.UUID, ctx: Admin, db: Db, ip: ClientIp) -> UserOut:
    return await users.reset_mfa(db, user_id, ctx.user, ip)


@router.post("/users/{user_id}/unlock", response_model=UserOut)
async def unlock(user_id: uuid.UUID, ctx: Admin, db: Db, ip: ClientIp) -> UserOut:
    return await users.unlock(db, user_id, ctx.user, ip)


@router.get("/audit", response_model=list[AuditOut])
async def list_audit(
    _: Admin, db: Db, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[AuditOut]:
    return await users.list_audit(db, limit)

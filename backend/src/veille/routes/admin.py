import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from veille.deps import Admin, ClientIp, Db
from veille.schemas import AuditOut, UserIn, UserOut, UserPatch
from veille.services import users

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(_: Admin, db: Db) -> list[UserOut]:
    return await users.list_users(db)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserIn, ctx: Admin, db: Db, ip: ClientIp) -> UserOut:
    return await users.create_user(db, data, ctx.user, ip)


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

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(url: str, *, pool_size: int = 3, max_overflow: int = 2) -> AsyncEngine:
    return create_async_engine(
        url, pool_pre_ping=True, pool_size=pool_size, max_overflow=max_overflow
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(UTC)

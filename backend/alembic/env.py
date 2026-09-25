import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from veille.models import Base

target_metadata = Base.metadata


def _url() -> str:
    url = os.environ.get("VEILLE_DATABASE_URL")
    if not url:
        raise RuntimeError("VEILLE_DATABASE_URL est requis pour les migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

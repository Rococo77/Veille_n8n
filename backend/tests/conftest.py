import hashlib
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from veille.config import Settings
from veille.db import utcnow
from veille.main import create_app
from veille.models import User
from veille.security import TotpCipher, hash_password
from veille.services import sessions

DB_URL = os.environ.get(
    "VEILLE_TEST_DATABASE_URL", "postgresql+asyncpg://veille:veille@127.0.0.1:55432/veille_test"
)
SERVICE_TOKEN = "service-token-for-tests-only"
PASSWORD = "correct horse battery staple"
BACKEND = Path(__file__).resolve().parents[1]

# Résolution DNS simulée : les tests ne dépendent pas du réseau.
FAKE_DNS = {
    "feeds.example.org": ["93.184.216.34"],
    "rebind.example.org": ["93.184.216.34", "10.0.0.5"],
    "internal.example.org": ["192.168.1.10"],
}


async def fake_resolver(host: str) -> list[str]:
    if host not in FAKE_DNS:
        raise OSError("NXDOMAIN")
    return FAKE_DNS[host]


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        database_url=DB_URL,
        totp_encryption_key=Fernet.generate_key().decode(),  # type: ignore[arg-type]
        internal_token_sha256=hashlib.sha256(SERVICE_TOKEN.encode()).hexdigest(),
        cookie_secure=True,
    )


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    # Les tests tournent sur le schéma produit par la migration, pas sur create_all :
    # c'est la migration qui part en prod.
    env = {**os.environ, "VEILLE_DATABASE_URL": DB_URL}
    alembic = [sys.executable, "-m", "alembic"]
    subprocess.run(
        [*alembic, "downgrade", "base"], cwd=BACKEND, env=env, check=True, capture_output=True
    )
    subprocess.run(
        [*alembic, "upgrade", "head"], cwd=BACKEND, env=env, check=True, capture_output=True
    )


@pytest.fixture(scope="session")
async def engine():  # type: ignore[no-untyped-def]
    eng = create_async_engine(DB_URL)
    yield eng
    await eng.dispose()


@pytest.fixture(autouse=True)
async def clean(engine) -> None:  # type: ignore[no-untyped-def]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE articles, sources, veille_groups, themes, user_sessions,"
                " audit_events, users RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
async def app(settings: Settings):  # type: ignore[no-untyped-def]
    application = create_app(settings, resolver=fake_resolver)
    async with application.router.lifespan_context(application):
        yield application


def make_client(app) -> AsyncClient:  # type: ignore[no-untyped-def]
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver")


@pytest.fixture
async def anon(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async with make_client(app) as client:
        yield client


@dataclass
class Actor:
    user: User
    client: AsyncClient


async def create_user(db: AsyncSession, email: str, role: str, *, active: bool = True) -> User:
    user = User(email=email, password_hash=hash_password(PASSWORD), role=role, is_active=active)
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def login_as(app, db: AsyncSession, settings: Settings):  # type: ignore[no-untyped-def]
    """Ouvre directement une session MFA validée (le parcours complet a son propre test)."""
    clients: list[AsyncClient] = []

    async def _login(role: str, email: str | None = None) -> Actor:
        user = await create_user(db, email or f"{role}@example.org", role)
        issued = sessions.issue(
            db, user, mfa_verified=True, settings=settings, ip=None, user_agent=None, now=utcnow()
        )
        await db.commit()
        client = make_client(app)
        client.cookies.set(settings.session_cookie_name, issued.token)
        client.headers["X-CSRF-Token"] = issued.csrf
        clients.append(client)
        return Actor(user, client)

    yield _login
    for c in clients:
        await c.aclose()


@pytest.fixture
def cipher(settings: Settings) -> TotpCipher:
    return TotpCipher(settings.totp_encryption_key.get_secret_value())


def service_headers(token: str = SERVICE_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from veille.config import Settings, get_settings
from veille.db import build_engine, build_sessionmaker
from veille.errors import DomainError, install_error_handlers, problem_response
from veille.routes import admin, articles, auth, catalog, internal
from veille.security import TotpCipher
from veille.url_policy import Resolver, system_resolver

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def create_app(settings: Settings | None = None, resolver: Resolver | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        app.state.settings = settings
        app.state.sessionmaker = build_sessionmaker(engine)
        app.state.totp_cipher = TotpCipher(settings.totp_encryption_key.get_secret_value())
        app.state.resolver = resolver or system_resolver
        try:
            yield
        finally:
            await engine.dispose()

    docs = settings.enable_docs
    app = FastAPI(
        title="Veille",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def harden(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Un formulaire HTML cross-site ne peut pas envoyer d'application/json sans preflight
        # CORS, et aucun CORS n'est ouvert : barrière anti-CSRF indépendante du jeton.
        has_body = (
            request.headers.get("content-length", "0") != "0"
            or "transfer-encoding" in request.headers
        )
        if request.method in _UNSAFE_METHODS and has_body:
            content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type != "application/json":
                err = DomainError(
                    415, "Type de contenu refusé", "application/json attendu.", "media"
                )
                response: Response = problem_response(err.status, err.title, err.detail, err.code)
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/api/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (auth, catalog, articles, admin, internal):
        app.include_router(module.router)
    return app


def app_factory() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app()

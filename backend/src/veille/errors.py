import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from veille.security import HasherBusyError

PROBLEM_MEDIA_TYPE = "application/problem+json"
logger = logging.getLogger("veille")


class DomainError(Exception):
    """Erreur métier traduite en Problem Details (RFC 9457, ex-7807)."""

    def __init__(self, status: int, title: str, detail: str | None = None, code: str = "") -> None:
        super().__init__(detail or title)
        self.status = status
        self.title = title
        self.detail = detail
        self.code = code or title.lower().replace(" ", "-")


def not_found(what: str) -> DomainError:
    return DomainError(404, "Ressource introuvable", f"{what} introuvable", "not-found")


def conflict(detail: str) -> DomainError:
    return DomainError(409, "Conflit", detail, "conflict")


def unauthorized(detail: str = "Authentification requise") -> DomainError:
    return DomainError(401, "Non authentifié", detail, "unauthenticated")


def forbidden(detail: str = "Droits insuffisants") -> DomainError:
    return DomainError(403, "Interdit", detail, "forbidden")


def constraint_name(exc: IntegrityError) -> str | None:
    # asyncpg expose le nom de contrainte sur l'exception d'origine, enveloppée par le dialecte.
    origin = getattr(exc.orig, "__cause__", None) or exc.orig
    return getattr(origin, "constraint_name", None)


def problem_response(
    status: int, title: str, detail: str | None, code: str, **extra: Any
) -> JSONResponse:
    body: dict[str, Any] = {"type": f"urn:veille:problem:{code}", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return problem_response(exc.status, exc.title, exc.detail, exc.code)

    @app.exception_handler(HasherBusyError)
    async def _busy(_: Request, __: HasherBusyError) -> JSONResponse:
        response = problem_response(
            503, "Serveur occupé", "Réessayez dans quelques secondes.", "busy"
        )
        response.headers["Retry-After"] = "5"
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # On ne renvoie jamais la valeur reçue : elle peut contenir un mot de passe.
        errors = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return problem_response(422, "Requête invalide", None, "validation", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(
            exc.status_code, detail or "Erreur", None, f"http-{exc.status_code}"
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return problem_response(500, "Erreur interne", None, "internal")

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from veille.models import AuditEvent, User


def record(
    db: AsyncSession,
    *,
    action: str,
    actor: User | None = None,
    service: bool = False,
    target: str | None = None,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Ajoute l'événement à la transaction en cours : il est commité avec l'action auditée,
    ou pas du tout."""
    kind = "service" if service else ("user" if actor else "anonymous")
    db.add(
        AuditEvent(
            actor_kind=kind,
            actor_user_id=actor.id if actor else None,
            action=action,
            target=(target or "")[:255] or None,
            ip=ip,
            details=details or {},
        )
    )

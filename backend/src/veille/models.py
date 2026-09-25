import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

VEILLE_TYPES: tuple[str, ...] = (
    "technologique",
    "concurrentielle",
    "reglementaire",
    "securite",
    "marche",
    "autre",
)
ROLES: tuple[str, ...] = ("viewer", "editor", "admin")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("role", ROLES), name="ck_users_role"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"), default=True)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)
    totp_confirmed: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)
    failed_logins: Mapped[int] = mapped_column(server_default=text("0"), default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    # Seuls les hash SHA-256 sont stockés : une fuite de la table ne permet pas de rejouer.
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mfa_verified: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    mfa_attempts: Mapped[int] = mapped_column(server_default=text("0"), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(lazy="raise")


class Theme(Timestamps, Base):
    __tablename__ = "themes"
    __table_args__ = (
        UniqueConstraint("name", name="uq_themes_name"),
        CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="ck_themes_color"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(7))


class VeilleGroup(Timestamps, Base):
    __tablename__ = "veille_groups"
    __table_args__ = (
        UniqueConstraint("name", name="uq_veille_groups_name"),
        CheckConstraint(_in("veille_type", VEILLE_TYPES), name="ck_veille_groups_type"),
        Index("ix_veille_groups_theme_id", "theme_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, server_default=text("''"), default="")
    veille_type: Mapped[str] = mapped_column(String(32))
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("themes.id", ondelete="RESTRICT", name="fk_veille_groups_theme")
    )
    enabled: Mapped[bool] = mapped_column(server_default=text("true"), default=True)

    theme: Mapped[Theme] = relationship(lazy="raise")
    # passive_deletes : la suppression en cascade est faite par la FK ON DELETE CASCADE.
    # Sans ça, l'ORM tente de passer group_id à NULL sur les sources avant le DELETE.
    sources: Mapped[list["Source"]] = relationship(
        lazy="raise",
        back_populates="group",
        order_by="Source.name",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Source(Timestamps, Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("group_id", "url", name="uq_sources_group_url"),
        CheckConstraint(
            "last_status IS NULL OR last_status IN ('ok', 'error')", name="ck_sources_status"
        ),
        CheckConstraint("url ~ '^https?://'", name="ck_sources_url_scheme"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("veille_groups.id", ondelete="CASCADE", name="fk_sources_group")
    )
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(server_default=text("true"), default=True)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(8))
    last_error: Mapped[str | None] = mapped_column(String(500))
    consecutive_failures: Mapped[int] = mapped_column(server_default=text("0"), default=0)

    group: Mapped[VeilleGroup] = relationship(lazy="raise", back_populates="sources")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source_id", "link", name="uq_articles_source_link"),
        CheckConstraint("link ~ '^https?://'", name="ck_articles_link_scheme"),
        Index("ix_articles_published", text("published_at DESC"), text("id DESC")),
        Index("ix_articles_source_published", "source_id", text("published_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE", name="fk_articles_source")
    )
    link: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(500))
    snippet: Mapped[str] = mapped_column(String(1000), server_default=text("''"), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_kind IN ('user', 'service', 'anonymous')", name="ck_audit_actor_kind"
        ),
        Index("ix_audit_events_at", text("at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_audit_actor")
    )
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(45))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), default=dict
    )

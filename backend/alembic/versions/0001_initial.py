"""Schéma initial : utilisateurs, sessions, thèmes, groupes, sources, articles, audit.

Revision ID: 0001
Revises:
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID_PK = dict(primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), **_UUID_PK),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("totp_secret_enc", sa.Text(), nullable=True),
        sa.Column("totp_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("totp_last_step", sa.BigInteger(), nullable=True),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("role IN ('viewer', 'editor', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        sa.CheckConstraint("failed_logins >= 0", name="ck_users_failed_logins"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), **_UUID_PK),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("csrf_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_sessions_user"
        ),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    # Purge des sessions expirées (voir README) : l'index évite un seq scan.
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "themes",
        sa.Column("id", sa.Uuid(), **_UUID_PK),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_themes_name"),
        sa.CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="ck_themes_color"),
    )

    op.create_table(
        "veille_groups",
        sa.Column("id", sa.Uuid(), **_UUID_PK),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("veille_type", sa.String(32), nullable=False),
        sa.Column("theme_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["theme_id"], ["themes.id"], ondelete="RESTRICT", name="fk_veille_groups_theme"
        ),
        sa.UniqueConstraint("name", name="uq_veille_groups_name"),
        sa.CheckConstraint(
            "veille_type IN ('technologique', 'concurrentielle', 'reglementaire', 'securite', 'marche', 'autre')",
            name="ck_veille_groups_type",
        ),
    )
    op.create_index("ix_veille_groups_theme_id", "veille_groups", ["theme_id"])

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), **_UUID_PK),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(8), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column(
            "consecutive_failures", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["group_id"], ["veille_groups.id"], ondelete="CASCADE", name="fk_sources_group"
        ),
        sa.UniqueConstraint("group_id", "url", name="uq_sources_group_url"),
        sa.CheckConstraint(
            "last_status IS NULL OR last_status IN ('ok', 'error')", name="ck_sources_status"
        ),
        sa.CheckConstraint("url ~ '^https?://'", name="ck_sources_url_scheme"),
        sa.CheckConstraint("consecutive_failures >= 0", name="ck_sources_failures"),
    )
    # uq_sources_group_url couvre déjà les recherches par group_id (colonne de tête).

    op.create_table(
        "articles",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("link", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("snippet", sa.String(1000), nullable=False, server_default=sa.text("''")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="CASCADE", name="fk_articles_source"
        ),
        sa.UniqueConstraint("source_id", "link", name="uq_articles_source_link"),
        sa.CheckConstraint("link ~ '^https?://'", name="ck_articles_link_scheme"),
    )
    # Tri principal du fil (keyset sur published_at, id).
    op.create_index(
        "ix_articles_published", "articles", [sa.text("published_at DESC"), sa.text("id DESC")]
    )
    # Filtre par source / groupe tout en gardant l'ordre chronologique.
    op.create_index(
        "ix_articles_source_published", "articles", ["source_id", sa.text("published_at DESC")]
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_kind", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL", name="fk_audit_actor"
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'service', 'anonymous')", name="ck_audit_actor_kind"
        ),
    )
    op.create_index("ix_audit_events_at", "audit_events", [sa.text("at DESC")])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("articles")
    op.drop_table("sources")
    op.drop_table("veille_groups")
    op.drop_table("themes")
    op.drop_table("user_sessions")
    op.drop_table("users")

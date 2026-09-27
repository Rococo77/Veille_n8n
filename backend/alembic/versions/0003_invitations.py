"""Invitations par lien à usage unique ; mot de passe absent tant qu'elle n'est pas acceptée.

Un compte invité n'a pas de mot de passe : l'admin ne le choisit plus et ne le connaît
jamais. Seul le hash SHA-256 du jeton d'invitation est stocké, comme pour les sessions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)

    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_invitations_user"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL", name="fk_invitations_created_by"
        ),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
        # Une seule invitation vivante par compte : en émettre une nouvelle révoque l'ancienne.
        sa.UniqueConstraint("user_id", name="uq_invitations_user"),
        sa.CheckConstraint("expires_at > created_at", name="ck_invitations_expiry"),
    )

    # Même règle que 0002 pour toute nouvelle table : fermée à l'API de données Supabase.
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON TABLE invitations FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("invitations")
    # Un compte encore sans mot de passe ne peut pas revenir au schéma NOT NULL.
    op.execute("DELETE FROM users WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)

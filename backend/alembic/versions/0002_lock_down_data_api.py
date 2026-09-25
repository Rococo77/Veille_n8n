"""Ferme l'API de données Supabase sur les tables du site.

Supabase expose automatiquement le schéma public via PostgREST aux rôles `anon` et
`authenticated`. Sans ceci, la clé publique du projet suffirait à lire users.password_hash
ou user_sessions. RLS activé sans aucune policy = refus total pour ces rôles ; le rôle
propriétaire utilisé par le backend n'est pas concerné (pas de FORCE ROW LEVEL SECURITY).
Sans effet de bord sur un Postgres classique où ces rôles n'existent pas.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "users",
    "user_sessions",
    "themes",
    "veille_groups",
    "sources",
    "articles",
    "audit_events",
    "alembic_version",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
              EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

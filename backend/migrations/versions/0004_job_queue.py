# SPDX-License-Identifier: AGPL-3.0-or-later
"""The job queue (F04, ADR-0022) and the purge of expired sessions (ADR-0029).

- Procrastinate's schema, as published by the pinned version (3.10), owned by the schema owner.
  Its tables hold job arguments (identifiers only) and no business data: they stay outside
  row-level security, like alembic_version (tests/platform/test_accounts_schema.py).
- `purge_expired_sessions`, an owner function run by a periodic job: it deletes the sessions
  past their idle timeout or lifetime, and the throttle counters past their window.

Revision: 0004
Previous: 0003
"""

import procrastinate.schema
from alembic import op

from otlet.platform import rls

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _raw(sql: str) -> None:
    """Runs `sql` on the psycopg connection itself, without parameters: psycopg then reads
    no placeholder in it, and the "%" and "::" of the SQL stay as they are."""
    op.get_bind().connection.driver_connection.execute(sql)  # type: ignore[union-attr]


PURGE = "purge_expired_sessions(interval, interval, interval)"


def upgrade() -> None:
    _raw(procrastinate.schema.SchemaManager.get_schema())
    op.execute(
        """
        CREATE FUNCTION purge_expired_sessions(
            p_idle interval, p_lifetime interval, p_throttle_window interval)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$
        DECLARE purged integer;
        BEGIN
            DELETE FROM user_sessions
            WHERE last_seen_at < now() - p_idle OR created_at < now() - p_lifetime;
            GET DIAGNOSTICS purged = ROW_COUNT;
            DELETE FROM auth_throttle WHERE window_start < now() - p_throttle_window;
            RETURN purged;
        END $$
        """
    )
    op.execute(rls.grant_to_app(PURGE))


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {PURGE}")
    # Procrastinate publishes no uninstall script: drop every object it created, by prefix.
    _raw(
        """
        DO $$
        DECLARE object record;
        BEGIN
            FOR object IN SELECT tablename FROM pg_tables
                          WHERE schemaname = 'public' AND tablename LIKE 'procrastinate\\_%'
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', object.tablename);
            END LOOP;
            FOR object IN SELECT p.oid::regprocedure AS signature FROM pg_proc AS p
                          JOIN pg_namespace AS n ON n.oid = p.pronamespace
                          WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate\\_%'
            LOOP
                EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', object.signature);
            END LOOP;
            FOR object IN SELECT t.typname FROM pg_type AS t
                          JOIN pg_namespace AS n ON n.oid = t.typnamespace
                          WHERE n.nspname = 'public' AND t.typname LIKE 'procrastinate\\_%'
                            AND t.typtype IN ('e', 'c')
            LOOP
                EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', object.typname);
            END LOOP;
        END $$
        """
    )

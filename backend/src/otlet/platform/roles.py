# SPDX-License-Identifier: AGPL-3.0-or-later
"""Database roles of M-12: the schema owner, the migration role and the application role are
distinct. Provisioning runs once per database with a superuser connection, before migrations.

- `otlet_owner` (no login) owns the schema and every table.
- `otlet_migrator` (login) is a member of `otlet_owner`; migrations run under `SET ROLE
  otlet_owner`, so what they create belongs to the owner.
- `otlet_app` (login) reads and writes rows only: it cannot create objects, does not own any
  table, and cannot bypass row-level security.
"""

import psycopg
from psycopg import sql

OWNER = "otlet_owner"
MIGRATOR = "otlet_migrator"
APP = "otlet_app"
EXTENSIONS = ("vector", "pg_trgm", "unaccent")

_ROLE_OPTIONS = "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"


def _ensure_role(cursor: psycopg.Cursor[object], name: str) -> None:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    if cursor.fetchone() is None:
        cursor.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(name)))


def provision(admin_url: str, migrator_password: str, app_password: str) -> None:
    """Create or update the three roles, the extensions and the privileges of the database
    named in `admin_url` (a superuser connection, libpq form `postgresql://…`). Idempotent."""
    with psycopg.connect(admin_url, autocommit=True) as connection, connection.cursor() as cursor:
        database = sql.Identifier(connection.info.dbname)
        owner, migrator, app = (sql.Identifier(name) for name in (OWNER, MIGRATOR, APP))
        options = sql.SQL(_ROLE_OPTIONS)

        for name in (OWNER, MIGRATOR, APP):
            _ensure_role(cursor, name)
        cursor.execute(sql.SQL("ALTER ROLE {} NOLOGIN {}").format(owner, options))
        cursor.execute(
            sql.SQL("ALTER ROLE {} LOGIN {} PASSWORD {}").format(
                migrator, options, sql.Literal(migrator_password)
            )
        )
        cursor.execute(
            sql.SQL("ALTER ROLE {} LOGIN NOINHERIT {} PASSWORD {}").format(
                app, options, sql.Literal(app_password)
            )
        )
        cursor.execute(sql.SQL("GRANT {} TO {}").format(owner, migrator))

        for extension in EXTENSIONS:
            cursor.execute(
                sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(sql.Identifier(extension))
            )

        cursor.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
        cursor.execute(
            sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}, {}").format(
                database, migrator, app
            )
        )
        cursor.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(owner))
        cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(app))
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public"
                " GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(owner, app)
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public"
                " GRANT USAGE, SELECT ON SEQUENCES TO {}"
            ).format(owner, app)
        )
        # Objects created before provisioning (by the superuser) move to the owner.
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tableowner <> %s",
            (OWNER,),
        )
        for (table,) in cursor.fetchall():
            cursor.execute(
                sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(sql.Identifier(table), owner)
            )
            cursor.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON public.{} TO {}").format(
                    sql.Identifier(table), app
                )
            )
        # Sequences of those tables follow them; free-standing ones move too. The application
        # role uses all of them (the job queue numbers its jobs).
        cursor.execute(
            "SELECT c.relname FROM pg_class AS c JOIN pg_namespace AS n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relkind = 'S' AND NOT EXISTS (SELECT 1"
            " FROM pg_depend AS d WHERE d.objid = c.oid AND d.deptype IN ('a', 'i', 'e'))"
            " AND pg_get_userbyid(c.relowner) <> %s",
            (OWNER,),
        )
        for (sequence,) in cursor.fetchall():
            cursor.execute(
                sql.SQL("ALTER SEQUENCE public.{} OWNER TO {}").format(
                    sql.Identifier(sequence), owner
                )
            )
        cursor.execute(
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(app)
        )
        # Types (the job queue's enums) and every function move to the owner, so that later
        # migrations, run as the owner, can change them.
        cursor.execute(
            "SELECT t.oid::regtype::text FROM pg_type AS t"
            " JOIN pg_namespace AS n ON n.oid = t.typnamespace"
            " WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd', 'c')"
            " AND (t.typtype <> 'c'"
            "  OR (SELECT relkind FROM pg_class WHERE oid = t.typrelid) = 'c')"
            " AND NOT EXISTS (SELECT 1 FROM pg_depend AS d"
            "  WHERE d.objid = t.oid AND d.deptype = 'e')"
            " AND pg_get_userbyid(t.typowner) <> %s",
            (OWNER,),
        )
        for (type_name,) in cursor.fetchall():
            cursor.execute(sql.SQL("ALTER TYPE {} OWNER TO {}").format(sql.SQL(type_name), owner))
        cursor.execute(
            "SELECT p.oid::regprocedure::text, p.prosecdef FROM pg_proc AS p"
            " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
            " AND NOT EXISTS (SELECT 1 FROM pg_depend AS d"
            " WHERE d.objid = p.oid AND d.deptype = 'e')"
        )
        for function, definer in cursor.fetchall():
            cursor.execute(
                sql.SQL("ALTER FUNCTION {} OWNER TO {}").format(sql.SQL(function), owner)
            )
            if not definer:
                continue
            # A SECURITY DEFINER function runs as the owner: only the application role may
            # call it (the sign-in lookup of ADR-0028, the claims of the scheduler).
            cursor.execute(
                sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC").format(sql.SQL(function))
            )
            cursor.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(sql.SQL(function), app)
            )

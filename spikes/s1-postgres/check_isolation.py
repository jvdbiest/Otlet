# SPDX-License-Identifier: AGPL-3.0-or-later
"""S1, criteria C4 and C5 on the measured data set (docs/spikes/S1.md §3.3).

    python check_isolation.py --app-url … --admin-url …

C4: with the application role and no workspace context, every business table returns zero
rows; with the context of the measured workspace, exactly that workspace's rows.
C5: the application role is not superuser, cannot bypass RLS, owns no table, cannot create one.
Writes results/isolation-<time>.json; exits 1 if a check fails.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import sqlalchemy as sa

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "bench"))

from bench import write_result  # noqa: E402

from otlet.platform import database  # noqa: E402

TABLES = ("workspaces", "sources", "items", "passages", "articles", "article_sources")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-url", required=True)
    parser.add_argument("--admin-url", required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE / "data" / "manifest.json").read_text(encoding="utf-8"))
    workspace = uuid.UUID(manifest["measured_workspace"])
    app = database.create_engine(args.app_url)
    admin = database.create_engine(args.admin_url)
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: object) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        print(("ok: " if ok else "FAIL: ") + name)

    for table in TABLES:
        key = "id" if table == "workspaces" else "workspace_id"
        with app.connect() as connection:
            without = connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()  # noqa: S608
        with database.workspace_transaction(app, workspace) as connection:
            within = connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()  # noqa: S608
        with admin.connect() as connection:
            expected = connection.execute(
                sa.text(f"SELECT count(*) FROM {table} WHERE {key} = :ws"),  # noqa: S608
                {"ws": workspace},
            ).scalar()
        check(f"C4 {table}: no context, zero rows", without == 0, without)
        check(f"C4 {table}: context, own rows only", within == expected, [within, expected])

    with admin.connect() as connection:
        role = connection.execute(
            sa.text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'otlet_app'"
            )
        ).one()
        owned = connection.execute(
            sa.text("SELECT count(*) FROM pg_tables WHERE tableowner = 'otlet_app'")
        ).scalar()
        forced = connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_class WHERE relname = ANY(:t)"
                " AND relrowsecurity AND relforcerowsecurity"
            ),
            {"t": list(TABLES)},
        ).scalar()
    check("C5 application role: not superuser, no BYPASSRLS", tuple(role) == (False, False), list(role))
    check("C5 application role owns no table", owned == 0, owned)
    check("C4 RLS enabled and forced on every business table", forced == len(TABLES), forced)
    with app.connect() as connection:
        try:
            connection.execute(sa.text("CREATE TABLE intruder (id int)"))
            created = True
        except sa.exc.ProgrammingError:
            created = False
    check("C5 application role cannot create a table", not created, created)

    passed = all(c["ok"] for c in checks)
    path = write_result({"criteria": "C4 C5", "passed": passed, "checks": checks}, HERE / "results", "isolation")
    print(f"Result: {path}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

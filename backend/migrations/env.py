# SPDX-License-Identifier: AGPL-3.0-or-later
"""Alembic environment. The URL comes from otlet.platform.migrations.alembic_config; migrations
are written by hand (no autogenerate) so each one states its downgrade explicitly."""

import sqlalchemy as sa
from alembic import context

config = context.config


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = sa.create_engine(
        config.get_main_option("sqlalchemy.url") or "", poolclass=sa.pool.NullPool
    )
    with engine.connect() as connection:
        # The migration role creates objects as the schema owner (M-12, otlet.platform.roles).
        # Kept optional for a database that has not been provisioned yet.
        is_member = connection.execute(
            sa.text(
                "SELECT pg_has_role(current_user, oid, 'MEMBER') AND current_user <> rolname"
                " FROM pg_roles WHERE rolname = 'otlet_owner'"
            )
        ).scalar()
        if is_member:
            connection.execute(sa.text("SET ROLE otlet_owner"))
        connection.commit()
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

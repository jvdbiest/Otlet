# SPDX-License-Identifier: AGPL-3.0-or-later
"""Schema migrations with Alembic, run by the one-shot `migrate` role before the other roles
start (ARCHITECTURE §20.4). The backup that precedes them is a separate Compose service."""

import logging

from alembic import command
from alembic.config import Config

from otlet.platform.config import Settings

logger = logging.getLogger(__name__)


def alembic_config(settings: Settings) -> Config:
    config = Config()
    config.set_main_option("script_location", str(settings.migrations_dir))
    # Percent signs would be read as interpolation by configparser.
    config.set_main_option("sqlalchemy.url", settings.require_database_url().replace("%", "%%"))
    return config


def upgrade(settings: Settings, revision: str = "head") -> None:
    logger.info("upgrading schema to %s", revision)
    command.upgrade(alembic_config(settings), revision)


def downgrade(settings: Settings, revision: str) -> None:
    logger.info("downgrading schema to %s", revision)
    command.downgrade(alembic_config(settings), revision)


def current(settings: Settings) -> None:
    command.current(alembic_config(settings), verbose=True)


def history(settings: Settings) -> None:
    command.history(alembic_config(settings), verbose=True)

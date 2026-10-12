# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared by the integration tests and their fixtures (tests/conftest.py)."""

import os
from dataclasses import dataclass

import pytest

# Superuser connection to a disposable database, libpq form; set by the CI on Linux.
ADMIN_URL = os.environ.get("OTLET_TEST_ADMIN_URL")

requires_database = pytest.mark.skipif(ADMIN_URL is None, reason="OTLET_TEST_ADMIN_URL not set")


@dataclass(frozen=True)
class TestDatabase:
    """SQLAlchemy URLs of the three connections: superuser, migration role, application role."""

    __test__ = False  # not a test class, despite its name

    admin_url: str
    migrator_url: str
    app_url: str

# SPDX-License-Identifier: AGPL-3.0-or-later
"""A single scheduler leads at a time, and another takes over when it disappears
(ARCHITECTURE §12.5, TECH_CHOICES §9.4)."""

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db
from otlet.platform.leader import LeaderLock

pytestmark = requires_database


def test_one_leader_at_a_time_and_a_takeover(migrated: TestDatabase) -> None:
    engine = db.create_engine(migrated.app_url)
    first, second = LeaderLock(engine, key=42), LeaderLock(engine, key=42)
    assert first.hold()
    assert not second.hold()
    assert first.hold()  # still leading
    first.release()  # the process disappears: its connection closes
    assert second.hold()
    assert not first.hold()
    second.release()

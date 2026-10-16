# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import threading
import time
from pathlib import Path

import pytest

from otlet.entrypoints import cli
from otlet.entrypoints.scheduler import main as scheduler
from otlet.platform import process
from otlet.platform.config import Settings


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(SystemExit):
        cli.main(["publisher"])


def test_loop_role_writes_heartbeats_and_stops(tmp_path: Path) -> None:
    settings = Settings(ui_dir=None, run_dir=tmp_path)
    stop = threading.Event()
    thread = threading.Thread(target=scheduler.run, args=(settings, stop))
    thread.start()
    deadline = time.monotonic() + 5
    while not process.heartbeat_path(tmp_path, "scheduler").exists():
        assert time.monotonic() < deadline, "no heartbeat"
        time.sleep(0.01)
    stop.set()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_healthcheck_of_loop_role(tmp_path: Path) -> None:
    settings = Settings(ui_dir=None, run_dir=tmp_path)
    assert cli.healthcheck("scheduler", settings, port=0) == 1

    process.beat(tmp_path, "scheduler")
    assert cli.healthcheck("scheduler", settings, port=0) == 0

    stale = time.time() - cli.HEARTBEAT_MAX_AGE_SECONDS - 1
    os.utime(process.heartbeat_path(tmp_path, "scheduler"), (stale, stale))
    assert cli.healthcheck("scheduler", settings, port=0) == 1


def test_healthcheck_of_api_without_server(tmp_path: Path) -> None:
    # Port 9 (discard) is never served in a test environment.
    assert cli.healthcheck("api", Settings(ui_dir=None, run_dir=tmp_path), port=9) == 1

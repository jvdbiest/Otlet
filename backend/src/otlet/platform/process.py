# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lifecycle of long-running roles: stop on signal, heartbeat file for container health checks."""

import logging
import signal
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import FrameType

logger = logging.getLogger(__name__)


def heartbeat_path(run_dir: Path, role: str) -> Path:
    return run_dir / f"{role}.heartbeat"


def beat(run_dir: Path, role: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_path(run_dir, role).touch()


def is_alive(run_dir: Path, role: str, max_age: float) -> bool:
    try:
        age = time.time() - heartbeat_path(run_dir, role).stat().st_mtime
    except FileNotFoundError:
        return False
    return age <= max_age


def stop_on_signals() -> threading.Event:
    """Return an event set on SIGTERM or SIGINT, so a role finishes its current step and exits."""
    stop = threading.Event()

    def handler(signum: int, _frame: FrameType | None) -> None:
        logger.info("received signal %s, stopping", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    return stop


def run_loop(
    role: str,
    run_dir: Path,
    step: Callable[[], None],
    stop: threading.Event,
    interval: float,
) -> None:
    """Call `step` every `interval` seconds until `stop` is set, beating after each step."""
    logger.info("%s started", role)
    while not stop.is_set():
        step()
        beat(run_dir, role)
        stop.wait(interval)
    logger.info("%s stopped", role)

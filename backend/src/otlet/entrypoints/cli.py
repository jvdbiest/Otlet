# SPDX-License-Identifier: AGPL-3.0-or-later
"""`otlet <command>`: one image, several roles chosen at start-up (TC-13).

Each role imports only what it needs: the worker never loads FastAPI, and the API will never
load worker-only code such as secret decryption (DR6).
"""

import argparse
import os
import sys
import urllib.request
from collections.abc import Sequence

from otlet import __version__
from otlet.platform import logging as otlet_logging
from otlet.platform import process
from otlet.platform.config import Settings

LOOP_ROLES = ("worker", "scheduler")
# Loop roles beat every 5 s; three missed beats mean the role is stuck.
HEARTBEAT_MAX_AGE_SECONDS = 15.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="otlet", description="Otlet, image multirôle.")
    parser.add_argument("--version", action="version", version=f"otlet {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    port = int(os.environ.get("OTLET_API_PORT", "8000"))

    api = commands.add_parser("api", help="serveur HTTP (API et interface)")
    api.add_argument("--host", default=os.environ.get("OTLET_API_HOST", "0.0.0.0"))  # noqa: S104
    api.add_argument("--port", type=int, default=port)
    api.add_argument("--workers", type=int, default=int(os.environ.get("OTLET_API_WORKERS", "2")))

    commands.add_parser("worker", help="exécuteur des tâches de fond")
    commands.add_parser("scheduler", help="planificateur")

    migrate = commands.add_parser("migrate", help="migrations du schéma de la base")
    steps = migrate.add_subparsers(dest="step", required=True)
    upgrade = steps.add_parser("upgrade", help="monter le schéma (par défaut : dernière révision)")
    upgrade.add_argument("revision", nargs="?", default="head")
    downgrade = steps.add_parser("downgrade", help="redescendre le schéma à une révision")
    downgrade.add_argument("revision")
    steps.add_parser("current", help="révision actuelle de la base")
    steps.add_parser("history", help="révisions connues de cette version")

    health = commands.add_parser("healthcheck", help="contrôle de santé d'un rôle (conteneurs)")
    health.add_argument("role", choices=("api", *LOOP_ROLES))
    health.add_argument("--port", type=int, default=port)
    return parser


def healthcheck(role: str, settings: Settings, port: int) -> int:
    if role in LOOP_ROLES:
        return 0 if process.is_alive(settings.run_dir, role, HEARTBEAT_MAX_AGE_SECONDS) else 1
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310 (fixed local URL)
            return 0 if response.status == 200 else 1
    except OSError:
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()

    if args.command == "healthcheck":
        return healthcheck(args.role, settings, args.port)

    otlet_logging.configure()
    if args.command == "api":
        from otlet.entrypoints.api import server

        server.run(args.host, args.port, args.workers)
    elif args.command == "worker":
        from otlet.entrypoints.worker import main as worker

        worker.run(settings, process.stop_on_signals())
    elif args.command == "scheduler":
        from otlet.entrypoints.scheduler import main as scheduler

        scheduler.run(settings, process.stop_on_signals())
    elif args.command == "migrate":
        from otlet.platform import migrations

        if args.step == "upgrade":
            migrations.upgrade(settings, args.revision)
        elif args.step == "downgrade":
            migrations.downgrade(settings, args.revision)
        elif args.step == "current":
            migrations.current(settings)
        else:
            migrations.history(settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
DEFAULT_WORKSPACE_NAME = "Mon espace"


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

    database = commands.add_parser("db", help="rôles de la base (M-12)")
    database_steps = database.add_subparsers(dest="step", required=True)
    database_steps.add_parser(
        "provision",
        help="créer ou mettre à jour les rôles de la base (superutilisateur requis)",
    )

    migrate = commands.add_parser("migrate", help="migrations du schéma de la base")
    steps = migrate.add_subparsers(dest="step", required=True)
    upgrade = steps.add_parser("upgrade", help="monter le schéma (par défaut : dernière révision)")
    upgrade.add_argument("revision", nargs="?", default="head")
    downgrade = steps.add_parser("downgrade", help="redescendre le schéma à une révision")
    downgrade.add_argument("revision")
    steps.add_parser("current", help="révision actuelle de la base")
    steps.add_parser("history", help="révisions connues de cette version")

    secrets = commands.add_parser("secrets", help="secrets scellés (DR6)")
    actions = secrets.add_subparsers(dest="action", required=True)
    put = actions.add_parser("put", help="sceller la valeur lue sur l'entrée standard")
    put.add_argument("name")
    verify = actions.add_parser(
        "verify", help="ouvrir un secret et afficher l'empreinte SHA-256 de sa valeur"
    )
    verify.add_argument("name")

    admin = commands.add_parser("admin", help="administration de l'instance")
    admin_actions = admin.add_subparsers(dest="action", required=True)
    create_admin = admin_actions.add_parser(
        "create",
        help="créer un compte administrateur ; le mot de passe est lu sur l'entrée standard",
    )
    create_admin.add_argument("--login", required=True, help="adresse e-mail de connexion")
    create_admin.add_argument("--name", required=True, help="nom affiché")

    commands.add_parser(
        "openapi", help="afficher la spécification OpenAPI de l'API (client de l'interface)"
    )

    backup = commands.add_parser("backup", help="sauvegardes de l'instance (F08, ADR-0042)")
    backup_actions = backup.add_subparsers(dest="action", required=True)
    run = backup_actions.add_parser("run", help="faire une sauvegarde complète et la vérifier")
    run.add_argument("--reason", default="manual", choices=("manual", "scheduled", "startup"))
    backup_actions.add_parser("list", help="lister les sauvegardes, les plus récentes d'abord")
    check = backup_actions.add_parser("verify", help="vérifier toute une sauvegarde")
    check.add_argument("name")
    backup_actions.add_parser("prune", help="supprimer les sauvegardes qui ne sont plus gardées")
    restore = backup_actions.add_parser(
        "restore",
        help="remplacer la base et rétablir les fichiers depuis une sauvegarde, après une"
        " sauvegarde de l'état actuel ; arrêter d'abord api, worker et scheduler",
    )
    restore.add_argument("name")
    restore.add_argument("--yes", action="store_true", help="confirmer le remplacement")
    restore.add_argument(
        "--secrets-to", help="dossier où écrire les secrets de l'instance de la sauvegarde"
    )

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

        worker.run(settings)
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
    elif args.command == "db":
        return provision_command()
    elif args.command == "secrets":
        return secrets_command(args.action, args.name, settings)
    elif args.command == "admin":
        return create_admin_command(args.login, args.name, settings)
    elif args.command == "openapi":
        print(openapi_document())
    elif args.command == "backup":
        return backup_command(args)
    return 0


PASSWORD_MIN_LENGTH = 24


def provision_command() -> int:
    """Creates or updates the roles of M-12 before every start of the stack (the `provision`
    service): the API, the worker and the scheduler then connect as `otlet_app`, which cannot
    bypass row-level security, and migrations run as `otlet_migrator`. Reads
    OTLET_ADMIN_DATABASE_URL (superuser, libpq form), OTLET_MIGRATOR_PASSWORD and
    OTLET_APP_PASSWORD. Idempotent."""
    import os

    from otlet.platform import roles

    admin_url = os.environ.get("OTLET_ADMIN_DATABASE_URL", "")
    passwords = [
        os.environ.get(name, "") for name in ("OTLET_MIGRATOR_PASSWORD", "OTLET_APP_PASSWORD")
    ]
    if not admin_url or any(len(p) < PASSWORD_MIN_LENGTH for p in passwords):
        print(
            "otlet db provision: OTLET_ADMIN_DATABASE_URL, OTLET_MIGRATOR_PASSWORD and"
            f" OTLET_APP_PASSWORD ({PASSWORD_MIN_LENGTH} characters at least) are required;"
            " run deploy/configure.sh --complete",
            file=sys.stderr,
        )
        return 2
    roles.provision(admin_url, passwords[0], passwords[1])
    print("otlet db provision: roles up to date")
    return 0


def openapi_document() -> str:
    """The OpenAPI specification, from which the interface's API types are generated
    (tools/generate-api-types.sh). No database is contacted: the URL only enables the routes."""
    import json

    from otlet.entrypoints.api.app import create_app

    settings = Settings(
        ui_dir=None,
        run_dir=Settings.from_env().run_dir,
        database_url="postgresql+psycopg://openapi@localhost/openapi",
    )
    return json.dumps(create_app(settings).openapi(), indent=2, ensure_ascii=False, sort_keys=True)


def create_admin_command(login: str, name: str, settings: Settings) -> int:
    """Creates the first account (ROADMAP §5.2: one administrator account in É1)."""
    import getpass

    import sqlalchemy as sa

    from otlet.identity.adapters.argon2_hasher import Argon2Hasher
    from otlet.identity.adapters.postgres import PostgresIdentityStore
    from otlet.identity.application.authentication import Authentication
    from otlet.identity.domain.model import IdentityError
    from otlet.platform import database
    from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
    from otlet.workspaces.application.workspaces import Workspaces

    if sys.stdin.isatty():
        password = getpass.getpass("Mot de passe : ")
        if getpass.getpass("Confirmation : ") != password:
            print("otlet admin create: passwords differ", file=sys.stderr)
            return 2
    else:
        password = sys.stdin.readline().rstrip("\r\n")
    engine = database.create_engine(settings.require_database_url())
    authentication = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
    try:
        user_id = authentication.create_user(name, login, password, is_instance_admin=True)
        # É1 has one user and one workspace: the administrator gets theirs at once.
        Workspaces(PostgresWorkspaceStore(engine)).create(user_id, DEFAULT_WORKSPACE_NAME)
    except IdentityError as error:
        print(f"otlet admin create: {error}", file=sys.stderr)
        return 2
    except sa.exc.IntegrityError:
        print("otlet admin create: this login is already taken", file=sys.stderr)
        return 2
    print(user_id)
    return 0


def secrets_command(action: str, name: str, settings: Settings) -> int:
    import hashlib

    from otlet.platform import database
    from otlet.platform.secrets import SecretError, sealing, store

    engine = database.create_engine(settings.require_database_url())
    try:
        if action == "put":
            if settings.secrets_public_key_file is None:
                raise SecretError("OTLET_SECRETS_PUBLIC_KEY_FILE is not set")
            public_key = sealing.load_public_key(settings.secrets_public_key_file)
            plaintext = sys.stdin.buffer.read()
            store.put(engine, name, sealing.seal(public_key, plaintext, store.context(name)))
            return 0

        # Imported here only: the API process never loads it (DR6).
        from otlet.platform.secrets import opening

        private_key = opening.load_private_key(settings.secrets_private_key_file)
        sealed = store.get(engine, name)
        if sealed is None:
            raise SecretError(f"no secret named {name!r}")
        plaintext = opening.open_sealed(private_key, sealed, store.context(name))
        print(hashlib.sha256(plaintext).hexdigest())
        return 0
    except SecretError as error:
        print(f"otlet secrets {action}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())


def backup_command(args: argparse.Namespace) -> int:
    """Backups of the instance (ADR-0042), with the owner role (OTLET_BACKUP_DATABASE_URL, libpq
    form) into OTLET_BACKUP_DIR; encrypted with the passphrase of
    OTLET_BACKUP_PASSPHRASE_FILE when there is one."""
    from pathlib import Path

    from otlet.backup.adapters.crypto import Cipher
    from otlet.backup.adapters.postgres import PostgresDatabase
    from otlet.backup.application.backups import BackupError, Backups

    url = os.environ.get("OTLET_BACKUP_DATABASE_URL", "")
    if not url:
        print("otlet backup: OTLET_BACKUP_DATABASE_URL is required", file=sys.stderr)
        return 2
    destination = Path(os.environ.get("OTLET_BACKUP_DIR", "/backups"))
    destination.mkdir(parents=True, exist_ok=True)
    passphrase_file = os.environ.get("OTLET_BACKUP_PASSPHRASE_FILE", "")
    passphrase = Path(passphrase_file).read_text("utf-8").strip() if passphrase_file else ""
    sealer = Cipher.for_destination(destination, passphrase) if passphrase else None
    secrets = tuple(
        Path(value)
        for value in (
            os.environ.get("OTLET_SECRETS_PUBLIC_KEY_FILE", ""),
            os.environ.get("OTLET_SECRETS_PRIVATE_KEY_FILE", ""),
        )
        if value
    )
    backups = Backups(
        destination,
        PostgresDatabase(url),
        Path(os.environ.get("OTLET_FILES_DIR", "/var/lib/otlet/files")),
        sealer,
        secrets,
        __version__,
    )
    try:
        if args.action == "run":
            if sealer is None:
                print("otlet backup: not encrypted (no passphrase file)", file=sys.stderr)
            name = backups.run(args.reason)
            manifest = backups.manifest(name)
            backups.prune(
                int(os.environ.get("OTLET_BACKUP_DAILY", "7")),
                int(os.environ.get("OTLET_BACKUP_WEEKLY", "4")),
            )
            print(f"{name} verified={manifest.verified} files_new={manifest.files_new}")
            return 0 if manifest.verified else 1
        if args.action == "list":
            for name in backups.names():
                manifest = backups.manifest(name)
                print(
                    f"{name} {manifest.reason} verified={manifest.verified}"
                    f" encrypted={manifest.encrypted} files={manifest.files}"
                )
            return 0
        if args.action == "verify":
            problems = backups.verify(args.name)
            for problem in problems:
                print(problem)
            return 1 if problems else 0
        if args.action == "prune":
            for name in backups.prune(
                int(os.environ.get("OTLET_BACKUP_DAILY", "7")),
                int(os.environ.get("OTLET_BACKUP_WEEKLY", "4")),
            ):
                print(f"removed {name}")
            return 0
        if not args.yes:
            print(
                "otlet backup restore: replaces the whole database; add --yes to confirm",
                file=sys.stderr,
            )
            return 2
        secrets_to = Path(args.secrets_to) if args.secrets_to else None
        safety = backups.restore(args.name, secrets_to)
        print(f"restored {args.name}; the state before is kept as {safety}")
        return 0
    except BackupError as error:
        print(f"otlet backup: {error}", file=sys.stderr)
        return 1

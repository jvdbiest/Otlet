#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Generates the deployment configuration next to compose.yaml:
#   .env   domain and random database passwords (superuser, migrations, application);
#   keys/  X25519 key pair of the secrets (DR6): the public key is given to the API and the
#          worker, the private key to the worker only; the passphrase of the backups (ADR-0042).
#   backups/  the destination of the backups, unless OTLET_BACKUP_DIR names another folder.
# Usage: ./configure.sh <domain>
#        ./configure.sh --complete   adds the settings a newer version needs to an existing .env
# Never overwrites an existing .env or key: they protect the existing data. Run as root on a
# server, so the private key can be handed to the container user (uid 10001) alone.
set -eu

cd "$(dirname "$0")"

random_hex() {
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
}

# The passphrase of the backups (ADR-0042): six groups of four characters, shown once.
backup_passphrase() {
    if [ ! -e keys/backup-passphrase ]; then
        mkdir -p keys
        head -c 18 /dev/urandom | od -An -tx1 | tr -d ' 
' | sed 's/..../&-/g; s/-$//'             > keys/backup-passphrase
        if [ "$(id -u)" = 0 ]; then chown "$container_uid:$container_uid" keys/backup-passphrase; fi
        echo "Passphrase of the backups (keys/backup-passphrase): $(cat keys/backup-passphrase)"
        echo "Write it down and keep it apart from this machine: without it, an encrypted"
        echo "backup cannot be restored."
    fi
    mkdir -p backups && chmod 755 backups  # read by the API (uid 10001), read only
}

# Settings added after the first installation: generated if missing, never replaced.
complete() {
    for name in OTLET_MIGRATOR_PASSWORD OTLET_APP_PASSWORD; do
        if ! grep -q "^$name=." .env; then
            sed -i "/^$name=/d" .env
            echo "$name=$(random_hex)" >> .env
            echo "Added $name to .env"
        fi
    done
}

container_uid=10001

if [ "${1:-}" = "--complete" ]; then
    [ -e .env ] || { echo "No .env here: run ./configure.sh <domain> first." >&2; exit 1; }
    umask 077
    complete
    backup_passphrase
    exit 0
fi

domain="${1:?usage: ./configure.sh <domain>}"

if [ -e .env ] || [ -e keys/secrets-private.pem ]; then
    echo ".env or keys/ already exist; remove them first to generate a new configuration." >&2
    exit 1
fi

umask 077
sed \
    -e "s|^OTLET_DOMAIN=.*|OTLET_DOMAIN=$domain|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random_hex)|" \
    .env.example > .env
complete >/dev/null

mkdir -p keys
openssl genpkey -algorithm X25519 -out keys/secrets-private.pem
openssl pkey -in keys/secrets-private.pem -pubout -out keys/secrets-public.pem
chmod 644 keys/secrets-public.pem
if [ "$(id -u)" = 0 ]; then
    chown "$container_uid:$container_uid" keys/secrets-private.pem
else
    echo "Not root: keys/secrets-private.pem stays readable by $(id -un) only." >&2
    echo "On a server, run: chown $container_uid:$container_uid keys/secrets-private.pem" >&2
fi

backup_passphrase
echo "Configuration written to $(pwd)/.env and $(pwd)/keys/"
echo "Back up keys/secrets-private.pem apart from the database: without it, stored secrets"
echo "cannot be recovered."

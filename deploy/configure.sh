#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Generates the deployment configuration next to compose.yaml:
#   .env   domain and random database password;
#   keys/  X25519 key pair of the secrets (DR6): the public key is given to the API and the
#          worker, the private key to the worker only.
# Usage: ./configure.sh <domain>
# Never overwrites an existing .env or key: they protect the existing data. Run as root on a
# server, so the private key can be handed to the container user (uid 10001) alone.
set -eu

cd "$(dirname "$0")"

domain="${1:?usage: ./configure.sh <domain>}"
container_uid=10001

if [ -e .env ] || [ -e keys/secrets-private.pem ]; then
    echo ".env or keys/ already exist; remove them first to generate a new configuration." >&2
    exit 1
fi

random_hex() {
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
}

umask 077
sed \
    -e "s|^OTLET_DOMAIN=.*|OTLET_DOMAIN=$domain|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random_hex)|" \
    .env.example > .env

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

echo "Configuration written to $(pwd)/.env and $(pwd)/keys/"
echo "Back up keys/secrets-private.pem apart from the database: without it, stored secrets"
echo "cannot be recovered."

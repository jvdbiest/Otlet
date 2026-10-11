#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Generates the deployment configuration (.env) next to compose.yaml.
# Usage: ./configure.sh <domain>
# Never overwrites an existing .env: its password protects the existing database.
set -eu

cd "$(dirname "$0")"

domain="${1:?usage: ./configure.sh <domain>}"

if [ -e .env ]; then
    echo ".env already exists; remove it first to generate a new configuration." >&2
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

echo "Configuration written to $(pwd)/.env"

#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S6, criterion C2: upgrade with migration, then rollback, following
# docs/exploitation/mise-a-jour.md, with a fingerprint of control data checked at every step.
# Protocol: docs/spikes/S6.md §3.4.
#
# Usage, from anywhere: sh spikes/s6-delivery/upgrade-rollback.sh
# Uses its own Compose project (otlet-s6) and destroys it at the end; ports 80 and 443 must
# be free (or set OTLET_HTTP_PORT and OTLET_HTTPS_PORT). Writes spikes/s6-delivery/results/upgrade-rollback-<UTC time>.json.
set -eu

cd "$(dirname "$0")/../.."
spike=spikes/s6-delivery
mkdir -p "$spike/results" "$spike/data/backups"
rm -rf "$spike"/data/backups/*

export COMPOSE_PROJECT_NAME=otlet-s6
export OTLET_IMAGE=otlet-s6
export OTLET_DOMAIN=localhost
export OTLET_BACKUP_DIR="../$spike/data/backups"
export OTLET_KEYS_DIR="../$spike/data/keys"
POSTGRES_PASSWORD=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
export POSTGRES_PASSWORD
# Roles of M-12 (deploy/configure.sh generates the same in .env).
OTLET_MIGRATOR_PASSWORD=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
OTLET_APP_PASSWORD=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
export OTLET_MIGRATOR_PASSWORD OTLET_APP_PASSWORD
compose() { docker compose -f deploy/compose.yaml "$@"; }

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
steps=""
failed=0

cleanup() { compose down -v >/dev/null 2>&1 || true; }
trap cleanup EXIT

now() { date +%s; }
record() { # name, verdict, seconds
    steps="$steps${steps:+,}{\"step\":\"$1\",\"ok\":$2,\"seconds\":$3}"
    if [ "$2" = true ]; then echo "ok: $1 (${3}s)"; else echo "FAIL: $1 (${3}s)"; failed=1; fi
}
revision() {
    curl -fsSk "https://localhost:${OTLET_HTTPS_PORT:-443}/health" | sed -n 's/.*"schema_revision":"\([^"]*\)".*/\1/p'
}
psql_value() {
    compose exec -T db psql -U otlet -d otlet -tA -c "$1"
}
# The control data only: the backup service writes its own state there too (ADR-0042).
fingerprint() {
    psql_value "SELECT md5(string_agg(key || '=' || value::text, ',' ORDER BY key))
                FROM instance_settings WHERE key NOT LIKE 'backup.%'"
}
has_note_column() {
    psql_value "SELECT count(*) FROM information_schema.columns
                WHERE table_name = 'instance_settings' AND column_name = 'note'"
}
up() { # version
    if ! output=$(OTLET_VERSION="$1" compose up -d --wait --wait-timeout 300 2>&1); then
        echo "$output" >&2
        compose ps -a >&2
        return 1
    fi
}

# The stack needs the secrets key pair (same generation as deploy/configure.sh).
rm -rf "$spike/data/keys"
mkdir -p "$spike/data/keys"
openssl genpkey -algorithm X25519 -out "$spike/data/keys/secrets-private.pem"
openssl pkey -in "$spike/data/keys/secrets-private.pem" -pubout     -out "$spike/data/keys/secrets-public.pem"
# The passphrase of the backups (ADR-0042), as deploy/configure.sh makes it.
head -c 18 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$spike/data/keys/backup-passphrase"

# Version N is the current code, at the head of backend/migrations; N+1 adds one migration on
# top of it (next/settings_note.py.in).
versions=backend/migrations/versions
schema_n=$(sed -n 's/^revision = "\(.*\)"$/\1/p' "$versions"/*.py | while read -r rev; do
    grep -q "^down_revision = \"$rev\"" "$versions"/*.py || echo "$rev"
done)
echo "Building version N (schema $schema_n) and N+1"
docker build -q -f deploy/Containerfile -t otlet-s6:n . >/dev/null
next_context=$(mktemp -d)
cp "$spike/next/Containerfile" "$next_context/"
sed "s/@HEAD@/$schema_n/" "$spike/next/settings_note.py.in" > "$next_context/settings_note.py"
docker build -q --build-arg BASE=otlet-s6:n -f "$next_context/Containerfile" -t otlet-s6:n1 \
    "$next_context" >/dev/null
rm -rf "$next_context"
cleanup

# 1. Install version N and insert control data.
t=$(now)
up n
psql_value "INSERT INTO instance_settings (key, value) VALUES
            ('site.title', '\"Otlet\"'), ('site.language', '\"fr\"'), ('demo.count', '42')" >/dev/null
reference=$(fingerprint)
[ "$(revision)" = "$schema_n" ] && ok=true || ok=false
record install-n "$ok" $(($(now) - t))

# 2. Upgrade to N+1 (mise-a-jour.md §2): new version, then start; backup and migration run
# before the API.
t=$(now)
up n1
# The backup taken at the start of N+1, before its migration (ADR-0042: a folder per backup).
pre_upgrade_backup=$(ls -1 "$spike"/data/backups | grep -E '^[0-9]{4}-' | sort | tail -n 1)
[ "$(revision)" = s6_next ] && [ "$(fingerprint)" = "$reference" ] && [ "$(has_note_column)" = 1 ] \
    && ok=true || ok=false
record upgrade-n-to-n1 "$ok" $(($(now) - t))

# 3. Rollback (mise-a-jour.md §3): downgrade the schema with N+1, then start N.
t=$(now)
OTLET_VERSION=n1 compose stop api worker scheduler caddy >/dev/null 2>&1
OTLET_VERSION=n1 compose run --rm migrate migrate downgrade "$schema_n" >/dev/null 2>&1
up n
[ "$(revision)" = "$schema_n" ] && [ "$(fingerprint)" = "$reference" ] && [ "$(has_note_column)" = 0 ] \
    && ok=true || ok=false
record rollback-n1-to-n "$ok" $(($(now) - t))

# 4. Second resort (mise-a-jour.md §4): upgrade again, then restore the pre-upgrade dump.
up n1
t=$(now)
compose stop api worker scheduler caddy >/dev/null 2>&1
compose exec -T backups otlet backup restore "$pre_upgrade_backup" --yes >/dev/null 2>&1
up n
[ "$(revision)" = "$schema_n" ] && [ "$(fingerprint)" = "$reference" ] && [ "$(has_note_column)" = 0 ] \
    && ok=true || ok=false
record restore-backup-to-n "$ok" $(($(now) - t))

result="$spike/results/upgrade-rollback-$(date -u +%Y%m%dT%H%M%SZ).json"
printf '{"criterion":"C2","started":"%s","host":"%s","docker":"%s","passed":%s,"steps":[%s]}\n' \
    "$started" "$(uname -sm)" "$(docker version --format '{{.Server.Version}}')" \
    "$([ "$failed" = 0 ] && echo true || echo false)" "$steps" > "$result"
echo "Result: $result"
exit "$failed"

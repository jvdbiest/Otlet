#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S6, criterion C3 (DR6): a secret sealed by the API process cannot be opened in the API
# container, and is opened by the worker. Protocol: docs/spikes/S6.md §3.5.
#
# Usage, from anywhere: sh spikes/s6-delivery/secrets-separation.sh
# Uses its own Compose project (otlet-s6) and destroys it at the end; ports 80 and 443 must
# be free. Writes spikes/s6-delivery/results/secrets-separation-<UTC time>.json.
set -eu

cd "$(dirname "$0")/../.."
spike=spikes/s6-delivery
keys="$spike/data/keys"
mkdir -p "$spike/results" "$spike/data/backups"
rm -rf "$keys"
mkdir -p "$keys"

export COMPOSE_PROJECT_NAME=otlet-s6
export OTLET_IMAGE=otlet-s6
export OTLET_VERSION=secrets
export OTLET_DOMAIN=localhost
export OTLET_BACKUP_DIR="../$spike/data/backups"
export OTLET_KEYS_DIR="../$keys"
POSTGRES_PASSWORD=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
export POSTGRES_PASSWORD
compose() { docker compose -f deploy/compose.yaml "$@"; }

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
checks=""
failed=0
cleanup() { compose down -v >/dev/null 2>&1 || true; }
trap cleanup EXIT

record() { # name, ok, detail (JSON value)
    checks="$checks${checks:+,}{\"check\":\"$1\",\"ok\":$2,\"detail\":$3}"
    if [ "$2" = true ]; then echo "ok: $1"; else echo "FAIL: $1"; failed=1; fi
}

# Same key generation as deploy/configure.sh.
openssl genpkey -algorithm X25519 -out "$keys/secrets-private.pem"
openssl pkey -in "$keys/secrets-private.pem" -pubout -out "$keys/secrets-public.pem"
chmod 600 "$keys/secrets-private.pem"
chmod 644 "$keys/secrets-public.pem"
if [ "$(uname -s)" = Linux ] && [ "$(id -u)" != 0 ]; then
    sudo -n chown 10001:10001 "$keys/secrets-private.pem"
fi

docker build -q -f deploy/Containerfile -t otlet-s6:secrets . >/dev/null
cleanup
compose up -d --wait --wait-timeout 300 >/dev/null 2>&1

secret="s6-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
expected=$(printf '%s' "$secret" | sha256sum | cut -d ' ' -f 1)

# 1. The API process seals the secret with its configuration.
if printf '%s' "$secret" | compose exec -T api otlet secrets put s6.check; then
    record api-seals true '""'
else
    record api-seals false '""'
fi

# 2. The same command that opens secrets fails in the API container.
if output=$(compose exec -T api otlet secrets verify s6.check 2>&1); then
    record api-cannot-open-with-cli false "\"opened: $output\""
else
    record api-cannot-open-with-cli true "\"$(echo "$output" | tr -d '"')\""
fi

# 3. Everything in the API container (environment, whole file system) is tried as a key.
report=$(compose exec -T api python - s6.check < "$spike/find_and_open.py" 2>/dev/null) \
    && opened=true || opened=false
[ -n "$report" ] || report='null'
if [ "$opened" = false ] && [ "$report" != null ]; then
    record api-container-has-no-usable-key true "$report"
else
    record api-container-has-no-usable-key false "$report"
fi

# 4. The private key's own text appears nowhere in the API container.
body=$(sed -n '2p' "$keys/secrets-private.pem")
if compose exec -T api sh -c "env | grep -qF '$body' || grep -rqsF '$body' / \
        --exclude-dir=proc --exclude-dir=sys --exclude-dir=dev"; then
    record private-key-absent-from-api false '""'
else
    record private-key-absent-from-api true '""'
fi

# 5. In the resolved Compose configuration, only the worker receives the private key.
holders=$(compose config --format json | docker run --rm -i --entrypoint python otlet-s6:secrets -c '
import json, sys
config = json.load(sys.stdin)
print(",".join(sorted(
    name for name, service in config["services"].items()
    if any(s.get("source") == "secrets_private_key" for s in service.get("secrets", []))
)))')
[ "$holders" = worker ] && ok=true || ok=false
record only-worker-mounts-private-key "$ok" "\"$holders\""

# 6. The worker opens the secret sealed by the API.
opened=$(compose exec -T worker otlet secrets verify s6.check 2>/dev/null || true)
[ "$opened" = "$expected" ] && ok=true || ok=false
record worker-opens "$ok" '""'

# 7. Control of check 3: the same search, run in the worker container, finds the key.
report=$(compose exec -T worker python - s6.check < "$spike/find_and_open.py" 2>/dev/null) \
    && ok=true || ok=false
[ -n "$report" ] || report='null'
record search-finds-key-in-worker "$ok" "$report"

result="$spike/results/secrets-separation-$(date -u +%Y%m%dT%H%M%SZ).json"
printf '{"criterion":"C3","started":"%s","host":"%s","docker":"%s","passed":%s,"checks":[%s]}\n' \
    "$started" "$(uname -sm)" "$(docker version --format '{{.Server.Version}}')" \
    "$([ "$failed" = 0 ] && echo true || echo false)" "$checks" > "$result"
echo "Result: $result"
exit "$failed"

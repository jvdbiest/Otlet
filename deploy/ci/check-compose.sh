#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Checks of the solo Compose stack (S6.3): every service healthy, the interface and /health
# served over HTTPS by Caddy, HTTP redirected to HTTPS, and the application connected with a
# role that row-level security binds (M-12).
# Expects a running stack: deploy/configure.sh localhost && docker compose up -d --wait
# Usage: deploy/ci/check-compose.sh [base-url] [compose-file]
set -eu

base="${1:-https://localhost}"
compose_file="${2:-deploy/compose.yaml}"
env_file="$(dirname "$compose_file")/.env"
failed=0

check() {
    description="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "ok: $description"
    else
        echo "FAIL: $description"
        failed=1
    fi
}

# -k: with OTLET_DOMAIN=localhost the certificate comes from Caddy's local authority.
check "/health over HTTPS" sh -c "curl -fsSk '$base/health' | grep -q '\"status\":\"ok\"'"
check "interface over HTTPS" sh -c "curl -fsSk '$base/' | grep -q '<div id=\"root\">'"
check "client route falls back to the interface" sh -c "curl -fsSk '$base/library/1' | grep -q '<div id=\"root\">'"
check "HTTP redirected to HTTPS" sh -c "curl -s 'http${base#https}/' -o /dev/null -w '%{http_code}' | grep -q 308"

# The application role is neither superuser nor allowed to bypass row-level security, the
# services use it, and without a workspace context it sees none of the rows that exist.
dc() {
    docker compose -f "$compose_file" "$@"
}
as_superuser() {
    dc exec -T db psql -U otlet -d otlet -tAc "$1"
}
app_password="$(sed -n 's/^OTLET_APP_PASSWORD=//p' "$env_file")"
app_is_bound() {
    test "$(as_superuser "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = 'otlet_app'")" = f
}
api_uses_app() {
    dc exec -T api sh -c 'echo "$OTLET_DATABASE_URL"' | grep -q '//otlet_app:'
}
app_sees_nothing() {
    test "$(dc exec -T -e PGPASSWORD="$app_password" db psql -h 127.0.0.1 -U otlet_app -d otlet \
        -tAc 'SELECT count(*) FROM workspaces')" = 0
}
check "otlet_app cannot bypass row-level security" app_is_bound
check "the API connects as otlet_app" api_uses_app
as_superuser "INSERT INTO workspaces (name) VALUES ('check-compose')" >/dev/null
check "without a workspace context, otlet_app sees zero rows" app_sees_nothing
as_superuser "DELETE FROM workspaces WHERE name = 'check-compose'" >/dev/null

exit "$failed"


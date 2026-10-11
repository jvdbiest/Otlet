#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Checks of the solo Compose stack (S6.3): every service healthy, the interface and /health
# served over HTTPS by Caddy, HTTP redirected to HTTPS.
# Expects a running stack: deploy/configure.sh localhost && docker compose up -d --wait
# Usage: deploy/ci/check-compose.sh [base-url]
set -eu

base="${1:-https://localhost}"
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

exit "$failed"

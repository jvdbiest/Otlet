#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Checks of the multi-role image (S6.2): the three roles start and report healthy on a
# read-only file system, processes run as a non-root user, Node.js is absent.
# Usage: deploy/ci/check-image.sh <image>
set -eu

image="${1:?usage: check-image.sh <image>}"
roles="api worker scheduler"
failed=0

cleanup() {
    for role in $roles; do docker rm -f "otlet-check-$role" >/dev/null 2>&1 || true; done
}
trap cleanup EXIT

uid=$(docker run --rm --entrypoint id "$image" -u)
if [ "$uid" = "0" ]; then
    echo "FAIL: the image runs as root"
    failed=1
else
    echo "ok: runs as uid $uid"
fi

if docker run --rm --entrypoint sh "$image" -c 'command -v node' >/dev/null 2>&1; then
    echo "FAIL: Node.js is present in the final image"
    failed=1
else
    echo "ok: no Node.js in the final image"
fi

for role in $roles; do
    docker run -d --name "otlet-check-$role" --read-only --tmpfs /tmp "$image" "$role" >/dev/null
done

for role in $roles; do
    healthy=0
    for _ in $(seq 1 30); do
        if docker exec "otlet-check-$role" otlet healthcheck "$role"; then
            healthy=1
            break
        fi
        sleep 1
    done
    if [ "$healthy" = 1 ]; then
        echo "ok: role $role healthy"
    else
        echo "FAIL: role $role not healthy after 30 s"
        docker logs "otlet-check-$role" || true
        failed=1
    fi
done

exit "$failed"

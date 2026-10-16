#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Checks of the multi-role image (S6.2): the three roles start and report healthy on a
# read-only file system against a throwaway PostgreSQL, processes run as a non-root user,
# Node.js is absent.
# Usage: deploy/ci/check-image.sh <image>
set -eu

image="${1:?usage: check-image.sh <image>}"
roles="api worker scheduler"
failed=0

cleanup() {
    for name in $roles db; do docker rm -f "otlet-check-$name" >/dev/null 2>&1 || true; done
    docker network rm otlet-check >/dev/null 2>&1 || true
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

# The worker runs the job queue (F04): the roles start against a throwaway, migrated database.
docker network create otlet-check >/dev/null
docker run -d --name otlet-check-db --network otlet-check -e POSTGRES_PASSWORD=check \
    -e POSTGRES_DB=otlet pgvector/pgvector:0.8.7-pg18-trixie >/dev/null
for _ in $(seq 1 30); do
    docker exec otlet-check-db pg_isready -h 127.0.0.1 -U postgres -d otlet >/dev/null 2>&1 && break
    sleep 1
done
url=postgresql+psycopg://postgres:check@otlet-check-db:5432/otlet
run() { docker run --network otlet-check --read-only --tmpfs /tmp -e OTLET_DATABASE_URL="$url" "$@"; }
if run --rm "$image" migrate upgrade >/dev/null 2>&1; then
    echo "ok: schema migrated"
else
    echo "FAIL: migrations"
    failed=1
fi

for role in $roles; do
    run -d --name "otlet-check-$role" "$image" "$role" >/dev/null
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

#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S2, run ON the measurement machine by run-s2.sh (detached). Uses the PostgreSQL of the
# Otlet stack installed in /opt/otlet, in a separate database otlet_s2.
# Usage: sh remote-s2.sh procrastinate|dbos
set -eu

engine="${1:-procrastinate}"
here=$(pwd)
work="$HOME/otlet-s2"
mkdir -p results
chmod 777 results
log() { echo "### $(date -u +%H:%M:%S) $*"; }
secret() { head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

super_password=$(sudo grep '^POSTGRES_PASSWORD=' /opt/otlet/deploy/.env | cut -d= -f2)
migrator_password=$(secret)
app_password=$(secret)
export S2_SERVER_URL="postgresql://otlet:$super_password@db:5432/postgres"
export S2_ADMIN_URL="postgresql://otlet:$super_password@db:5432/otlet_s2"
export S2_MIGRATOR_URL="postgresql://otlet_migrator:$migrator_password@db:5432/otlet_s2"
export S2_APP_URL="postgresql://otlet_app:$app_password@db:5432/otlet_s2"

image=otlet-s2
network=otlet_default
environment="-e S2_SERVER_URL -e S2_ADMIN_URL -e S2_MIGRATOR_URL -e S2_APP_URL -e S2_ENGINE=$engine -e PYTHONPATH=/work/backend/src"

run_py() {
    # shellcheck disable=SC2086
    sudo -E docker run --rm --network "$network" $environment \
        -v "$work:/work" -w /work/spikes/s2-queue --entrypoint python "$image" "$@"
}
start_worker() {
    # shellcheck disable=SC2086
    sudo -E docker run -d --name "$1" --network "$network" $environment -e S2_WORKER="$1" \
        -v "$work:/work" -w /work/spikes/s2-queue --entrypoint python "$image" \
        "${engine}_app.py" worker > /dev/null
}
sql() {
    sudo docker exec otlet-db-1 psql -U otlet -d otlet_s2 -tAc "$1"
}
wait_for() { # sql returning a number, expected value, timeout in seconds
    deadline=$(( $(date +%s) + $3 ))
    while [ "$(sql "$1")" != "$2" ] && [ "$(date +%s)" -lt "$deadline" ]; do sleep 5; done
}
cleanup() { sudo docker rm -f s2-worker-1 s2-worker-2 > /dev/null 2>&1 || true; }
trap cleanup EXIT

log "image"
sudo docker build -q -t "$image" . > /dev/null
cleanup

log "setup ($engine)"
run_py scenarios.py setup

log "C1 transactional enqueue"
run_py scenarios.py c1

start_worker s2-worker-1
start_worker s2-worker-2

log "C6 row-level security"
run_py scenarios.py c6-enqueue
wait_for "SELECT count(*) FROM effects WHERE task_ref LIKE 'c6-%'" 220 600
run_py scenarios.py c6-check

log "C5 targeted cancellation"
run_py scenarios.py c5

log "C2 C3 C4 brutal stops"
run_py scenarios.py c2-enqueue
seed=2026
deadline=$(( $(date +%s) + 1800 ))
while [ "$(sql "SELECT count(*) FROM effects WHERE task_ref LIKE 'c2-%'")" -lt 1000 ] \
        && [ "$(date +%s)" -lt "$deadline" ]; do
    seed=$((seed + 1))
    pause=$(awk -v s="$seed" 'BEGIN { srand(s); print 5 + int(rand() * 26) }')
    victim=$(awk -v s="$seed" 'BEGIN { srand(s * 7); print (rand() < 0.5) ? "s2-worker-1" : "s2-worker-2" }')
    sleep "$pause"
    sql "INSERT INTO kills (worker) VALUES ('$victim')" > /dev/null
    sudo docker kill -s KILL "$victim" > /dev/null
    sudo docker start "$victim" > /dev/null
    echo "killed $victim after ${pause}s"
done
sleep 15
run_py scenarios.py c2-check
sudo docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' s2-worker-1 s2-worker-2 \
    > results/worker-memory.txt || true
sudo chown -R "$(id -u)" results
log "done"

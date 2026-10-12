#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S1, the whole measure on the measurement machine (docs/spikes/S1.md §3.4), as one command:
#   OTLET_SSH_OPTS="-i ~/.ssh/otlet_nas" sh spikes/s1-postgres/run-s1.sh otlet@192.168.129.249
# Expects Otlet installed in /opt/otlet (docs/exploitation/installation.md). Copies the
# spikes and backend/src to the machine, restarts PostgreSQL with the settings of
# compose.s1.yaml, provisions the roles (M-12), generates the data set, checks C4 and C5,
# then runs 3 passes of each variant while memwatch samples the memory of the stack.
set -eu

target="${1:?usage: run-s1.sh <ssh target>}"
cd "$(dirname "$0")/../.."
ssh_opts="${OTLET_SSH_OPTS:-}"

# shellcheck disable=SC2086
tar -cf - --exclude=results --exclude=data --exclude=__pycache__ \
        spikes/bench spikes/s1-postgres backend/src \
    | ssh $ssh_opts "$target" 'rm -rf ~/otlet-s1 && mkdir -p ~/otlet-s1 && tar -xf - -C ~/otlet-s1'

# shellcheck disable=SC2086
ssh $ssh_opts "$target" sh -s <<'REMOTE'
set -eu
cd ~/otlet-s1/spikes/s1-postgres
mkdir -p results data
chmod 777 results data
secret() { head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
super_password=$(sudo grep '^POSTGRES_PASSWORD=' /opt/otlet/deploy/.env | cut -d= -f2)
migrator_password=$(secret); app_password=$(secret); bench_password=$(secret)
admin="postgresql://otlet:$super_password@db:5432/otlet"
migrator="postgresql://otlet_migrator:$migrator_password@db:5432/otlet"
app="postgresql+psycopg://otlet_app:$app_password@db:5432/otlet"
admin_sa="postgresql+psycopg://otlet:$super_password@db:5432/otlet"
bench="postgresql+psycopg://otlet_bench:$bench_password@db:5432/otlet"

compose() {
    sudo docker compose --project-directory /opt/otlet/deploy \
        -f /opt/otlet/deploy/compose.yaml -f "$PWD/compose.s1.yaml" "$@"
}
python_in_image() {
    sudo docker run --rm --network otlet_default \
        -v "$HOME/otlet-s1:/work" -e PYTHONPATH=/work/backend/src \
        -w /work/spikes/s1-postgres --entrypoint python otlet:dev "$@"
}

echo "### $(date -u +%H:%M:%S) restart with the S1 settings"
compose up -d --wait --wait-timeout 300 >/dev/null 2>&1
compose exec -T db psql -U otlet -d otlet -tAc "SHOW shared_buffers"

echo "### $(date -u +%H:%M:%S) roles (M-12)"
python_in_image -c "from otlet.platform import roles; roles.provision('$admin', '$migrator_password', '$app_password')"

echo "### $(date -u +%H:%M:%S) data set (S1.2)"
python_in_image generate.py --admin-url "$admin" --migrator-url "$migrator"
compose exec -T db psql -U otlet -d otlet -v ON_ERROR_STOP=1 -v password="$bench_password" < bench_role.sql >/dev/null

echo "### $(date -u +%H:%M:%S) isolation (C4, C5)"
python_in_image check_isolation.py --app-url "$app" --admin-url "$admin_sa" || true

echo "### $(date -u +%H:%M:%S) measures (C1, C2, C3)"
sudo python3 ../bench/memwatch.py --project otlet --out results/memory.json > /dev/null &
watcher=$!
sleep 3
for number in 1 2 3; do
    python_in_image measure.py rls --url "$app" --pass "$number"
    python_in_image measure.py norls --url "$bench" --pass "$number"
done
sudo kill -INT "$watcher"
wait "$watcher" || true
sudo chown -R "$(id -u)" results data
cp data/summary.json results/dataset.json
echo "### $(date -u +%H:%M:%S) done"
REMOTE

mkdir -p spikes/s1-postgres/results
# shellcheck disable=SC2086
ssh $ssh_opts "$target" 'cd ~/otlet-s1/spikes/s1-postgres && tar -cf - results' \
    | tar -xf - -C spikes/s1-postgres
echo "Results copied to spikes/s1-postgres/results/"

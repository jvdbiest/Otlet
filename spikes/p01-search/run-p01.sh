#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# P01, the whole measure as one command (docs/spikes/P01.md §3):
#   OTLET_SSH_OPTS="-i ~/.ssh/otlet_nas" sh spikes/p01-search/run-p01.sh <corpus host> <measure host> [--smoke]
# 1. exports the real items collected on the corpus host (the work VM, stack otlet-x01);
# 2. on the measure host (the NAS VM): starts a disposable PostgreSQL with the settings of S1,
#    provisions the roles of M-12, applies the migrations, loads the data set, measures the
#    selectivity of the queries, then runs 3 passes (1 short trial with --smoke);
# 3. brings results/ back and removes the disposable database.
# The corpus itself never leaves the two machines (P01 §3.1).
set -eu

corpus_host="${1:?usage: run-p01.sh <corpus host> <measure host> [--smoke]}"
measure_host="${2:?usage: run-p01.sh <corpus host> <measure host> [--smoke]}"
smoke="${3:-}"
cd "$(dirname "$0")/../.."
ssh_opts="${OTLET_SSH_OPTS:-}"

# shellcheck disable=SC2086
tar -cf - --exclude=results --exclude=data --exclude=__pycache__ --exclude=.venv \
        spikes/bench spikes/p01-search backend/src backend/migrations backend/pyproject.toml \
        backend/uv.lock \
    | ssh $ssh_opts "$measure_host" \
        'sudo rm -rf ~/otlet-p01 && mkdir -p ~/otlet-p01/spikes/p01-search/data && tar -xf - -C ~/otlet-p01'

echo "### corpus: real items of $corpus_host (feed items only, never versioned)"
# shellcheck disable=SC2086
ssh $ssh_opts "$corpus_host" "sudo docker exec otlet-x01-db-1 psql -U otlet -d otlet -tA -c \
    \"SELECT json_build_object('title', title, 'summary', summary, 'language', language,
       'text', CASE WHEN text_status = 'full_text' THEN coalesce(text, feed_content) END)
      FROM source_items WHERE origin = 'feed' AND text_status IN ('full_text', 'summary_only')\"" \
    | ssh $ssh_opts "$measure_host" 'cat > ~/otlet-p01/spikes/p01-search/data/corpus.jsonl'

# shellcheck disable=SC2086
ssh $ssh_opts "$measure_host" SMOKE="$smoke" sh -s <<'REMOTE'
set -eu
cd ~/otlet-p01/spikes/p01-search
mkdir -p results
chmod 777 results data
secret() { head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
super=$(secret); migrator=$(secret); app=$(secret)

cleanup() {
    sudo docker rm -f p01-pg >/dev/null 2>&1 || true
    sudo docker volume rm p01-data >/dev/null 2>&1 || true
    sudo docker network rm p01 >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
sudo docker network create p01 >/dev/null
echo "### $(date -u +%H:%M:%S) disposable PostgreSQL with the settings of S1"
sudo docker run -d --name p01-pg --network p01 --shm-size=1g -v p01-data:/var/lib/postgresql \
    -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD="$super" -e POSTGRES_DB=otlet \
    pgvector/pgvector:0.8.7-pg18-trixie postgres -c shared_buffers=768MB \
    -c effective_cache_size=2GB -c work_mem=16MB -c maintenance_work_mem=256MB \
    -c random_page_cost=1.1 >/dev/null
until sudo docker exec p01-pg pg_isready -U postgres -d otlet >/dev/null 2>&1; do sleep 1; done
sleep 2

python_env() {
    sudo docker run --rm --network p01 -v "$HOME/otlet-p01:/repo" -v p01-uv:/uv \
        -e UV_CACHE_DIR=/uv/cache -e UV_PROJECT_ENVIRONMENT=/uv/venv -e UV_PYTHON=3.13 \
        -e PYTHONDONTWRITEBYTECODE=1 \
        -w /repo/spikes/p01-search python:3.13-slim sh -c \
        "pip install -q uv==0.13.0 2>/dev/null; (cd /repo/backend && uv sync -q --locked --no-dev) && /uv/venv/bin/python $*"
}
admin="postgresql://postgres:$super@p01-pg:5432/otlet"
migrator_url="postgresql+psycopg://otlet_migrator:$migrator@p01-pg:5432/otlet"
app_url="postgresql+psycopg://otlet_app:$app@p01-pg:5432/otlet"
flag=""
[ "$SMOKE" = "--smoke" ] && flag="--smoke"

echo "### $(date -u +%H:%M:%S) roles (M-12), schema and data set"
python_env "-c \"from otlet.platform import roles; roles.provision('$admin', '$migrator', '$app')\""
python_env "generate.py --admin-url '$admin' --migrator-url '$migrator_url' $flag"
echo "### $(date -u +%H:%M:%S) selectivity (information)"
python_env "measure.py --url '$app_url' --selectivity"
passes="1 2 3"
[ -n "$flag" ] && passes="1"
for number in $passes; do
    echo "### $(date -u +%H:%M:%S) pass $number"
    python_env "measure.py --url '$app_url' --pass $number $flag"
done
sudo chown -R "$(id -u)" results data
echo "### $(date -u +%H:%M:%S) done"
REMOTE

mkdir -p spikes/p01-search/results
# shellcheck disable=SC2086
ssh $ssh_opts "$measure_host" 'cd ~/otlet-p01/spikes/p01-search && tar -cf - results' \
    | tar -xf - -C spikes/p01-search
echo "Results copied to spikes/p01-search/results/"

#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# P02 on the work VM, detached (nohup). Each step resumes or is skipped once done:
#   check  S5's CC0 corpus gives S5b's thresholds again, or nothing else runs
#   extract, preview, select  read the instance, no model
#   generate  one call at a time; needs ~/p02-corpus/go.ok, OLLAMA_URL and OLLAMA_MODEL
#   score  needs ~/p02-corpus/review.ok, written once the outputs are read (P02 §3.1)
# Reads the whole instance (P02 §3.1). Texts stay in ~/p02-corpus, never versioned.
set -eu
cd "$(dirname "$0")"
CORPUS="$HOME/p02-corpus"
DB=otlet-x01-db-1
mkdir -p "$CORPUS" results && chmod 700 "$CORPUS" && chmod 777 results
step() { echo "### $(date -u +%H:%M:%S) $1"; }
bench() {
    sudo docker run --rm --cpus=2 -v otlet-p02-models:/models -e HF_HOME=/models/hf \
        -v "$(pwd):/work" -v "$CORPUS:/corpus" -v "$(pwd)/../s5-similarity/corpus:/s5:ro" otlet-p02 p02.py "$@"
}

sudo docker build -q -f Containerfile -t otlet-p02 . > /dev/null
step check
bench check /s5

if [ ! -s "$CORPUS/candidates.jsonl" ]; then
    step extract
    sudo docker exec "$DB" mkdir -p /tmp/p02
    sudo docker cp extract.sql "$DB:/tmp/p02/extract.sql"
    sudo docker exec "$DB" sh -c \
        "psql -U \$POSTGRES_USER -d \${POSTGRES_DB:-otlet} -v out=/tmp/p02 -f /tmp/p02/extract.sql"
    sudo docker cp "$DB:/tmp/p02/candidates.jsonl" "$CORPUS/"
    sudo docker cp "$DB:/tmp/p02/drafts.jsonl" "$CORPUS/"
    sudo docker exec "$DB" rm -rf /tmp/p02
    sudo chown "$(id -u):$(id -g)" "$CORPUS"/*.jsonl
fi
if [ ! -e "$CORPUS/preview.done" ]; then
    step preview
    bench preview /corpus
    touch "$CORPUS/preview.done"
fi
if [ ! -e "$CORPUS/go.ok" ]; then
    step "preview done: the generation waits for Joël ($CORPUS/go.ok)"
    exit 0
fi
if [ ! -s "$CORPUS/selected.json" ]; then
    step select
    bench select /corpus
fi
step generate
python3 generate.py "$CORPUS"
if [ -e "$CORPUS/review.ok" ]; then
    step score
    bench score /corpus
else
    step "waiting for the review: $CORPUS/review.ok"
fi
step done

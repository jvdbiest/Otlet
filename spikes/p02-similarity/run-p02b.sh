#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# P02b on the work VM, detached (nohup), after P02: uses its extract in ~/p02-corpus.
#   select  the fresh sources, no model
#   generate  one call at a time; needs OLLAMA_URL and OLLAMA_MODEL
#   score  needs ~/p02b-corpus/review.ok, written once the outputs are read (P02b §3)
set -eu
cd "$(dirname "$0")"
FIRST="$HOME/p02-corpus"
SECOND="$HOME/p02b-corpus"
mkdir -p "$SECOND" results && chmod 700 "$SECOND" && chmod 777 results
step() { echo "### $(date -u +%H:%M:%S) $1"; }
bench() {
    sudo docker run --rm --cpus=2 -v otlet-p02-models:/models -e HF_HOME=/models/hf \
        -v "$(pwd):/work" -v "$FIRST:/first" -v "$SECOND:/second" otlet-p02 p02b.py "$@"
}

sudo docker build -q -f Containerfile -t otlet-p02 . > /dev/null
if [ ! -s "$SECOND/selected.json" ]; then
    step select
    bench select /first /second
    sudo chown "$(id -u):$(id -g)" "$SECOND"/*
fi
step generate
python3 generate.py "$SECOND"
if [ -e "$SECOND/review.ok" ]; then
    step score
    bench score /first /second
else
    step "waiting for the review: $SECOND/review.ok"
fi
step done

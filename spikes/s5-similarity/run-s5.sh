#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S5 on the measurement machine, detached (nohup): one container per model, limited to
# 2 vCPU, models cached in a Docker volume. Progress: ~/otlet-s5/run.log
set -eu
cd "$(dirname "$0")"
mkdir -p results && chmod 777 results
sudo docker build -q -f Containerfile -t otlet-s5 . > /dev/null
for model in sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
             intfloat/multilingual-e5-small \
             minishlab/potion-multilingual-128M; do
    echo "### $(date -u +%H:%M:%S) $model"
    sudo docker run --rm --cpus=2 -v otlet-s5-models:/models -e FASTEMBED_CACHE_PATH=/models \
        -v "$(pwd):/work" otlet-s5 s5.py "$model" || echo "FAILED $model"
done
echo "### $(date -u +%H:%M:%S) done"

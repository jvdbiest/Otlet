#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S5b on the measurement machine, detached (nohup): one container per variant, limited to
# 2 vCPU, model cached in the same Docker volume as S5. Progress: run-s5b.log
set -eu
cd "$(dirname "$0")"
mkdir -p results && chmod 777 results
sudo docker build -q -f Containerfile -t otlet-s5 . > /dev/null
for variant in float32 float16 int8; do
    echo "### $(date -u +%H:%M:%S) $variant"
    sudo docker run --rm --cpus=2 -v otlet-s5-models:/models -e HF_HOME=/models/hf \
        -v "$(pwd):/work" otlet-s5 s5b.py "$variant" || echo "FAILED $variant"
done
echo "### $(date -u +%H:%M:%S) done"

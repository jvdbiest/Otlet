#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S4 on the measurement machine, detached (nohup), from a copy of spikes/ (s4-gateway and
# s5-similarity side by side). Needs ~/otlet-s4.env (S4_DATABASE_URL, S4_FAKE, S4_PROVIDERS),
# the containers s4-ollama (model pulled) and s4-fake, all on the network otlet_default.
# Conformity, budget and fallbacks first (minutes), then the 50 briefs on Ollama (hours).
set -eu
cd "$(dirname "$0")"
mkdir -p results && chmod 777 results
sudo docker build -q -f Containerfile -t otlet-s4 . > /dev/null
sudo docker start s4-ollama s4-fake > /dev/null
sleep 5

run() {
    sudo docker run --rm --network otlet_default --env-file "$HOME/otlet-s4.env" -e S4_TIMEOUT=1800 \
        -v "$(cd .. && pwd):/spikes" -w /spikes/s4-gateway otlet-s4 -u run_s4.py "$@"
}
for measure in conformity budget fallbacks; do
    echo "### $(date -u +%H:%M:%S) $measure"
    run "$measure" || echo "FAILED $measure"
done
echo "### $(date -u +%H:%M:%S) briefs ollama"
sudo docker exec s4-ollama ollama show qwen2.5:1.5b-instruct --modelfile | grep -m1 '^FROM' || true
run briefs ollama || echo "FAILED briefs"
echo "### $(date -u +%H:%M:%S) done"

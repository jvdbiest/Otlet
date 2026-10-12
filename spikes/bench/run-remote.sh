#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Runs a command of the spikes on the measurement machine, then fetches its results (B09).
#
# Usage: spikes/bench/run-remote.sh <ssh target> <spike dir> <command…>
#   spikes/bench/run-remote.sh otlet@192.168.129.249 bench \
#       python3 bench.py http https://192.168.129.249/health --insecure --name health
#
# The spike directory (spikes/<dir>) and the bench are copied to ~/otlet-spikes on the
# machine; the command runs from the spike directory; its results/ folder is copied back.
# SSH options (key…) come from OTLET_SSH_OPTS, for example "-i ~/.ssh/otlet_nas".
set -eu

target="${1:?usage: run-remote.sh <ssh target> <spike dir> <command…>}"
spike="${2:?usage: run-remote.sh <ssh target> <spike dir> <command…>}"
shift 2
cd "$(dirname "$0")/.."
ssh_opts="${OTLET_SSH_OPTS:-}"

# shellcheck disable=SC2086
tar -cf - --exclude=results --exclude=data --exclude=__pycache__ bench "$spike" \
    | ssh $ssh_opts "$target" 'rm -rf ~/otlet-spikes/bench ~/otlet-spikes/'"$spike"' && mkdir -p ~/otlet-spikes && tar -xf - -C ~/otlet-spikes'
# shellcheck disable=SC2086
ssh $ssh_opts "$target" "cd ~/otlet-spikes/$spike || exit 1; $*"
mkdir -p "$spike/results"
# shellcheck disable=SC2086
ssh $ssh_opts "$target" "cd ~/otlet-spikes/$spike && tar -cf - results 2>/dev/null || true" \
    | tar -xf - -C "$spike"
echo "Results copied to spikes/$spike/results/"

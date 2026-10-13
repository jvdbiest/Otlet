#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S2 on the measurement machine (docs/spikes/S2.md §3.7). Copies the bench and backend/src,
# then starts the whole scenario DETACHED on the machine (nohup): this PC may sleep.
#
#   OTLET_SSH_OPTS="-i ~/.ssh/otlet_nas" sh spikes/s2-queue/run-s2.sh <ssh target> [engine]
#   OTLET_SSH_OPTS="-i ~/.ssh/otlet_nas" sh spikes/s2-queue/run-s2.sh <ssh target> fetch
#
# engine: procrastinate (default) or dbos. "fetch" copies the results back.
# Progress on the machine: ~/otlet-s2/run.log
set -eu

target="${1:?usage: run-s2.sh <ssh target> [procrastinate|dbos|fetch]}"
engine="${2:-procrastinate}"
cd "$(dirname "$0")/../.."
ssh_opts="${OTLET_SSH_OPTS:-}"

if [ "$engine" = fetch ]; then
    mkdir -p spikes/s2-queue/results
    # shellcheck disable=SC2086
    ssh $ssh_opts "$target" 'cd ~/otlet-s2/spikes/s2-queue && tar -cf - results' \
        | tar -xf - -C spikes/s2-queue
    echo "Results copied to spikes/s2-queue/results/"
    exit 0
fi

# shellcheck disable=SC2086
tar -cf - --exclude=results --exclude=__pycache__ spikes/s2-queue backend/src \
    | ssh $ssh_opts "$target" 'rm -rf ~/otlet-s2 && mkdir -p ~/otlet-s2 && tar -xf - -C ~/otlet-s2'
# shellcheck disable=SC2086
ssh $ssh_opts "$target" "cd ~/otlet-s2/spikes/s2-queue && nohup sh remote-s2.sh $engine > ~/otlet-s2/run.log 2>&1 < /dev/null &"
echo "Started on $target; follow with: ssh $target tail -f otlet-s2/run.log"

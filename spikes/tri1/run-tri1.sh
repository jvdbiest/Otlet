#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# TRI1 on the work VM, in the worker container, detached: run-tri1.sh [--pilot]
# ~/s-tri1 holds items.jsonl and labels.csv; tri1.py sits beside this script.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
FOLDER="$HOME/s-tri1"
WORKER=otlet-x01-worker-1
sudo docker exec "$WORKER" mkdir -p /tmp/tri1
sudo docker cp "$HERE/tri1.py" "$WORKER:/tmp/tri1/tri1.py"
for file in items.jsonl labels.csv calls.jsonl; do
  [ -f "$FOLDER/$file" ] && sudo docker cp "$FOLDER/$file" "$WORKER:/tmp/tri1/$file"
done
sudo docker exec "$WORKER" python /tmp/tri1/tri1.py /tmp/tri1 "$@" >> "$FOLDER/run.out" 2>&1 || echo FAILED >> "$FOLDER/run.out"
sudo docker cp "$WORKER:/tmp/tri1/calls.jsonl" "$FOLDER/calls.jsonl"
sudo chown "$(id -u):$(id -g)" "$FOLDER/calls.jsonl"
echo finished >> "$FOLDER/run.out"

#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# TRI1 on the work VM, in the worker container, detached: run-tri1.sh [--pilot]
# ~/s-tri1 holds items.jsonl and labels.csv; tri1.py sits beside this script. One call per run of
# tri1.py, its result kept out of the container each time: /tmp is a tmpfs there, which docker cp
# does not see and a restart loses.
HERE=$(cd "$(dirname "$0")" && pwd)
FOLDER="$HOME/s-tri1"
WORKER=otlet-x01-worker-1
MAX_SECONDS=10800
in_worker() {
  sudo docker exec -i "$WORKER" sh -c "cat > /tmp/tri1/$2" < "$1"
}
one_call() {
  sudo docker exec "$WORKER" mkdir -p /tmp/tri1
  in_worker "$HERE/tri1.py" tri1.py
  for file in items.jsonl labels.csv calls.jsonl; do
    if [ -f "$FOLDER/$file" ]; then in_worker "$FOLDER/$file" "$file"; fi
  done
  sudo docker exec "$WORKER" python /tmp/tri1/tri1.py /tmp/tri1 --pilot >> "$FOLDER/run.out" 2>&1 || echo FAILED >> "$FOLDER/run.out"
  sudo docker exec "$WORKER" cat /tmp/tri1/calls.jsonl > "$FOLDER/calls.new" && mv "$FOLDER/calls.new" "$FOLDER/calls.jsonl"
}
start=$(date +%s)
while :; do
  one_call
  [ "$1" = "--pilot" ] && break
  last=$(tail -1 "$FOLDER/run.out")
  [ "$last" = "complete" ] || [ "$last" = "FAILED" ] && break
  if [ $(($(date +%s) - start)) -gt $MAX_SECONDS ]; then
    echo "max duration reached" >> "$FOLDER/run.out"
    break
  fi
  sleep 5
done
echo finished >> "$FOLDER/run.out"

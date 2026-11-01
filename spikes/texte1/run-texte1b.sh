#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# TEXTE1b on the work VM: a throwaway container of the worker's image, trafilatura installed in it
# alone. ~/s-texte1 holds pages.jsonl and receives results.jsonl. Usage: run-texte1b.sh [--summary]
HERE=$(cd "$(dirname "$0")" && pwd)
sudo docker run --rm --network bridge --user root --entrypoint sh \
  -v "$HOME/s-texte1:/data" -v "$HERE:/scripts:ro" otlet:dev -c '
  /opt/otlet/venv/bin/python -m ensurepip -q 2>/dev/null
  /opt/otlet/venv/bin/python -m pip install -q --target /tmp/extra "trafilatura==2.0.0" &&
  PYTHONPATH=/tmp/extra /opt/otlet/venv/bin/python /scripts/texte1b.py /data "$@"' sh "$@"

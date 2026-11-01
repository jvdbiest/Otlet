#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# TEXTE1b on the work VM. ~/s-texte1 holds pages.jsonl and receives results.jsonl. trafilatura lies
# in ~/s-texte1/extra, for the bench alone; the libraries of the image come first. A throwaway
# container of the worker's image, without network. Usage: run-texte1b.sh [--summary]
HERE=$(cd "$(dirname "$0")" && pwd)
if [ ! -d "$HOME/s-texte1/extra/trafilatura" ]; then
  sudo docker run --rm -v "$HOME/s-texte1:/data" python:3.13-slim \
    pip install -q --target /data/extra "trafilatura==2.0.0"
fi
sudo docker run --rm --network none --user root --entrypoint /opt/otlet/venv/bin/python \
  -e TEXTE1B_EXTRA=/data/extra -v "$HOME/s-texte1:/data" -v "$HERE:/scripts:ro" otlet:dev \
  /scripts/texte1b.py /data "$@"

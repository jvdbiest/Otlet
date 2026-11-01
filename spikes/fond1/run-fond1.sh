#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# FOND1 on the work VM, detached (nohup): extracts once, then the calls, one at a time.
# Needs OLLAMA_URL. Texts stay in ~/fond1, never versioned.
set -eu
cd "$(dirname "$0")"
FOLDER="$HOME/fond1"
DB=otlet-x01-db-1
mkdir -p "$FOLDER" && chmod 700 "$FOLDER"
if [ ! -s "$FOLDER/sources.jsonl" ]; then
    sudo docker exec "$DB" mkdir -p /tmp/fond1
    sudo docker cp extract.sql "$DB:/tmp/fond1/extract.sql"
    sudo docker exec "$DB" sh -c \
        "psql -q -U \$POSTGRES_USER -d \${POSTGRES_DB:-otlet} -f /tmp/fond1/extract.sql"
    sudo docker cp "$DB:/tmp/fond1/drafts.jsonl" "$FOLDER/"
    sudo docker cp "$DB:/tmp/fond1/sources.jsonl" "$FOLDER/"
    sudo docker exec "$DB" rm -rf /tmp/fond1
    sudo chown "$(id -u):$(id -g)" "$FOLDER"/*.jsonl
fi
python3 fond1.py "$FOLDER"
python3 fond1.py "$FOLDER" --summary > "$FOLDER/summary.json"
echo "### finished"

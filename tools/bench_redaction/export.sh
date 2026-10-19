#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copies the texts of the sources of the reference briefs (briefs.json) from a database of Otlet
# into data/sources.jsonl, on this machine only: they are articles of others, never versioned.
#
# Usage, from the repository root:
#   OTLET_SSH="ssh -i ~/.ssh/otlet_nas otlet@192.168.129.252" OTLET_DB=otlet-x01-db-1 \
#     sh tools/bench_redaction/export.sh
set -eu

cd "$(dirname "$0")"
mkdir -p data
urls=$(python3 -c "import json; print(','.join(sorted({u for b in json.load(open('briefs.json', encoding='utf-8'))['briefs'] for u in b['sources']})))" 2>/dev/null \
    || python -c "import json; print(','.join(sorted({u for b in json.load(open('briefs.json', encoding='utf-8'))['briefs'] for u in b['sources']})))")
# The same text the drafts use (articles_postgres.sources): the full text Otlet may use, else
# the summary; one row per URL, whatever the workspace that collected it.
query="SELECT DISTINCT ON (url) json_build_object('url', url, 'title', title,
  'text', coalesce(CASE WHEN text_status IN ('full_text', 'manual') THEN coalesce(text, feed_content) END, summary, title),
  'full_text', text_status IN ('full_text', 'manual'))
  FROM source_items WHERE url = ANY(string_to_array('$urls', ',')) ORDER BY url, collected_at DESC"
$OTLET_SSH "sudo docker exec -i $OTLET_DB psql -U otlet -d otlet -tA" <<EOF > data/sources.jsonl
$query
EOF
echo "$(wc -l < data/sources.jsonl) sources in tools/bench_redaction/data/sources.jsonl"

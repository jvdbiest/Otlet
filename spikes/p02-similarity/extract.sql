-- SPDX-License-Identifier: AGPL-3.0-or-later
-- P02 §3.1: reads the whole instance, writes nothing. One JSON object per line, for p02.py.
-- psql -v out=<folder inside the container> -f extract.sql
\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

\o :out/candidates.jsonl
select json_build_object(
    'id', id, 'source_id', source_id, 'lang', left(language, 2), 'title', title,
    'url', normalized_url,
    'text', coalesce(nullif(text, ''), summary, ''), 'published_at', published_at,
    'sample', text_status = 'full_text' and duplicate_of is null, 'meaning', meaning::text)
from source_items;

\o :out/drafts.jsonl
select json_build_object(
    'article_id', v.article_id, 'number', v.number, 'title', v.title, 'body_text', v.body_text,
    'model', v.model, 'language', b.language,
    'item_ids', (select json_agg(bi.item_id order by bi.position)
                 from brief_items bi where bi.brief_id = a.brief_id))
from article_versions v
join articles a on a.id = v.article_id
join briefs b on b.id = a.brief_id
where v.origin = 'ia';
\o

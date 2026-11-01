-- SPDX-License-Identifier: AGPL-3.0-or-later
-- FOND1 §3: reads the instance, writes nothing. One JSON object per line, for fond1.py.
\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on
\o /tmp/fond1/drafts.jsonl
select json_build_object('article', left(v.article_id::text, 8), 'body_text', v.body_text)
from article_versions v
where v.origin = 'ia' and v.number = 1
  and left(v.article_id::text, 8) in ('725cf52b', 'ebb23952', '5f41ec65', '726df3ee');
\o /tmp/fond1/sources.jsonl
select json_build_object('article', left(v.article_id::text, 8), 'n', s.ord, 'title', si.title,
    'text', regexp_replace(coalesce(nullif(si.text, ''), si.summary, ''), '\s+', ' ', 'g'))
from article_versions v
cross join lateral jsonb_array_elements(v.document -> 'attrs' -> 'sources') with ordinality s(e, ord)
join articles a on a.id = v.article_id
join brief_items bi on bi.brief_id = a.brief_id
join source_items si on si.id = bi.item_id and si.url = s.e ->> 'url'
where v.origin = 'ia' and v.number = 1
  and left(v.article_id::text, 8) in ('725cf52b', 'ebb23952', '5f41ec65', '726df3ee');
\o

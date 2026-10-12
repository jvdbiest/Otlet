# SPDX-License-Identifier: AGPL-3.0-or-later
"""The five reads of docs/spikes/S1.md §3.2, fixed before measurement.

Every read filters on workspace_id explicitly, as the application's data layer always does
(MD6); in the "rls" variant the policies filter a second time, in the "norls" variant they do
not apply (role with BYPASSRLS). The difference between the two is the cost of the RLS.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa

TRIAGE_FEED = sa.text(
    "SELECT id, title, score, published_at FROM items"
    " WHERE workspace_id = :ws AND triage_state = 'new'"
    "   AND published_at > now() - interval '7 days'"
    " ORDER BY score DESC, published_at DESC LIMIT 50"
)
FULL_TEXT = sa.text(
    "SELECT id, title, ts_rank(search, query) AS rank"
    " FROM items, websearch_to_tsquery('french', :terms) AS query"
    " WHERE workspace_id = :ws AND published_at > now() - interval '30 days'"
    "   AND search @@ query"
    " ORDER BY rank DESC LIMIT 20"
)
VECTOR_SETTINGS = (
    sa.text("SET LOCAL hnsw.ef_search = 40"),
    sa.text("SET LOCAL hnsw.iterative_scan = relaxed_order"),
)
VECTOR = sa.text(
    "SELECT id, item_id, embedding <=> CAST(:vector AS halfvec(384)) AS distance"
    " FROM passages WHERE workspace_id = :ws"
    " ORDER BY embedding <=> CAST(:vector AS halfvec(384)) LIMIT 20"
)
LIBRARY = sa.text(
    "SELECT a.id, a.title, a.updated_at,"
    "  (SELECT count(*) FROM article_sources s"
    "    WHERE s.workspace_id = a.workspace_id AND s.article_id = a.id) AS sources"
    " FROM articles a WHERE a.workspace_id = :ws AND a.state = :state"
    " ORDER BY a.updated_at DESC LIMIT 50"
)
ARTICLE = sa.text(
    "SELECT id, title, state, body, created_at, updated_at FROM articles"
    " WHERE workspace_id = :ws AND id = :id"
)
ARTICLE_SOURCES = sa.text(
    "SELECT i.id, i.title, i.published_at FROM article_sources s"
    " JOIN items i ON i.workspace_id = s.workspace_id AND i.id = s.item_id"
    " WHERE s.workspace_id = :ws AND s.article_id = :id"
)
WORDS = ("énergie", "climat", "budget", "réforme", "santé", "numérique", "transport",
         "élection", "entreprise", "recherche", "prix", "école", "banque", "europe")  # fmt: skip
STATES = ("draft", "review", "published")

Read = Callable[[sa.Connection, random.Random], Any]


def reads(manifest: dict[str, Any]) -> dict[str, Read]:
    ws = manifest["measured_workspace"]
    vectors: list[str] = manifest["query_vectors"]
    articles: list[str] = manifest["measured_articles"]

    def triage_feed(c: sa.Connection, rng: random.Random) -> Any:
        return c.execute(TRIAGE_FEED, {"ws": ws}).all()

    def full_text(c: sa.Connection, rng: random.Random) -> Any:
        terms = " ".join(rng.sample(WORDS, rng.randint(2, 3)))
        return c.execute(FULL_TEXT, {"ws": ws, "terms": terms}).all()

    def vector(c: sa.Connection, rng: random.Random) -> Any:
        for setting in VECTOR_SETTINGS:
            c.execute(setting)
        return c.execute(VECTOR, {"ws": ws, "vector": rng.choice(vectors)}).all()

    def library(c: sa.Connection, rng: random.Random) -> Any:
        return c.execute(LIBRARY, {"ws": ws, "state": rng.choice(STATES)}).all()

    def article(c: sa.Connection, rng: random.Random) -> Any:
        article_id = rng.choice(articles)
        row = c.execute(ARTICLE, {"ws": ws, "id": article_id}).one()
        return row, c.execute(ARTICLE_SOURCES, {"ws": ws, "id": article_id}).all()

    return {
        "L1_triage_feed": triage_feed,
        "L2_full_text": full_text,
        "L3_vector_top20": vector,
        "L4_library": library,
        "L5_article_detail": article,
    }

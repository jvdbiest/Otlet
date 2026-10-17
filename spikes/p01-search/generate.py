# SPDX-License-Identifier: AGPL-3.0-or-later
"""P01: the data set and the queries of the measure (docs/spikes/P01.md §3.1 and §3.3).

    python generate.py --admin-url postgresql://… --migrator-url postgresql+psycopg://…
                       [--smoke]

Reads data/corpus.jsonl (real items exported from the work VM, never versioned), creates the
schema of the product with its migrations, then loads 3 workspaces, 200 sources and 100,000
items built by recombining real titles and paragraphs (fixed seed). Writes data/queries.json,
data/manifest.json and results/corpus.json (statistics and SHA-256 of the corpus, no text).
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import random
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg

from otlet.collection.domain.model import search_config
from otlet.platform import migrations
from otlet.platform.config import Settings

HERE = Path(__file__).parent
SEED = 20261016
ITEMS, SOURCES = 100_000, 200
SHARES = (0.80, 0.15, 0.05)  # the measure runs in the first workspace
QUERIES_PER_FAMILY = 50
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
# Words too common to be a search on their own (both languages of the corpus).
STOP = set(
    "les des une pour par sur dans avec qui que est sont aux pas plus son ses leur leurs mais"
    " cette ces été être fait comme tout tous elle ils nous vous après avant entre sans sous"
    " the and for with that this from are was were has have had its their they into over"
    " after about than but not you his her who what when will would can could new more".split()
)


def escape(value: str) -> str:
    """A value for COPY in text format."""
    return value.replace("\\", "\\\\").replace("\t", " ").replace("\n", "\\n")


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) >= 80]


def load_corpus(path: Path) -> tuple[list[dict[str, str]], str]:
    raw = path.read_bytes()
    documents = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    return documents, hashlib.sha256(raw).hexdigest()


FRENCH_MARKS = set("les des une est pour dans avec qui sur par aux sont cette ont".split())
ENGLISH_MARKS = set("the and for with that this from are was were has have its their".split())


def language_of(document: dict[str, str]) -> str:
    """The language the feed declared, or, when it did not (items collected before U02), the one
    whose stop words are the most frequent in the text (P01 §3.1)."""
    declared = document.get("language")
    if declared:
        return declared.split("-")[0].lower()
    body = document.get("text") or document.get("summary") or ""
    words = WORD.findall(f"{document['title']} {body}".lower())
    french = sum(1 for w in words if w in FRENCH_MARKS)
    english = sum(1 for w in words if w in ENGLISH_MARKS)
    return "en" if english > french else "fr"


def pools(documents: list[dict[str, str]]) -> dict[str, dict[str, list[str]]]:
    """Titles and paragraphs per language (primary subtag)."""
    by_language: dict[str, dict[str, list[str]]] = collections.defaultdict(
        lambda: {"titles": [], "paragraphs": []}
    )
    for document in documents:
        language = language_of(document)
        pool = by_language[language]
        pool["titles"].append(document["title"])
        body = document.get("text") or document.get("summary") or ""
        pool["paragraphs"].extend(paragraphs(body))
    return {lang: pool for lang, pool in by_language.items() if pool["paragraphs"]}


def queries(documents: list[dict[str, str]], rng: random.Random) -> dict[str, list[str]]:
    titles = [d["title"] for d in documents]
    words_of = [[w.lower() for w in WORD.findall(t) if w.lower() not in STOP] for t in titles]
    # Ordered, not a set: the draw must not depend on the hash seed of the process (P01b §4).
    frequency = collections.Counter(w for words in words_of for w in dict.fromkeys(words))
    ranked = [w for w, _ in frequency.most_common()]
    frequent = ranked[: max(QUERIES_PER_FAMILY, len(ranked) // 100)]
    rare = [w for w, n in frequency.items() if 1 <= n <= 10]
    long_titles = [words for words in words_of if len(words) >= 3]
    pairs = [
        (a.lower(), b.lower())
        for t in titles
        for a, b in zip(WORD.findall(t), WORD.findall(t)[1:], strict=False)
        if a.lower() not in STOP and b.lower() not in STOP
    ]
    return {
        "Q1 mot fréquent": rng.sample(frequent, min(QUERIES_PER_FAMILY, len(frequent))),
        "Q2 mot rare": rng.sample(rare, min(QUERIES_PER_FAMILY, len(rare))),
        "Q3 deux ou trois mots": [
            " ".join(rng.sample(words, rng.choice((2, 3))))
            for words in rng.sample(long_titles, min(QUERIES_PER_FAMILY, len(long_titles)))
        ],
        "Q4 expression": [
            f'"{a} {b}"' for a, b in rng.sample(pairs, min(QUERIES_PER_FAMILY, len(pairs)))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-url", required=True, help="superuser, libpq form")
    parser.add_argument("--migrator-url", required=True, help="otlet_migrator, SQLAlchemy form")
    parser.add_argument("--smoke", action="store_true", help="1,000 items: a trial, not a measure")
    args = parser.parse_args()
    total = 1_000 if args.smoke else ITEMS

    documents, digest = load_corpus(HERE / "data" / "corpus.jsonl")
    rng = random.Random(SEED)
    by_language = pools(documents)
    languages = [lang for lang in by_language for _ in range(len(by_language[lang]["titles"]))]

    migrations.upgrade(
        Settings(ui_dir=None, run_dir=Path("/tmp"), database_url=args.migrator_url)  # noqa: S108
    )

    workspaces = [uuid.UUID(int=rng.getrandbits(128), version=4) for _ in SHARES]
    now = datetime.now(UTC)
    with psycopg.connect(args.admin_url, autocommit=False) as connection:
        cursor = connection.cursor()
        for number, workspace in enumerate(workspaces):
            cursor.execute(
                "INSERT INTO workspaces (id, name) VALUES (%s, %s)", (workspace, f"P01 {number}")
            )
        sources: list[tuple[uuid.UUID, uuid.UUID]] = []
        for number in range(SOURCES):
            workspace = rng.choices(workspaces, weights=SHARES)[0]
            source = uuid.UUID(int=rng.getrandbits(128), version=4)
            url = f"https://source{number}.example.org/feed"
            cursor.execute(
                "INSERT INTO sources (id, workspace_id, name, url, feed_url, interval_minutes,"
                " legal_status) VALUES (%s, %s, %s, %s, %s, 60, 'full_text')",
                (source, workspace, f"Source {number}", url, url),
            )
            sources.append((source, workspace))
        by_workspace = collections.defaultdict(list)
        for source, workspace in sources:
            by_workspace[workspace].append(source)

        buffer = io.StringIO()
        for number in range(total):
            workspace = rng.choices(workspaces, weights=SHARES)[0]
            source = rng.choice(by_workspace[workspace])
            language = rng.choice(languages)
            pool = by_language[language]
            text = "\n\n".join(rng.choices(pool["paragraphs"], k=rng.randint(3, 8)))
            published = now - timedelta(seconds=rng.randint(0, 90 * 24 * 3600))
            row = (
                str(uuid.UUID(int=rng.getrandbits(128), version=4)),
                str(workspace),
                str(source),
                "feed",
                f"p01-{number}",
                rng.choice(pool["titles"]),
                text[:300],
                text,
                "full_text",
                language,
                search_config(language),
                published.isoformat(),
                published.isoformat(),
                now.isoformat(),
            )
            buffer.write("\t".join(escape(value) for value in row))
            buffer.write("\n")
        buffer.seek(0)
        with cursor.copy(
            "COPY source_items (id, workspace_id, source_id, origin, guid, title, summary, text,"
            " text_status, language, search_config, published_at, collected_at, watched_at)"
            " FROM STDIN"
        ) as copy:
            while chunk := buffer.read(1 << 20):
                copy.write(chunk)
        connection.commit()
    with psycopg.connect(args.admin_url, autocommit=True) as connection:
        connection.execute("VACUUM ANALYZE")

    family_queries = queries(documents, random.Random(SEED + 1))
    data = HERE / "data"
    (data / "queries.json").write_text(
        json.dumps(family_queries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (data / "manifest.json").write_text(
        json.dumps({"measured_workspace": str(workspaces[0]), "items": total, "seed": SEED}),
        encoding="utf-8",
    )
    words = collections.Counter(
        w.lower() for d in documents for w in WORD.findall(f"{d['title']} {d.get('text') or ''}")
    )
    statistics = {
        "sha256": digest,
        "documents": len(documents),
        "full_text": sum(1 for d in documents if d.get("text")),
        "languages": {lang: len(pool["titles"]) for lang, pool in by_language.items()},
        "paragraphs": {lang: len(pool["paragraphs"]) for lang, pool in by_language.items()},
        "distinct_words": len(words),
        "items_generated": total,
    }
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    (results / ("corpus-smoke.json" if args.smoke else "corpus.json")).write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(statistics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

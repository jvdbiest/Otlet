# SPDX-License-Identifier: AGPL-3.0-or-later
"""S1.2: synthetic data set of docs/spikes/S1.md §3.1, reproducible from a seed.

    python generate.py --admin-url postgresql://postgres:…@db:5432/otlet [--seed 1] [--scale 1]

Loads with a superuser connection (row-level security does not apply to it), with COPY, after
recreating the schema from schema.sql with the migration role. Builds the indexes, then runs
VACUUM ANALYZE. `--scale` divides every volume, for a quick trial (never for a measure).
Prints the workspace ids and writes data/manifest.json for the reads.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg

HERE = Path(__file__).parent

SHARES = (0.80, 0.15, 0.05)
SOURCES, ITEMS, PASSAGES_PER_ITEM, ARTICLES, SOURCES_PER_ARTICLE = 200, 100_000, 3, 2_000, 3
DIMENSIONS, CENTERS = 384, 50
DAYS = 90
TRIAGE = (("new", 0.30), ("kept", 0.10), ("dismissed", 0.60))
ARTICLE_STATES = (("draft", 0.5), ("review", 0.2), ("published", 0.3))

# A small French vocabulary written for this test, drawn with a Zipf-like law.
WORDS = """
le la les un une des de du et à en dans pour sur par avec sans sous entre vers chez
plateforme veille source article rédaction publication marque espace sujet élément
politique économie énergie climat santé éducation culture sport justice sécurité
gouvernement parlement ministre commune région europe belgique france monde ville
entreprise marché emploi salaire budget dette croissance inflation banque crédit
recherche université étude rapport données analyse chiffre tendance hausse baisse
technologie logiciel intelligence artificielle modèle réseau internet numérique
transport train route vélo aéroport port énergie électricité gaz pétrole solaire
éolien nucléaire eau forêt agriculture alimentation prix consommateur ménage
hôpital médecin patient vaccin maladie soin prévention école élève enseignant
projet loi réforme accord négociation grève syndicat élection vote parti débat
annonce décision mesure plan stratégie objectif résultat impact risque crise
nouveau grand petit premier dernier important public privé national local
international social environnemental financier technique juridique éditorial
annoncer présenter publier décider proposer adopter lancer réduire augmenter
développer soutenir protéger critiquer analyser expliquer confirmer rappeler
selon après avant pendant depuis jusqu toujours encore déjà aussi très plus moins
année mois semaine jour matin soir heure semestre trimestre saison période
""".split()


def zipf_weights(count: int) -> list[float]:
    return [1 / (rank + 1) ** 1.05 for rank in range(count)]


class Text:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.weights = zipf_weights(len(WORDS))

    def words(self, count: int) -> str:
        return " ".join(self.rng.choices(WORDS, self.weights, k=count))

    def title(self) -> str:
        return self.words(self.rng.randint(5, 11)).capitalize()

    def body(self, size: int) -> str:
        sentences, length = [], 0
        while length < size:
            sentence = self.words(self.rng.randint(8, 22)).capitalize() + "."
            sentences.append(sentence)
            length += len(sentence) + 1
        return " ".join(sentences)


def pick(rng: random.Random, table: tuple[tuple[str, float], ...]) -> str:
    return rng.choices([v for v, _ in table], [w for _, w in table])[0]


def unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.4f}" for x in vector) + "]"


def counts(total: int, scale: int) -> list[int]:
    total //= scale
    parts = [int(total * share) for share in SHARES]
    parts[0] += total - sum(parts)
    return parts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-url", required=True, help="connexion superutilisateur (libpq)")
    parser.add_argument("--migrator-url", required=True, help="connexion du rôle de migration")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    text = Text(rng)
    now = datetime.now(UTC).replace(microsecond=0)
    started = time.monotonic()

    with psycopg.connect(args.migrator_url, autocommit=True) as connection:
        connection.execute((HERE / "schema.sql").read_text(encoding="utf-8"))

    centers = [unit([rng.gauss(0, 1) for _ in range(DIMENSIONS)]) for _ in range(CENTERS)]
    workspaces = [uuid.UUID(int=rng.getrandbits(128), version=4) for _ in SHARES]
    manifest: dict[str, object] = {
        "seed": args.seed,
        "scale": args.scale,
        "generated_at": now.isoformat(),
        "workspaces": [str(w) for w in workspaces],
        "measured_workspace": str(workspaces[0]),
    }
    item_ids: dict[uuid.UUID, list[uuid.UUID]] = {w: [] for w in workspaces}
    sample_vectors: list[str] = []

    with psycopg.connect(args.admin_url) as connection, connection.cursor() as cursor:
        with cursor.copy("COPY workspaces (id, name) FROM STDIN") as copy:
            for index, workspace in enumerate(workspaces):
                copy.write_row((workspace, f"Espace {index + 1}"))

        sources: dict[uuid.UUID, list[uuid.UUID]] = {}
        with cursor.copy("COPY sources (workspace_id, id, name, url) FROM STDIN") as copy:
            for workspace, count in zip(workspaces, counts(SOURCES, args.scale), strict=True):
                sources[workspace] = []
                for _ in range(max(count, 1)):
                    source = uuid.UUID(int=rng.getrandbits(128), version=4)
                    sources[workspace].append(source)
                    copy.write_row((workspace, source, text.title(), f"https://example.org/{source}"))

        print("items and passages…", flush=True)
        with cursor.copy(
            "COPY items (workspace_id, id, source_id, title, body, language, published_at,"
            " score, triage_state) FROM STDIN"
        ) as items:
            # (workspace, item, topic) only: vectors are drawn in a second pass, streamed.
            topics = []
            for workspace, count in zip(workspaces, counts(ITEMS, args.scale), strict=True):
                for _ in range(count):
                    item = uuid.UUID(int=rng.getrandbits(128), version=4)
                    item_ids[workspace].append(item)
                    published = now - timedelta(seconds=rng.randrange(DAYS * 86_400))
                    items.write_row(
                        (
                            workspace,
                            item,
                            rng.choice(sources[workspace]),
                            text.title(),
                            text.body(rng.randint(3_500, 6_500)),
                            "fr",
                            published,
                            round(rng.random(), 4),
                            pick(rng, TRIAGE),
                        )
                    )
                    topics.append((workspace, item, rng.randrange(CENTERS)))
        with cursor.copy(
            "COPY passages (workspace_id, item_id, position, embedding) FROM STDIN"
        ) as copy:
            for workspace, item, topic in topics:
                for position in range(PASSAGES_PER_ITEM):
                    vector = literal(unit([c + rng.gauss(0, 0.08) for c in centers[topic]]))
                    copy.write_row((workspace, item, position, vector))
                    if len(sample_vectors) < 1_000 and workspace == workspaces[0]:
                        sample_vectors.append(vector)
        del topics

        print("articles…", flush=True)
        article_ids: dict[uuid.UUID, list[str]] = {w: [] for w in workspaces}
        with cursor.copy(
            "COPY articles (workspace_id, id, title, state, body, created_at, updated_at)"
            " FROM STDIN"
        ) as articles:
            links = []
            for workspace, count in zip(workspaces, counts(ARTICLES, args.scale), strict=True):
                for _ in range(count):
                    article = uuid.UUID(int=rng.getrandbits(128), version=4)
                    article_ids[workspace].append(str(article))
                    created = now - timedelta(seconds=rng.randrange(DAYS * 86_400))
                    body = {
                        "type": "doc",
                        "content": [
                            {"type": "paragraph", "text": text.body(rng.randint(500, 900))}
                            for _ in range(5)
                        ],
                    }
                    articles.write_row(
                        (
                            workspace,
                            article,
                            text.title(),
                            pick(rng, ARTICLE_STATES),
                            json.dumps(body, ensure_ascii=False),
                            created,
                            created + timedelta(hours=rng.randint(0, 72)),
                        )
                    )
                    for item in rng.sample(item_ids[workspace], SOURCES_PER_ARTICLE):
                        links.append((workspace, article, item))
        with cursor.copy(
            "COPY article_sources (workspace_id, article_id, item_id) FROM STDIN"
        ) as copy:
            for row in links:
                copy.write_row(row)
        connection.commit()

        print("indexes…", flush=True)
        cursor.execute("SET maintenance_work_mem = '256MB'")
        cursor.execute(
            "CREATE INDEX passages_embedding ON passages"
            " USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
        cursor.execute("ALTER INDEX passages_embedding OWNER TO otlet_owner")
        connection.commit()

    with psycopg.connect(args.admin_url, autocommit=True) as connection:
        connection.execute("VACUUM ANALYZE")
        sizes = connection.execute(
            "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname"
        ).fetchall()
        database_size = connection.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        ).fetchone()

    manifest["rows"] = dict(sizes)
    manifest["database_size"] = database_size[0] if database_size else None
    manifest["load_seconds"] = round(time.monotonic() - started)
    manifest["measured_items"] = [str(i) for i in item_ids[workspaces[0]][:2_000]]
    manifest["measured_articles"] = article_ids[workspaces[0]]
    manifest["query_vectors"] = sample_vectors
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    summary = {k: v for k, v in manifest.items() if not k.startswith(("measured_", "query_"))}
    (HERE / "data" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# SPDX-License-Identifier: AGPL-3.0-or-later
"""REL1 (docs/spikes/REL1.md §3): a reading aid without a model. For each paragraph of a draft,
the sentences of the sources it cites that share its names, figures and rare words, best first:
do they show the author what reveals the known errors, without too much to read?

    python fid1-style:  python3 rel1.py freeze   (worker container, /data/frozen.json)
                        python3 rel1.py measure <folder>   (standard library)
"""

import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

DATA = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/data")
SINCE = "2026-11-07"
WS = "0150f5a4-a6bf-40db-ba7a-256b75d6d412"
SHOWN = 5  # sentences shown under a paragraph, at most
# Known errors (REL1 §3), fixed before the measure: (brief, paragraph pattern, revealing
# source sentence pattern).
CASES = {
    "MotoGP, Martín deuxième": (
        "0793d3f8-6577-4ea5-940c-aebb9165438b", r"terminant deuxi[eè]me",
        r"termine donc deuxi[eè]me, devant Martin|devance Jorge Martin dans le dernier tour",
    ),
    "MotoGP, Zarco 281 points": (
        "0793d3f8-6577-4ea5-940c-aebb9165438b", r"Johann Zarco, cinqui[eè]me",
        r"Ogura[^.]*281|281[^.]*Ogura",
    ),
    "Dana White devenu « elle »": (
        "83ba4b1f-e9cb-47c6-acb4-f47b7a97e072", r"photo la repr[ée]sentant", r"photo le montrant",
    ),
    "Printemps devenu avril": (
        "c22f90fc-83f4-48a2-95e9-ad89dde0b2cf", r"avril 2026", r"[Aa]u printemps 2026",
    ),
    "Citation à moitié traduite": (
        "dcbdf698-3075-42d2-93f2-bba3433a6f30", r"btw-nummer est het", r"[Zz]onder btw-nummer is het stilstand",
    ),
}
INVENTED = ("d6651caa-633b-4860-bc0f-a85eea990c3a", r"urgence|d[ée]centralis|coordination|inqui[ée]tude")
SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")
WORD = re.compile(r"[\w'’-]+")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
STOP = set(
    """le la les un une des du de d l au aux en et ou à a est sont été être avoir ont il elle
    ils elles on ce cette ces cet qui que quoi dont où pour par sur dans avec sans plus moins
    pas ne se sa son ses leur leurs lui y mais comme aussi selon après avant entre lors très""".split()
)


def fold(text: str) -> str:
    bare = unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
    return "".join(c for c in bare if not unicodedata.combining(c))


def tokens(text: str) -> set[str]:
    out = set()
    for w in WORD.findall(text):
        f = fold(w)
        if len(f) > 2 and f not in STOP:
            out.add(f[:6] if not f.isdigit() else f)  # a light stem: « déuxième » and « deuxièmes »
    out |= {n.replace(",", ".") for n in NUMBER.findall(text)}
    return out


def names(text: str) -> set[str]:
    return {fold(w) for w in re.findall(r"\b[A-ZÀ-ÖØ-Ý][\w'’-]{2,}", text)}


def shown(paragraph: str, sources: list[str], idf: dict[str, float]) -> list[tuple[float, str]]:
    """The source sentences that share the most with the paragraph: names and figures weigh
    three times a word; nothing shared, nothing shown."""
    wanted, wanted_names = tokens(paragraph), names(paragraph)
    figures = {n.replace(",", ".") for n in NUMBER.findall(paragraph)}
    scored = []
    for source in sources:
        for sentence in SENTENCE.split(source):
            if len(sentence) < 20:
                continue
            have = tokens(sentence)
            score = sum(idf.get(t, 1.0) for t in wanted & have)
            score += 3 * len(wanted_names & names(sentence)) + 3 * len(figures & have)
            if score > 0:
                scored.append((score, sentence.strip()))
    scored.sort(key=lambda x: -x[0])
    # Only what shares enough: half the best score at least.
    best = scored[0][0] if scored else 0
    return [s for s in scored if s[0] >= best / 2][:SHOWN]


def freeze() -> None:
    from uuid import UUID

    import sqlalchemy as sa

    from otlet.platform import database
    from otlet.platform.config import Settings
    from otlet.platform.database import workspace_transaction

    engine = database.create_engine(Settings.from_env().require_database_url())
    with workspace_transaction(engine, UUID(WS)) as c:
        rows = c.execute(sa.text(
            "SELECT b.id::text AS brief, b.title, v.number, v.document,"
            " (SELECT json_agg(json_build_array(i.title, coalesce(i.text, i.summary, ''))"
            "  ORDER BY bi.position) FROM brief_items bi JOIN source_items i ON i.id = bi.item_id"
            "  WHERE bi.brief_id = b.id) AS sources"
            " FROM briefs b JOIN articles a ON a.brief_id = b.id"
            " JOIN article_versions v ON v.article_id = a.id"
            " WHERE v.origin = 'ia' AND b.created_at >= :since ORDER BY b.created_at, v.number"
        ), {"since": SINCE}).all()
    out = []
    for r in rows:
        sources = [f"{t}. {x}" for t, x in (r.sources or [])]
        keys = (r.document.get("attrs") or {}).get("sources") or []
        out.append({
            "brief": r.brief, "title": r.title, "version": r.number, "sources": sources,
            "keys": keys, "paragraphs": _paragraphs(r.document),
        })
    json.dump(out, (DATA / "frozen.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(len(out), "drafts frozen")


def _paragraphs(document: dict) -> list[dict]:
    """Each paragraph, its text without references, and the keys of the sources it cites."""
    out = []
    for block in document.get("content", []):
        if block.get("type") != "paragraph":
            continue
        text, cited = [], []
        for node in block.get("content") or []:
            refs = [m for m in node.get("marks", []) if m.get("type") == "source_ref"]
            if refs:
                cited.append(refs[0].get("attrs", {}).get("source"))
            elif node.get("type") == "text":
                text.append(node.get("text", ""))
        out.append({"text": "".join(text).strip(), "cited": cited})
    return out


def _cited_sources(draft: dict, paragraph: dict) -> list[str]:
    """The texts of the sources a paragraph cites; all of them for the lead (it cites none)."""
    sources = draft["sources"]
    if not paragraph["cited"]:
        return sources
    picked = []
    for key in paragraph["cited"]:
        n = int(re.sub(r"\D", "", key or "") or 0)
        if 1 <= n <= len(sources):
            picked.append(sources[n - 1])
    return picked or sources


def measure() -> None:
    drafts = json.load((DATA / "frozen.json").open(encoding="utf-8"))
    documents = [s for d in drafts for s in d["sources"]]
    df = Counter(t for s in documents for t in tokens(s))
    idf = {t: math.log((1 + len(documents)) / (1 + n)) + 1 for t, n in df.items()}
    lines, counts, empty, total = [], [], 0, 0
    for d in drafts:
        for p in d["paragraphs"]:
            if len(p["text"]) < 40:
                continue
            got = shown(p["text"], _cited_sources(d, p), idf)
            total += 1
            counts.append(len(got))
            empty += not got
    print(f"paragraphs {total}; sentences shown per paragraph {sum(counts) / max(total, 1):.1f};"
          f" paragraphs with nothing shown {empty} ({empty / max(total, 1):.0%})")
    revealed = 0
    for name, (brief, where, reveal) in CASES.items():
        found = None
        for d in drafts:
            if d["brief"] != brief:
                continue
            for p in d["paragraphs"]:
                if re.search(where, p["text"]):
                    got = shown(p["text"], _cited_sources(d, p), idf)
                    found = next((n + 1 for n, (_, s) in enumerate(got) if re.search(reveal, s)), 0)
                    lines.append(f"## {name} (v{d['version']})\nPARAGRAPH: {p['text'][:300]}\n" + "\n".join(
                        f"  {n + 1}. [{score:.1f}] {s[:300]}" for n, (score, s) in enumerate(got)))
                    break
            if found is not None:
                break
        revealed += bool(found)
        print(f"{name}: {'revealed at rank ' + str(found) if found else 'not revealed' if found == 0 else 'paragraph not found'}")
    print(f"known errors revealed: {revealed} of {len(CASES)}")
    brief, invented = INVENTED
    for d in drafts:
        if d["brief"] == brief:
            for p in d["paragraphs"]:
                if re.search(invented, p["text"]):
                    got = shown(p["text"], _cited_sources(d, p), idf)
                    lines.append(f"## Invented paragraph (police, v{d['version']})\nPARAGRAPH: {p['text'][:300]}\n" + "\n".join(
                        f"  {n + 1}. [{score:.1f}] {s[:300]}" for n, (score, s) in enumerate(got)))
    (DATA / "shown.txt").write_text("\n\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    {"freeze": freeze, "measure": measure}[sys.argv[1]]()

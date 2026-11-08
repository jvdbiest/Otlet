# SPDX-License-Identifier: AGPL-3.0-or-later
"""REL2 (docs/spikes/REL2.md §3): the reading aid at the level of the sentence, and the signal
« peu soutenu ». Uses the frozen drafts and the scoring of REL1 (rel1.py beside this file).

    python3 rel2.py measure <folder>   (standard library; frozen.json of REL1 in <folder>)
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import rel1

DATA = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/data")
SHOWN = 3  # sentences shown under a sentence, at most
PERTURBATIONS_MAX = 60
WEAK_SHARE = 0.10  # the paragraphs whose best support is in the lowest tenth: « à vérifier »
# The five errors of REL1, with patterns widened before REL2 (they are no longer blind: REL1
# showed their sentences), and the sentence of the draft that holds each error.
CASES = {
    "MotoGP, Martín deuxième": (
        "0793d3f8-6577-4ea5-940c-aebb9165438b", r"terminant deuxi",
        r"deuxi[eè]me place qui lui a [eé]chapp|termine donc deuxi[eè]me, devant Martin|devance Jorge Martin",
    ),
    "MotoGP, Zarco 281 points": (
        "0793d3f8-6577-4ea5-940c-aebb9165438b", r"Johann Zarco, cinqui", r"Ogura[^.]*281|281[^.]*Ogura",
    ),
    "Dana White devenu « elle »": (
        "83ba4b1f-e9cb-47c6-acb4-f47b7a97e072", r"photo la repr", r"photo le montrant",
    ),
    "Printemps devenu avril": (
        "c22f90fc-83f4-48a2-95e9-ad89dde0b2cf", r"avril 2026", r"printemps 2026",
    ),
    "Citation à moitié traduite": (
        "dcbdf698-3075-42d2-93f2-bba3433a6f30", r"btw-nummer est het", r"[Zz]onder btw-nummer is het stilstand",
    ),
}
# The paragraphs of the police brief (RB1, question 8) that invent what the sources do not say.
INVENTED = ("d6651caa-633b-4860-bc0f-a85eea990c3a", (r"situations d'urgence", r"inqui[ée]tude de nombreux agents"))
MONTHS = "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split()
RANKS = "premier deuxième troisième quatrième cinquième sixième septième huitième neuvième dixième".split()


def idf_of(drafts: list[dict]) -> dict[str, float]:
    documents = [s for d in drafts for s in d["sources"]]
    df = Counter(t for s in documents for t in rel1.tokens(s))
    return {t: math.log((1 + len(documents)) / (1 + n)) + 1 for t, n in df.items()}


def shown(sentence: str, sources: list[str], idf: dict[str, float]) -> list[tuple[float, str]]:
    return rel1.shown(sentence, sources, idf)[:SHOWN]


def sentences(paragraph: str) -> list[str]:
    return [s for s in rel1.SENTENCE.split(paragraph) if len(s) >= 40]


def perturbed(sentence: str) -> list[tuple[str, str]]:
    """Errors a model makes, written into a correct sentence: (kind, new sentence)."""
    out = []
    for m in re.finditer(r"\b\d+\b", sentence):
        n = int(m.group(0))
        if not 1900 <= n <= 2100:
            out.append(("chiffre", sentence[: m.start()] + str(n + 1) + sentence[m.end():]))
            break
    for i, month in enumerate(MONTHS):
        if re.search(rf"\b{month}\b", sentence):
            out.append(("mois", re.sub(rf"\b{month}\b", MONTHS[(i + 1) % 12], sentence, count=1)))
            break
    for i, rank in enumerate(RANKS[:-1]):
        if re.search(rf"\b{rank}\b", sentence):
            out.append(("rang", re.sub(rf"\b{rank}\b", RANKS[i + 1], sentence, count=1)))
            break
    if re.search(r"\bil\b", sentence):
        out.append(("pronom", re.sub(r"\bil\b", "elle", sentence, count=1)))
    # Two different people or places: the last word of two runs of capitalized words.
    runs = re.findall(r"(?:\b[A-ZÀ-ÖØ-Ý][a-zà-ÿ'’-]{2,}\s?)+", sentence)
    found = list(dict.fromkeys(r.split()[-1] for r in runs if len(r.split()[-1]) > 3))
    if len(found) >= 2:
        a, b = found[0], found[1]
        hole = chr(0)
        out.append(("noms échangés", sentence.replace(a, hole, 1).replace(b, a, 1).replace(hole, b, 1)))
    return out


def measure() -> None:
    drafts = json.load((DATA / "frozen.json").open(encoding="utf-8"))
    idf = idf_of(drafts)
    total = empty = 0
    best_by_paragraph = []
    trials = Counter()
    kept = Counter()
    for d in drafts:
        for p in d["paragraphs"]:
            if len(p["text"]) < 40:
                continue
            sources = rel1._cited_sources(d, p)
            best = 0.0
            for s in sentences(p["text"]):
                got = shown(s, sources, idf)
                total += 1
                empty += not got
                best = max(best, got[0][0] if got else 0.0)
                # Perturbations: the sentence the aid shows first for the sentence as written,
                # is it still shown for the sentence with an error?
                if got and sum(trials.values()) < PERTURBATIONS_MAX:
                    support = got[0][1]
                    for kind, wrong in perturbed(s):
                        if sum(trials.values()) >= PERTURBATIONS_MAX:
                            break
                        trials[kind] += 1
                        kept[kind] += any(x == support for _, x in shown(wrong, sources, idf))
            best_by_paragraph.append((best, d["brief"], d["version"], p["text"]))
    print(f"sentences {total}; with nothing shown {empty} ({empty / max(total, 1):.0%})")
    done = sum(trials.values())
    print(f"perturbations: support still shown {sum(kept.values())}/{done}"
          f" ({sum(kept.values()) / max(done, 1):.0%}); by kind "
          + ", ".join(f"{k} {kept[k]}/{trials[k]}" for k in trials))
    revealed = 0
    lines = []
    for name, (brief, where, reveal) in CASES.items():
        result = "sentence not found"
        for d in drafts:
            if d["brief"] != brief:
                continue
            for p in d["paragraphs"]:
                hit = next((s for s in sentences(p["text"]) if re.search(where, s)), None)
                if hit:
                    got = shown(hit, rel1._cited_sources(d, p), idf)
                    rank = next((n + 1 for n, (_, x) in enumerate(got) if re.search(reveal, x)), 0)
                    revealed += bool(rank)
                    result = f"revealed at rank {rank}" if rank else "not revealed"
                    lines.append(f"## {name}\nSENTENCE: {hit}\n" + "\n".join(
                        f"  {n + 1}. [{sc:.1f}] {x[:300]}" for n, (sc, x) in enumerate(got)))
                    break
            if result != "sentence not found":
                break
        print(f"{name}: {result}")
    print(f"known errors revealed: {revealed} of {len(CASES)}")
    ordered = sorted(best_by_paragraph)
    cut = ordered[int(len(ordered) * WEAK_SHARE)][0] if ordered else 0
    weak = [x for x in ordered if x[0] < cut]
    brief, patterns = INVENTED
    for pattern in patterns:
        flagged = any(b == brief and re.search(pattern, t) for _, b, _, t in weak)
        print(f"invented « {pattern} »: {'flagged' if flagged else 'not flagged'}")
    print(f"weak support: {len(weak)} of {len(ordered)} paragraphs under {cut:.1f}")
    lines.append("## Paragraphs « peu soutenus »\n" + "\n".join(
        f"  [{b:.1f}] {t[:250]}" for b, _, _, t in weak))
    (DATA / "rel2.txt").write_text("\n\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    {"measure": measure}[sys.argv[1]]()

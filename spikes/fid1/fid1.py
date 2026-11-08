# SPDX-License-Identifier: AGPL-3.0-or-later
"""FID1 (docs/spikes/FID1.md §3): does a check without a model catch a name tied to the wrong
place, rank or figure in a draft, as « Martín deuxième » when the sources say third?

    python3 fid1.py freeze   (in the worker container: /data/frozen.json, the drafts and sources)
    python3 fid1.py measure  (anywhere, standard library: results on stdout, flags in flags.txt)
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

DATA = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/data")
SINCE = "2026-11-07"
REFERENCE = ("0793d3f8-6577-4ea5-940c-aebb9165438b", "Martín")  # brief, name (RB1 §9)
MUTATIONS_MAX = 40
VARIANTS = ("V1", "V2", "V3")

# Words written with a capital that name nobody.
NOT_NAMES = set(
    """le la les l un une des du de d au aux en à a selon cette ce ces cet il elle ils elles on
    après avant pendant dans par pour sur sous avec sans mais et ou donc or ni car lors depuis
    malgré cependant toutefois ainsi enfin puis alors ensuite si quand comme dès entre face
    lundi mardi mercredi jeudi vendredi samedi dimanche janvier février mars avril mai juin
    juillet août septembre octobre novembre décembre grand prix course sprint pole""".split()
)
RANK_WORDS = {
    "premier": 1, "premiere": 1, "1er": 1, "1re": 1, "1ere": 1, "vainqueur": 1, "victoire": 1,
    "deuxieme": 2, "second": 2, "seconde": 2, "2e": 2, "2eme": 2,
    "troisieme": 3, "3e": 3, "3eme": 3, "quatrieme": 4, "4e": 4, "4eme": 4,
    "cinquieme": 5, "5e": 5, "5eme": 5, "sixieme": 6, "6e": 6, "septieme": 7, "7e": 7,
    "huitieme": 8, "8e": 8, "neuvieme": 9, "9e": 9, "dixieme": 10, "10e": 10,
    "onzieme": 11, "11e": 11, "douzieme": 12, "12e": 12,
}
# What separates the actor of a value from the others in a clause (« deuxième, devant Martin »).
CLAUSE = re.compile(r"[,;:()«»\"]|\b(?:devant|derrière|derriere|après|apres|avant|face à|par|contre|que|qui)\b")
SENTENCE = re.compile(r"(?<=[.!?…])\s+")
NAME = re.compile(r"\b[A-ZÀ-ÖØ-Ý][\w'’-]+(?:\s+(?:de|di|da|del|van|von|le|la)?\s*[A-ZÀ-ÖØ-Ý][\w'’-]+)*")
NUMBER = re.compile(r"\b\d{1,3}(?:[  .]\d{3})+(?:,\d+)?\b|\b\d+(?:[.,]\d+)?\b")


def fold(text: str) -> str:
    bare = unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
    return "".join(c for c in bare if not unicodedata.combining(c))


def names(text: str) -> list[str]:
    out = []
    for m in NAME.finditer(text):
        words = [w for w in m.group(0).split() if fold(w) not in NOT_NAMES]
        if words:
            out.append(words[-1])  # the surname: « Jorge Martín » is « Martín »
    return out


def values(text: str) -> list[str]:
    folded = fold(text)
    out = [f"rang {n}" for w, n in RANK_WORDS.items() if re.search(rf"\b{w}\b", folded)]
    for m in NUMBER.finditer(text):
        digits = re.sub(r"[  .]", "", m.group(0)).replace(",", ".")
        if not re.fullmatch(r"(19|20)\d\d", digits):  # a year is a date: U05 checks dates
            out.append(digits)
    return out


def units(text: str, variant: str) -> list[str]:
    """V1: the sentence; V2: the clause (V3 pairs within the sentence, by position)."""
    sentences = SENTENCE.split(text)
    if variant == "V1":
        return sentences
    return [c for s in sentences for c in CLAUSE.split(s) if c and c.strip()]


def _positions(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """The names and values of a sentence, each with where it starts."""
    found_names = []
    for m in NAME.finditer(text):
        words = [w for w in m.group(0).split() if fold(w) not in NOT_NAMES]
        if words:
            found_names.append((m.start(), words[-1]))
    found_values = []
    folded = fold(text)
    for word, n in RANK_WORDS.items():
        for m in re.finditer(rf"\b{word}\b", folded):
            found_values.append((m.start(), f"rang {n}"))
    for m in NUMBER.finditer(text):
        digits = re.sub(r"[  .]", "", m.group(0)).replace(",", ".")
        if not re.fullmatch(r"(19|20)\d\d", digits):
            found_values.append((m.start(), digits))
    return found_names, found_values


def pairs(text: str, variant: str) -> list[tuple[str, str, str]]:
    if variant == "V3":
        # Each value with the name written last before it, in its sentence: « Martín …,
        # terminant deuxième » is Martín's; « Il termine deuxième, devant Martin » is nobody's.
        out = []
        for sentence in SENTENCE.split(text):
            found_names, found_values = _positions(sentence)
            for at, value in found_values:
                before = [name for start, name in found_names if start < at]
                if before:
                    out.append((before[-1], value, sentence.strip()))
        return out
    out = []
    for unit in units(text, variant):
        for name in names(unit):
            for value in values(unit):
                out.append((name, value, unit.strip()))
    return out


def supported(name: str, value: str, source_units: list[str], variant: str = "V1") -> bool:
    key = fold(name)
    if variant == "V3":
        return any(
            fold(n) == key and v == value for unit in source_units for n, v, _ in pairs(unit, "V3")
        )
    for unit in source_units:
        folded = fold(unit)
        if re.search(rf"\b{re.escape(key)}\b", folded) and value in values(unit):
            return True
    return False


def check(draft: str, sources: list[str], variant: str) -> list[tuple[str, str, str]]:
    source_units = [u for s in sources for u in units(s, "V1" if variant == "V3" else variant)]
    known = fold(" ".join(sources))
    return [
        (name, value, unit)
        for name, value, unit in pairs(draft, variant)
        # A name no source writes is U05's (unsupported); here, names the sources write.
        if re.search(rf"\b{re.escape(fold(name))}\b", known)
        and not supported(name, value, source_units, variant)
    ]


def mutations(draft: str, sources: list[str]) -> list[tuple[str, str]]:
    """Sentences of the draft with two names and two different values: (sentence, the same with
    the two values swapped). The same for every variant; a variant catches a swap when the
    mutated sentence has a flag the sentence as written has not."""
    out = []
    for sentence in SENTENCE.split(draft):
        found_names, found_values = _positions(sentence)
        if len({n for _, n in found_names}) < 2:
            continue
        distinct = []
        for _, value in sorted(found_values):
            if value not in distinct:
                distinct.append(value)
        if len(distinct) < 2:
            continue
        raw1, raw2 = _raw(sentence, distinct[0]), _raw(sentence, distinct[1])
        if raw1 is None or raw2 is None or raw1 == raw2:
            continue
        hole = chr(0)
        swapped = sentence.replace(raw1, hole, 1).replace(raw2, raw1, 1).replace(hole, raw2, 1)
        out.append((sentence, swapped))
    return out


def _raw(sentence: str, value: str) -> str | None:
    """The words of the sentence that wrote a value, to swap them."""
    if value.startswith("rang "):
        n = int(value.split()[1])
        for word in re.findall(r"[\w']+", sentence):
            if RANK_WORDS.get(fold(word)) == n:
                return word
        return None
    for m in NUMBER.finditer(sentence):
        if re.sub(r"[  .]", "", m.group(0)).replace(",", ".") == value:
            return m.group(0)
    return None


def freeze() -> None:
    import sqlalchemy as sa

    from otlet.platform import database
    from otlet.platform.config import Settings

    engine = database.create_engine(Settings.from_env().require_database_url())
    with engine.connect() as c:
        c.execute(sa.text("SET row_security = off"))
        rows = c.execute(sa.text(
            "SELECT b.id::text AS brief, b.title, v.number, v.document,"
            " (SELECT json_agg(json_build_array(i.title, coalesce(i.text, i.summary, ''))"
            "  ORDER BY bi.position) FROM brief_items bi JOIN source_items i ON i.id = bi.item_id"
            "  WHERE bi.brief_id = b.id) AS sources"
            " FROM briefs b JOIN articles a ON a.brief_id = b.id"
            " JOIN article_versions v ON v.article_id = a.id"
            " WHERE v.origin = 'ia' AND b.created_at >= :since ORDER BY b.created_at, v.number"
        ), {"since": SINCE}).all()
    out = [
        {"brief": r.brief, "title": r.title, "version": r.number, "text": _text(r.document),
         "sources": [f"{t}. {x}" for t, x in (r.sources or [])]}
        for r in rows
    ]
    json.dump(out, (DATA / "frozen.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(len(out), "drafts frozen")


def _text(document: dict) -> str:
    """The lead and paragraphs of a draft, without its headings and references."""
    def inner(node: dict) -> str:
        return "".join(
            c.get("text", "") if c.get("type") == "text" else inner(c)
            for c in node.get("content") or []
            if not (c.get("type") == "text" and any(m.get("type") == "source_ref" for m in c.get("marks", [])))
        )
    return "\n".join(
        inner(block) for block in document.get("content", []) if block.get("type") == "paragraph"
    )


def measure() -> None:
    drafts = json.load((DATA / "frozen.json").open(encoding="utf-8"))
    report = []
    for variant in VARIANTS:
        flags = [(d, f) for d in drafts for f in check(d["text"], d["sources"], variant)]
        reference = [
            f for d, f in flags if d["brief"] == REFERENCE[0] and fold(f[0]) == fold(REFERENCE[1])
            and f[1] == "rang 2"
        ]
        caught = total = 0
        for d in drafts:
            for written, mutated in mutations(d["text"], d["sources"]):
                if total >= MUTATIONS_MAX:
                    break
                total += 1
                before = {f[:2] for f in check(written, d["sources"], variant)}
                caught += bool({f[:2] for f in check(mutated, d["sources"], variant)} - before)
        report.append(
            f"{variant}: MotoGP « Martín deuxième » flagged: {bool(reference)}; mutations caught"
            f" {caught}/{total}; flags on the drafts {len(flags)} for {len(drafts)} drafts"
            f" ({len(flags) / max(len(drafts), 1):.1f} per draft)"
        )
        with (DATA / f"flags-{variant}.txt").open("w", encoding="utf-8") as out:
            for d, (name, value, unit) in flags:
                out.write(f"{d['title'][:60]} v{d['version']} | {name} ↔ {value} | {unit[:220]}\n")
    print("\n".join(report))


if __name__ == "__main__":
    {"freeze": freeze, "measure": measure}[sys.argv[1]]()

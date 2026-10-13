# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3.1: writes the corpus of docs/spikes/S3.md §3.1 (CC0-1.0) and its expected elements.

    python make_corpus.py     -> corpus/written/*.json, corpus/ai/*.md,
                                 corpus/pasted/*.html (+ .sources.json), corpus/expected.json

Every document is first described in an abstract form (blocks, inline runs, sources), then
emitted in the form of its group. expected.json is derived from the abstract form, never from
our renderer or from a parser, so that a defect of the pipeline cannot hide itself.
Texts use French typography (’ « » —) so that WordPress's typographic filter has nothing to
change. Seeded: the corpus is identical on every run.
"""

from __future__ import annotations

import json
import random
from html import escape
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
CORPUS = HERE / "corpus"
SEED = 2026

TOPICS = [
    ("la rénovation énergétique des écoles", "énergie"),
    ("le budget participatif de la commune", "budget"),
    ("les pistes cyclables entre deux villages", "mobilité"),
    ("la fermeture d’une ligne de bus du soir", "transport"),
    ("l’ouverture d’une maison médicale de garde", "santé"),
    ("la numérisation des archives communales", "numérique"),
    ("le prix de l’eau pour les ménages", "eau"),
    ("la création d’un jardin partagé", "environnement"),
    ("la sécurité aux abords d’une gare", "sécurité"),
    ("le recrutement d’enseignants remplaçants", "éducation"),
]
OPENINGS = [
    "Le conseil a présenté mardi soir le projet consacré à {t}.",
    "Après plusieurs mois de concertation, le dossier sur {t} revient sur la table.",
    "Les habitants étaient nombreux à suivre le débat sur {t}.",
    "Le rapport publié cette semaine éclaire {t} sous un jour nouveau.",
]
DETAILS = [
    "Le calendrier prévoit une première phase dès le printemps, puis une évaluation à l’automne.",
    "Les montants annoncés restent provisoires tant que les subsides régionaux ne sont pas confirmés.",
    "Plusieurs associations demandent que les données de suivi soient rendues publiques.",
    "L’opposition salue l’intention mais s’interroge sur le coût d’entretien à long terme.",
    "Un comité de suivi réunira élus, agents et riverains deux fois par an.",
    "Les premiers retours d’expérience venus d’autres communes sont jugés encourageants.",
]
QUOTES = [
    "Nous voulons des résultats mesurables, pas seulement des annonces.",
    "Chaque euro dépensé doit pouvoir être expliqué aux habitants.",
    "Le projet n’a de sens que s’il est construit avec celles et ceux qui l’utiliseront.",
    "Les chiffres sont encourageants, mais il faut rester prudent.",
]
PUBLISHERS = ["Le Courrier local", "Bulletin communal", "Revue des territoires", "Agence régionale"]
LIST_ITEMS = [
    "une étude de faisabilité",
    "un appel à projets ouvert aux associations",
    "une consultation en ligne de six semaines",
    "un budget de fonctionnement distinct",
    "un rapport annuel public",
]


def sources_for(rng: random.Random, index: int, count: int) -> list[dict[str, str]]:
    result = []
    for number in range(1, count + 1):
        day = rng.randint(1, 28)
        result.append(
            {
                "id": f"S{number}",
                "titre": f"Dossier {index:02d}, document {number}",
                "editeur": rng.choice(PUBLISHERS),
                "date": f"2026-0{rng.randint(1, 9)}-{day:02d}",
                "url": f"https://exemple.org/dossiers/{index:02d}/document-{number}",
            }
        )
    return result


def spec(index: int, rng: random.Random, variant: str) -> dict[str, Any]:
    """Abstract document: blocks of ("h", level, runs) ("p", runs) ("list", ordered, items)
    ("quote", text, source); a run is (text, marks) with marks among bold, italic,
    ("link", href), ("src", id)."""
    topic, word = TOPICS[index % len(TOPICS)]
    sources = sources_for(rng, index, rng.randint(2, 4))
    link = f"https://exemple.org/{word}/fiche-{index:02d}"
    blocks: list[tuple[Any, ...]] = [
        ("p", [(rng.choice(OPENINGS).format(t=topic), [])]),
        ("h", 2, [(f"Ce que prévoit le projet sur {word}", [])]),
        (
            "p",
            [
                ("Selon les documents consultés, ", []),
                ("le coût total reste à confirmer", [("src", "S1")]),
                (". ", []),
                (rng.choice(DETAILS), []),
            ],
        ),
        (
            "p",
            [
                ("La ", []),
                ("fiche détaillée", [("link", link)]),
                (" est disponible en ligne, et ", []),
                ("plusieurs points restent ouverts", ["bold"]),
                (".", []),
            ],
        ),
        ("quote", rng.choice(QUOTES), "S2"),
        ("h", 3, [("Les prochaines étapes", [])]),
        ("list", variant == "ordered", [(item, []) for item in rng.sample(LIST_ITEMS, 3)]),
        ("p", [(rng.choice(DETAILS), ["italic"])]),
    ]
    if variant == "nested":
        blocks[6] = ("list", False, [(LIST_ITEMS[0], [LIST_ITEMS[1], LIST_ITEMS[2]]), (LIST_ITEMS[3], [])])
    if variant == "short":
        blocks = [blocks[1], blocks[2], blocks[3], blocks[4]]
    if variant == "long":
        blocks += [("h", 2, [("Contexte", [])])] + [("p", [(d, [])]) for d in DETAILS]
    if variant == "link_in_heading":
        blocks[1] = ("h", 2, [("Le projet sur ", []), (word, [("link", link + "#titre")])])
    if variant == "quote_last":
        blocks.append(("quote", QUOTES[0], "S1"))
    if variant == "special_chars":
        blocks.append(("p", [("Coût : 1 200 € (soit 12 % du budget) ; échéance < 2027 & au-delà > 2030.", [])]))
    return {"index": index, "sources": sources, "blocks": blocks}


# --- emitters ---------------------------------------------------------------------------------

def runs_to_nodes(runs: list[tuple[str, list[Any]]]) -> list[dict[str, Any]]:
    nodes = []
    for text, marks in runs:
        node: dict[str, Any] = {"type": "text", "text": text}
        out = []
        for mark in marks:
            if mark in ("bold", "italic"):
                out.append({"type": mark})
            elif mark[0] == "link":
                out.append({"type": "link", "attrs": {"href": mark[1]}})
            else:
                out.append({"type": "source_ref", "attrs": {"source": mark[1]}})
        if out:
            node["marks"] = out
        nodes.append(node)
    return nodes


def to_json(document: dict[str, Any], origins: list[str]) -> dict[str, Any]:
    content = []
    for number, block in enumerate(document["blocks"], start=1):
        attrs = {"id": f"b{number}", "origine": origins[(number - 1) % len(origins)]}
        kind = block[0]
        if kind == "h":
            content.append({"type": "heading", "attrs": {**attrs, "level": block[1]}, "content": runs_to_nodes(block[2])})
        elif kind == "p":
            content.append({"type": "paragraph", "attrs": attrs, "content": runs_to_nodes(block[1])})
        elif kind == "quote":
            content.append(
                {
                    "type": "citation",
                    "attrs": {**attrs, "source": block[2]},
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": block[1]}]}],
                }
            )
        else:
            items = []
            for text, children in block[2]:
                item: dict[str, Any] = {"type": "list_item", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}
                if children:
                    item["content"].append(
                        {
                            "type": "bullet_list",
                            "content": [
                                {"type": "list_item", "content": [{"type": "paragraph", "content": [{"type": "text", "text": c}]}]}
                                for c in children
                            ],
                        }
                    )
                items.append(item)
            content.append({"type": "ordered_list" if block[1] else "bullet_list", "attrs": attrs, "content": items})
    return {"type": "doc", "attrs": {"version_schema": 1, "langue": "fr", "sources": document["sources"]}, "content": content}


def runs_to_md(runs: list[tuple[str, list[Any]]]) -> str:
    out = []
    for text, marks in runs:
        for mark in marks:
            if mark == "bold":
                text = f"**{text}**"
            elif mark == "italic":
                text = f"*{text}*"
            elif mark[0] == "link":
                text = f"[{text}]({mark[1]})"
            else:
                text = f"[[{text}]]{{src:{mark[1]}}}"
        out.append(text)
    return "".join(out)


def to_markdown(document: dict[str, Any]) -> str:
    lines = [f"<!-- sources: {json.dumps(document['sources'], ensure_ascii=False)} -->"]
    for block in document["blocks"]:
        kind = block[0]
        if kind == "h":
            lines += ["#" * block[1] + " " + runs_to_md(block[2]), ""]
        elif kind == "p":
            lines += [runs_to_md(block[1]), ""]
        elif kind == "quote":
            lines += [f"> {block[1]} {{cite:{block[2]}}}", ""]
        else:
            for number, (text, children) in enumerate(block[2], start=1):
                lines.append(f"{number}. {text}" if block[1] else f"- {text}")
                lines += [f"  - {c}" for c in children]
            lines.append("")
    return "\n".join(lines)


def runs_to_html(runs: list[tuple[str, list[Any]]], flavour: str) -> str:
    out = []
    for text, marks in runs:
        html = escape(text, quote=False)
        for mark in marks:
            if mark == "bold":
                html = f"<b>{html}</b>" if flavour == "word" else f'<span style="font-weight:700;">{html}</span>'
            elif mark == "italic":
                html = f"<i>{html}</i>" if flavour == "word" else f'<span style="font-style:italic;">{html}</span>'
            elif mark[0] == "link":
                html = f'<a href="{mark[1]}">{html}</a>'
            # source references do not exist in Word or Google Docs: the text stays plain
        if flavour == "word":
            html = f'<span lang=FR-BE style=\'mso-ansi-language:FR-BE\'>{html}</span>'
        else:
            html = f'<span style="font-size:11pt;font-family:Arial,sans-serif;color:#000000;">{html}</span>'
        out.append(html)
    return "".join(out)


def source_by_id(document: dict[str, Any], source_id: str) -> dict[str, str]:
    return next(s for s in document["sources"] if s["id"] == source_id)


def to_word(document: dict[str, Any]) -> str:
    body = []
    for block in document["blocks"]:
        kind = block[0]
        if kind == "h":
            body.append(f"<h{block[1]}><span lang=FR-BE>{runs_to_html(block[2], 'word')}</span><o:p></o:p></h{block[1]}>")
        elif kind == "p":
            body.append(f"<p class=MsoNormal>{runs_to_html(block[1], 'word')}<o:p></o:p></p>")
        elif kind == "quote":
            source = source_by_id(document, block[2])
            body.append(f"<p class=MsoQuote><i>{escape(block[1])}</i><o:p></o:p></p>")
            body.append(f"<p class=MsoNormal>— <a href=\"{source['url']}\">{escape(source['titre'])}</a><o:p></o:p></p>")
        else:
            entries = []
            for text, children in block[2]:
                entries.append((1, text))
                entries += [(2, c) for c in children]
            for number, (level, text) in enumerate(entries, start=1):
                position = "First" if number == 1 else ("Last" if number == len(entries) else "Middle")
                marker = f"{number}." if block[1] else "·"
                body.append(
                    f"<p class=MsoListParagraphCxSp{position} style='text-indent:-18.0pt;mso-list:l0 level{level} lfo1'>"
                    f"<![if !supportLists]><span style='font-family:Symbol'>{marker}<span style='font:7.0pt \"Times New Roman\"'>&nbsp;&nbsp;</span></span><![endif]>"
                    f"<span lang=FR-BE>{escape(text)}</span><o:p></o:p></p>"
                )
    return (
        "<html xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:w=\"urn:schemas-microsoft-com:office:word\">"
        "<head><meta name=Generator content=\"Microsoft Word 15\"><style><!-- p.MsoNormal {margin:0cm;} --></style>"
        "<!--[if gte mso 9]><xml><w:WordDocument><w:View>Normal</w:View></w:WordDocument></xml><![endif]--></head>"
        "<body lang=FR-BE style='tab-interval:35.4pt'><!--StartFragment-->"
        + "".join(body)
        + "<!--EndFragment--></body></html>"
    )


def to_gdocs(document: dict[str, Any]) -> str:
    body = []
    for block in document["blocks"]:
        kind = block[0]
        if kind == "h":
            body.append(f'<h{block[1]} dir="ltr" style="line-height:1.38;margin-top:18pt;">{runs_to_html(block[2], "gdocs")}</h{block[1]}>')
        elif kind == "p":
            body.append(f'<p dir="ltr" style="line-height:1.38;margin-top:0pt;margin-bottom:0pt;">{runs_to_html(block[1], "gdocs")}</p>')
        elif kind == "quote":
            source = source_by_id(document, block[2])
            body.append(f'<p dir="ltr" style="line-height:1.38;margin-left:36pt;margin-top:0pt;"><span style="font-style:italic;">{escape(block[1])}</span></p>')
            body.append(f'<p dir="ltr" style="line-height:1.38;margin-top:0pt;"><span>— </span><a href="{source["url"]}" style="text-decoration:none;"><span style="color:#1155cc;text-decoration:underline;">{escape(source["titre"])}</span></a></p>')
        else:
            tag = "ol" if block[1] else "ul"
            items = []
            for text, children in block[2]:
                items.append(f'<li dir="ltr" aria-level="1" style="list-style-type:disc;"><p dir="ltr" role="presentation"><span>{escape(text)}</span></p></li>')
                items += [f'<li dir="ltr" aria-level="2" style="list-style-type:circle;"><p dir="ltr" role="presentation"><span>{escape(c)}</span></p></li>' for c in children]
            body.append(f'<{tag} style="margin-top:0;margin-bottom:0;">{"".join(items)}</{tag}>')
    return (
        '<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-5f1e2a3b-7fff-1c2d-3e4f-000000000000">'
        + "".join(body)
        + "</b><br class=\"Apple-interchange-newline\">"
    )


# --- expected elements ---------------------------------------------------------------------------

def text_of_runs(runs: list[tuple[str, list[Any]]]) -> str:
    return "".join(text for text, _ in runs)


def expected(document: dict[str, Any], mention: bool, keeps_source_refs: bool) -> dict[str, Any]:
    headings, links, citations = [], [], []
    for block in document["blocks"]:
        if block[0] == "h":
            headings.append({"level": block[1], "text": text_of_runs(block[2])})
        if block[0] in ("h", "p"):
            for text, marks in block[-1]:
                for mark in marks:
                    if isinstance(mark, tuple) and mark[0] == "link":
                        links.append({"href": mark[1], "text": text})
        if block[0] == "quote":
            citations.append({"text": block[1], "source": source_by_id(document, block[2])["url"]})
    return {
        "headings": headings,
        "links": links,
        "citations": citations,
        "sources": [{"href": s["url"], "titre": s["titre"]} for s in document["sources"]],
        "mention_ia": mention,
        "source_refs_kept": keeps_source_refs,
    }


def main() -> None:
    rng = random.Random(SEED)
    expectations: dict[str, Any] = {}
    variants = ["plain", "ordered", "nested", "short", "long", "link_in_heading", "quote_last", "special_chars", "plain", "ordered"]
    for folder in ("written", "ai", "pasted"):
        (CORPUS / folder).mkdir(parents=True, exist_ok=True)

    for number in range(10):  # written: JSON, some blocks partly AI
        document = spec(number + 1, rng, variants[number])
        origins = ["humain"] if number % 2 == 0 else ["humain", "ia_modifie"]
        name = f"written/{number + 1:02d}.json"
        (CORPUS / name).write_text(json.dumps(to_json(document, origins), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        expectations[name] = expected(document, mention=number % 2 == 1, keeps_source_refs=True)

    for number in range(10):  # AI outputs: restricted Markdown
        document = spec(number + 11, rng, variants[number])
        name = f"ai/{number + 11:02d}.md"
        (CORPUS / name).write_text(to_markdown(document) + "\n", encoding="utf-8")
        expectations[name] = expected(document, mention=True, keeps_source_refs=True)

    for number in range(10):  # pasted: 5 Word, 5 Google Docs
        document = spec(number + 21, rng, variants[number])
        flavour = "word" if number < 5 else "gdocs"
        name = f"pasted/{number + 21:02d}-{flavour}.html"
        html = to_word(document) if flavour == "word" else to_gdocs(document)
        (CORPUS / name).write_text(html + "\n", encoding="utf-8")
        (CORPUS / name.replace(".html", ".sources.json")).write_text(
            json.dumps(document["sources"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        expectations[name] = expected(document, mention=False, keeps_source_refs=False)

    (CORPUS / "expected.json").write_text(json.dumps(expectations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (CORPUS / "LICENSE").write_text(
        "Corpus de la preuve S3, écrit pour elle (textes, sources fictives, balisage).\n"
        "Dédié au domaine public : CC0-1.0, https://creativecommons.org/publicdomain/zero/1.0/\n",
        encoding="utf-8",
    )
    print(f"{len(expectations)} documents written to {CORPUS}")


if __name__ == "__main__":
    main()

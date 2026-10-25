# SPDX-License-Identifier: AGPL-3.0-or-later
"""A2 bench, operation « reconstituer »: a chronology or a thematic synthesis from several sources.

1. The model splits the question into facets (three to five) and says the form: chronologie or
   synthèse.
2. The model extracts, from the numbered articles, the lines of each facet: a short fact, when,
   where, and the exact passage. The engine keeps a line only when its passage is in the article.
3. The model writes the AI analysis from the kept lines only, never from the articles; each
   sentence names its lines and says whether it is a deduction. The engine flags a sentence
   whose figures, dates or proper names are in none of its lines.
4. The engine computes, per facet, its sources and the concordance of its figures, then the
   confidence: forte (each facet has two sources or more, none diverges), moyenne (a facet
   holds on one source), faible (a facet is empty or diverges).

Appended to replay.py and bench.py, run in the worker container:
  cat replay.py bench.py reconstitute.py | docker compose exec -T -e A2_BENCH=1 -e RECONSTITUER=1 \
      worker python - <workspace id>
DUMP=1 prints the articles given to the model, to establish the reference by hand.
"""

import re

from otlet.assistant.domain.qualify import (
    BATCH, NOT_JUDGED, QUALIFY_SCHEMA, QUALIFY_SYSTEM, Line, Verdict, qualify_message, read_qualify,
)
from otlet.assistant.domain.terms import publisher_country

RIOTS = ("pillages", "pillé", "pillards", "casseurs", "émeutes", "émeutiers", "rellen", "plunderingen")
RECONSTITUTIONS = [
    ("R1", "Quand la tempête Austen est-elle apparue en Belgique, par où est-elle passée et est-elle finie ?",
     [AUSTEN]),
    ("R2", "Que trouve-t-on comme informations concernant la culture des OGM, et que mettent en avant "
           "les articles parlant de leur utilisation intensive ?",
     [("OGM", "organismes génétiquement modifiés", "génétiquement modifié", "ggo", "genetisch gemodificeerd", "GMO")]),
    ("R3", "Que s'est-il passé lors des émeutes à Bruxelles : quand, dans quelles rues, et comment la "
           "ville se prépare-t-elle pour la suite ?",
     [RIOTS, BXL]),
    ("R4", "Que disent les articles sur le budget fédéral, et quelles critiques mettent-ils en avant ?",
     [("budget", "begroting"), ("fédéral", "Arizona", "federale", "federal")]),
]

FACETS_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. L'auteur demande une reconstitution à partir de "
    "plusieurs articles. Dis sa forme : « chronologie » (ce qui s'est passé, quand, où, comment cela "
    "a fini) ou « synthèse » (ce que disent les articles sur un thème, ce qu'ils mettent en avant, "
    "les points de vue). Puis découpe la question en 3 à 5 volets, chacun une question courte à "
    "laquelle des articles peuvent répondre. Pour une chronologie, par exemple « Début », « Lieux », "
    "« Fin » ; pour une synthèse, par exemple « Ce qui est dit », « Ce qui est mis en avant », "
    "« Critiques ». Les volets suivent la question de l'auteur, sans en ajouter d'autres."
)
FACETS_SCHEMA = {
    "type": "object",
    "properties": {
        "forme": {"type": "string", "enum": ["chronologie", "synthèse"]},
        "volets": {"type": "array", "items": {"type": "object", "properties": {
            "nom": {"type": "string"}, "question": {"type": "string"}}, "required": ["nom", "question"]}},
    },
    "required": ["forme", "volets"],
}
LINES_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. Pour chaque volet, relève dans les articles "
    "numérotés, et en eux seuls, ce qui y répond : une ligne par information, avec le numéro du "
    "volet, le numéro de l'article, l'information en quelques mots (avec ses chiffres tels "
    "qu'écrits), quand et où (tels que l'article les donne, « non précisé » sinon), et l'extrait "
    "exact qui la contient (copié mot pour mot, une phrase). Pour une synthèse, l'information est "
    "ce que l'article affirme ou met en avant, attribué à qui le dit. N'ajoute rien que les "
    "articles ne disent pas ; un volet sans réponse n'a aucune ligne. Ne garde d'un article que ce "
    "qui porte sur le sujet de la question. Une ligne dit ce que l'article apprend, jamais le nom "
    "du volet ni « n'est pas mentionné ». Pas de date ni de jour que l'article n'écrit pas : "
    "« vendredi » reste « vendredi »."
)
LINES_SCHEMA = {
    "type": "object",
    "properties": {"lignes": {"type": "array", "items": {"type": "object", "properties": {
        "volet": {"type": "integer"}, "article": {"type": "integer"}, "information": {"type": "string"},
        "quand": {"type": "string"}, "ou": {"type": "string"}, "extrait": {"type": "string"}},
        "required": ["volet", "article", "information", "quand", "ou", "extrait"]}}},
    "required": ["lignes"],
}
ANALYSIS_SYSTEM = (
    "Tu es le Reporter d'Otlet. Écris une analyse courte (3 à 6 phrases) qui répond à la question "
    "de l'auteur à partir des lignes numérotées, et d'elles seules : tu ne vois pas les articles. "
    "Pour chaque phrase, donne les numéros des lignes qui la portent. Une déduction (ce que les "
    "lignes laissent penser sans le dire) est permise, mais marque-la comme déduction et "
    "formule-la comme telle (« semble », « laisse penser »). Aucun chiffre, aucune date, aucun "
    "lieu, aucun nom qui ne soit dans les lignes. Des moments différents désignent des événements "
    "différents, pas des sources en désaccord. Si les lignes ne suffisent pas pour répondre, "
    "dis-le en une phrase."
)
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {"phrases": {"type": "array", "items": {"type": "object", "properties": {
        "texte": {"type": "string"}, "lignes": {"type": "array", "items": {"type": "integer"}},
        "deduction": {"type": "boolean"}}, "required": ["texte", "lignes", "deduction"]}}},
    "required": ["phrases"],
}

# Words that may start with a capital without being a name, at the start of a sentence or not.
COMMON = set(fold(w) for w in (
    "Le La Les Un Une Des D'après Selon Après Avant Puis Ensuite Enfin Aucun Aucune Il Elle Ils "
    "Elles Ce Cette Ces Les Sources Plusieurs Certains Certaines Dans En Au Aux Du De Lors Alors "
    "Toutefois Cependant Mais Et Si Pour Par Sur L'alerte La tempête Belgique").split())


def unsupported(sentence: str, support: str) -> list[str]:
    """The figures and the names of a sentence that its lines do not hold (ADR-0043 §10)."""
    held = fold(support)
    missing = [n for n in re.findall(r"\d+(?:[.,]\d+)?", sentence) if n not in support]
    # The first word of a sentence is a capital by grammar (« Proposition de geler… »): not checked.
    for word in re.findall(r"(?<![.!?] )(?<!^)\b[A-ZÀ-Ý][\w'’-]+", sentence.strip()):
        name = fold(word.replace("’", "'"))
        if name not in COMMON and name.split("'")[-1] not in held:
            missing.append(word)
    return missing


DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
          "octobre", "novembre", "decembre"]


def dated(published: datetime, text: str) -> str:
    """The date of an article and the dates its weekdays can name: the last such day up to the
    article, or the next one after it (« samedi » written on Friday 23 October is the 24th)."""
    days = [published]
    for name in set(re.findall(r"\w+", fold(text))) & set(DAYS):
        back = (published.weekday() - DAYS.index(name)) % 7
        days += [published - timedelta(days=back), published + timedelta(days=(7 - back) % 7 or 7)]
    return " ".join(f"{d.day} {MONTHS[d.month - 1]} {DAYS[d.weekday()]}" for d in days)


def wrong_days(text: str, year: int) -> list[str]:
    """« mercredi 23 octobre » when the 23rd of October is a Friday: a day the calendar denies."""
    out = []
    for day, number, month in re.findall(r"(\w+) (\d{1,2}) (\w+)", fold(text)):
        if day in DAYS and month in MONTHS:
            try:
                real = datetime(year, MONTHS.index(month) + 1, int(number)).weekday()
            except ValueError:
                continue
            if DAYS[real] != day:
                out.append(f"{day} {number} {month} (un {DAYS[real]})")
    return out


def added(information: str, extract: str, glossary: list, asked: str) -> list[str]:
    """The figures and names of a line that its passage does not hold: the model added them.
    The glossary counts (« Bruxelles » is in a passage that writes « Brussel »), and so do the
    words of the question and of its facets (« Austen », « Début »)."""
    held = fold(extract)
    same = [t for e in glossary if any(f" {fold(x)} " in f" {held} " for x in e.terms) for t in e.terms]
    return unsupported(information, " ".join([extract, *same, asked]))


def empty(information: str, extract: str, asked: str) -> bool:
    """A line that tells nothing of its passage: only the words of the question and its facets
    (« Lieux traversés par la tempête Austen »), or what the article does not say."""
    if "pas mentionn" in fold(information):
        return True
    words = {w for w in re.findall(r"\w+", fold(information)) if len(w) > 3}
    return not (words - set(re.findall(r"\w+", fold(asked)))) & set(re.findall(r"\w+", fold(extract)))


def confidence(form: str, facets: list[dict], kept: list[dict], glossary: list) -> tuple[str, list[str]]:
    """Forte, moyenne or faible, with its reasons, from the kept lines of each facet. Figures
    are set against each other only in a chronology, and only between lines that measure the
    same thing (a word in common): in a synthesis, 10 billions by 2029 and 4 billions in 2027
    are two proposals, not two sources in disagreement."""
    reasons, level = [], "forte"
    for n, facet in enumerate(facets, 1):
        lines = [line for line in kept if line["volet"] == n]
        sources = {line["source"] for line in lines}
        state, pairs = concordance(
            [{**line, "chiffre": line["information"], "mesure": line["information"]} for line in lines
             if form == "chronologie" and any(ch.isdigit() for ch in line["information"])], glossary)
        if not lines:
            reasons.append(f"« {facet['nom']} » : aucune source"); level = "faible"
        elif pairs:
            reasons.append(f"« {facet['nom']} » : les sources divergent ({pairs[0][1]} contre {pairs[0][2]})")
            level = "faible"
        elif len(sources) == 1:
            reasons.append(f"« {facet['nom']} » ne tient qu'à une source ({next(iter(sources))})")
            level = "moyenne" if level == "forte" else level
    return level, reasons


def reconstitute(workspace: UUID) -> None:
    engine = db.create_engine(Settings.from_env().require_database_url())
    store = PostgresAssistantStore(engine)
    glossary = [stored.entry for stored in store.glossary(workspace)]
    since = datetime.now(UTC) - timedelta(days=30)
    total = store.total_items(workspace, since)
    only = os.environ.get("ONLY")
    for key, question, concepts in RECONSTITUTIONS:
        if only and key not in only.split(","):
            continue
        widened = widen([Concept(t[0], tuple(t)) for t in concepts], glossary)
        counts = store.term_counts(workspace, [t for w in widened for t in w.all_terms], since)
        found = sorted(store.candidates(workspace, too_general(widened, counts, total), since, 400),
                       key=lambda c: c.dated)
        # The sort of A1b first (« traite », « proche », « hors sujet » on title and summary): only
        # the matter goes to the extraction; « proche » only when « traite » is short.
        judged: dict = {}
        for start in range(0, len(found), BATCH):
            batch = found[start:start + BATCH]
            lines = [Line(c.title, c.summary, c.language, c.publisher, publisher_country(c.url)) for c in batch]
            raw, _ = chat(QUALIFY_SYSTEM, qualify_message(question, "", lines), QUALIFY_SCHEMA)
            verdicts = read_qualify(json.dumps(raw), len(batch))
            judged |= {c.id: verdicts.get(n, NOT_JUDGED).verdict for n, c in enumerate(batch, 1)}
        matter = [c for c in found if judged[c.id] == Verdict.TRAITE]
        # « Proche » completes the matter, it never makes it: without one article that « traite »
        # the subject, the Reporter does not find (the spiruline is no answer about GMOs).
        if matter and len(matter) < 5:
            matter += [c for c in found if judged[c.id] == Verdict.PROCHE]
        matter.sort(key=lambda c: c.dated)
        # A chronology needs the whole period: the articles are taken evenly along it.
        step = max(1, len(matter) / ARTICLES)
        articles = [matter[int(i * step)] for i in range(min(ARTICLES, len(matter)))]
        out = sum(1 for v in judged.values() if v == Verdict.HORS_SUJET)
        print(f"\n=================== {key} : {question}\n    {len(found)} articles trouvés, "
              f"{out} hors sujet selon le tri, {len(articles)} lus")
        if not articles:
            print("    je ne trouve pas d'article sur ce sujet : ni lignes ni analyse")
            continue
        with workspace_transaction(engine, workspace) as connection:
            rows = {r.id: r for r in connection.execute(
                sa.text("SELECT i.id, i.title, coalesce(i.text, i.feed_content, i.summary, '') AS body,"
                        " s.name AS publisher, i.published_at FROM source_items i"
                        " LEFT JOIN sources s ON s.id = i.source_id WHERE i.id = ANY(:ids)"),
                {"ids": [c.id for c in articles]}).all()}
        texts = [f"{rows[c.id].title}. {rows[c.id].body}"[:BODY] for c in articles]
        numbered = "\n\n".join(
            f"[{n}] {rows[c.id].publisher}, {rows[c.id].published_at:%d/%m %H:%M} — {t}"
            for n, (c, t) in enumerate(zip(articles, texts), 1))
        if os.environ.get("DUMP"):
            print(numbered)
            continue
        plan, seconds = chat(FACETS_SYSTEM, f"Question : {question}", FACETS_SCHEMA)
        facets = plan.get("volets", [])[:5]
        print(f"--- forme {plan.get('forme')} ({seconds} s) ; volets : " + " ; ".join(
            f"{n}. {f['nom']}" for n, f in enumerate(facets, 1)))
        if not facets:
            continue
        asked = "\n".join(f"{n}. {f['nom']} : {f['question']}" for n, f in enumerate(facets, 1))
        # One call per facet: a local model holds one facet at a time better than all of them.
        rows_by_facet, seconds = [], 0.0
        for v, facet in enumerate(facets, 1):
            answer, spent = chat(LINES_SYSTEM, f"Question : {question}\n\nVolets :\n1. {facet['nom']} : "
                                 f"{facet['question']}\n\nArticles :\n{numbered}", LINES_SCHEMA)
            seconds += spent
            rows_by_facet += [(v, row) for row in answer.get("lignes", [])]
        seconds = round(seconds, 1)
        words = f"{question} {asked}"
        kept, dropped, flagged, emptied = [], 0, [], 0
        for v, row in rows_by_facet:
            n = row.get("article", 0)
            text = texts[n - 1] if 1 <= n <= len(texts) else ""
            if not (text and 1 <= v <= len(facets) and fold(row.get("extrait", ""))[:80] in fold(text)):
                dropped += 1
                continue
            c = articles[n - 1]
            line = {k: str(row.get(k, "")) for k in ("information", "quand", "ou", "extrait")} | {
                "volet": v, "article": n, "source": rows[c.id].publisher, "date": rows[c.id].published_at}
            if empty(line["information"], line["extrait"], words):
                emptied += 1
                continue
            # Guards without a model: what the line says beyond its article (the passage anchors
            # the line; a list of places may run over the next sentences), and days the calendar
            # denies. Such a line is shown to the author, never given to the analysis.
            extra = added(line["information"], text, glossary, words) + wrong_days(
                f"{line['information']} {line['quand']}", line["date"].year)
            if extra:
                flagged.append((line, extra))
                continue
            # One passage gives one line: the same passage under a second facet is a repeat.
            if any(k["article"] == n and fold(k["extrait"]) == fold(line["extrait"]) for k in kept):
                continue
            kept.append(line)
        kept.sort(key=lambda line: (line["volet"], line["date"]))
        print(f"--- lignes ({seconds} s) : {len(kept)} gardées, {dropped} retirées (extrait absent), "
              f"{emptied} vides, {len(flagged)} à vérifier (ajout hors extrait)")
        for line, extra in flagged:
            print(f"      à vérifier [{line['article']}] {line['source']} | {line['information']} | ajout : {', '.join(extra)}")
        for v, facet in enumerate(facets, 1):
            print(f"    {facet['nom']}")
            for line in (line for line in kept if line["volet"] == v):
                print(f"      [{line['article']}] {line['source']}, {line['date']:%d/%m} | {line['information']} | {line['quand']} | {line['ou']}")
                print(f"          « {line['extrait'][:160]} »")
        level, reasons = confidence(plan.get("forme", ""), facets, kept, glossary)
        print(f"    confiance calculée : {level}" + (f" ({' ; '.join(reasons)})" if reasons else "")
              + f" ; {len({l['article'] for l in kept})} articles utilisés")
        if not kept:
            print("    analyse : aucune ligne, pas d'analyse")
            continue
        listed = "\n".join(
            f"L{i} ({line['source']}, article du {line['date']:%d/%m}) {line['information']} | quand : {line['quand']} | où : {line['ou']}"
            for i, line in enumerate(kept, 1))
        analysis, seconds = chat(ANALYSIS_SYSTEM, f"Question : {question}\n\nLignes :\n{listed}", ANALYSIS_SCHEMA)
        print(f"--- analyse IA ({seconds} s)")
        for sentence in analysis.get("phrases", []):
            cited = [kept[i - 1] for i in sentence.get("lignes", []) if 1 <= i <= len(kept)]
            # The analysis may use what the cited articles hold, their dates, and the dates their
            # weekdays name (« samedi » in an article of Sunday 18 October is 17 October).
            support = " ".join(f"{texts[l['article'] - 1]} {l['source']} {dated(l['date'], texts[l['article'] - 1])}"
                               for l in cited)
            missing = (unsupported(sentence.get("texte", ""), support) + wrong_days(sentence.get("texte", ""), 2026)
                       if cited else ["aucune ligne citée"])
            mark = "déduction" if sentence.get("deduction") else "fait"
            flag = f" | SANS APPUI : {', '.join(missing)}" if missing else ""
            print(f"      ({mark}, L{sentence.get('lignes')}) {sentence.get('texte')}{flag}")


reconstitute(UUID(sys.argv[1]))

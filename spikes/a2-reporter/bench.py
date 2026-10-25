# SPDX-License-Identifier: AGPL-3.0-or-later
"""A2 bench: the Reporter with the author's model, on the twelve conversations of replay.py.

1. Each question is translated by the model into an operation (chercher, restreindre, élargir,
   trier, fait, agir) and its terms; the set those terms give is compared with the reference
   set (the hand translation of replay.py).
2. Each question of fact is answered by the model from the reference set, as a table (figure,
   what it measures, when, where, source, passage), then checked without a model: the passage
   must be in the article, and the figure in the passage.

Appended to replay.py and run in the worker container:
  cat replay.py bench.py | docker compose exec -T worker python - <workspace id>
(replay.py then does not run its own main: A2_BENCH is set below before it is reached.)
"""

import json
import os
import time
import unicodedata
import urllib.request

OLLAMA = os.environ.get("OLLAMA", "http://192.168.129.45:11434")
MODEL = os.environ.get("MODEL", "qwen3:14b")
ARTICLES = 15
BODY = 2500

OPERATION_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste qui aide un auteur à explorer sa veille de "
    "presse belge (français, néerlandais, anglais). Traduis la dernière question de l'auteur en "
    "une opération sur l'ensemble d'articles courant :\n"
    "- « chercher » : un nouveau sujet ; donne 1 ou 2 concepts, chacun avec ses termes ;\n"
    "- « restreindre » : garder ceux qui parlent aussi d'autre chose (un lieu, un aspect) ; donne "
    "le concept ajouté et ses termes ; ou une langue (fr, nl, en) ;\n"
    "- « élargir » : ajouter des termes à un concept existant ;\n"
    "- « trier » : garder ceux qui portent vraiment sur le sujet ;\n"
    "- « fait » : une question dont la réponse est un nombre ou une date ;\n"
    "- « agir » : garder le dossier, préparer un brief.\n"
    "Termes : 1 à 3 mots, les formes courtes des titres de presse d'abord (Bruxelles, bruxellois, "
    "Brussel), dans les trois langues, 8 au plus par concept, jamais de terme trop général "
    "(« météo », « course », « nouveau »). Un concept ne contient que des mots qui le désignent : "
    "jamais un lieu ou un aspect dans le concept du sujet. Un sujet simple (un nom, un événement) "
    "n'a qu'un concept ; restreindre ajoute exactement un concept."
)
OPERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["chercher", "restreindre", "élargir", "trier", "fait", "agir"]},
        "concepts": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "terms": {"type": "array", "items": {"type": "string"}}},
            "required": ["name", "terms"]}},
        "langue": {"type": ["string", "null"]},
    },
    "required": ["operation", "concepts"],
}
FACT_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. Réponds à la question de l'auteur à partir des "
    "articles numérotés, et d'eux seuls. Pour chaque chiffre ou date trouvé, une ligne : le "
    "numéro de l'article, le chiffre tel qu'écrit, ce qu'il mesure, quand, où, et l'extrait exact "
    "(copié mot pour mot, une phrase) qui le contient. N'additionne jamais des chiffres de sources "
    "différentes : elles peuvent compter les mêmes faits. Si deux chiffres ne portent pas sur la "
    "même période ou le même lieu, dis-le. « quand » et « où » sont obligatoires : la date ou le "
    "moment, et le lieu, de ce que le chiffre mesure, tels que l'article les donne (« non précisé » "
    "sinon). Lis la question avec la conversation : « Combien ? » après « des blessés ? » veut "
    "dire « combien de blessés ». Puis la "
    "concordance : « concordent » (les sources disent la même chose), « divergent » (elles "
    "diffèrent), « partiel » (des chiffres différents qui ne mesurent pas la même chose), ou "
    "« absent » (aucun article ne répond ; alors aucune ligne). Une phrase de conclusion courte, "
    "sans rien ajouter que les lignes ne disent."
)
FACT_SCHEMA = {
    "type": "object",
    "properties": {
        "lignes": {"type": "array", "items": {"type": "object", "properties": {
            "article": {"type": "integer"}, "chiffre": {"type": "string"}, "mesure": {"type": "string"},
            "quand": {"type": "string"}, "ou": {"type": "string"}, "extrait": {"type": "string"}},
            "required": ["article", "chiffre", "mesure", "quand", "ou", "extrait"]}},
        "concordance": {"type": "string", "enum": ["concordent", "divergent", "partiel", "absent"]},
        "conclusion": {"type": "string"},
    },
    "required": ["lignes", "concordance", "conclusion"],
}


def chat(system: str, user: str, schema: dict) -> tuple[dict, float]:
    body = json.dumps({
        "model": MODEL, "stream": False, "think": False, "format": schema,
        "options": {"temperature": 0, "num_ctx": 16384},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    started = time.monotonic()
    request = urllib.request.Request(f"{OLLAMA}/api/chat", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.load(response)
    return json.loads(data["message"]["content"]), round(time.monotonic() - started, 1)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def bench(workspace: UUID) -> None:
    engine = db.create_engine(Settings.from_env().require_database_url())
    store = PostgresAssistantStore(engine)
    glossary = [stored.entry for stored in store.glossary(workspace)]
    since = datetime.now(UTC) - timedelta(days=30)

    total = store.total_items(workspace, since)

    def find(concepts, language):
        widened = widen(concepts, glossary)
        counts = store.term_counts(workspace, [t for w in widened for t in w.all_terms], since)
        widened = too_general(widened, counts, total)
        found = store.candidates(workspace, widened, since, 400)
        return [c for c in found if not language or (c.language or "").startswith(language)]

    for key, steps in CONVERSATIONS:
        print(f"\n=================== Conversation {key}")
        ref_concepts, ref_language, reference = [], None, []
        model_concepts, model_language = [], None
        history: list[str] = []
        for question, kind, added, lang, _ in steps:
            ref_concepts += [Concept(t[0], tuple(t)) for t in added]
            ref_language = lang or ref_language
            if kind != "fait":
                reference = find(ref_concepts, ref_language)
            current = " ; ".join(f"{c.name}: {', '.join(c.terms)}" for c in model_concepts) or "(aucun)"
            user = (
                "Conversation :\n" + "\n".join(history) + f"\nConcepts de l'ensemble courant : {current}"
                f"\nLangue : {model_language or 'toutes'}\n\nDernière question : {question}"
            )
            answer, seconds = chat(OPERATION_SYSTEM, user, OPERATION_SCHEMA)
            history.append(f"Auteur : {question}")
            operation = answer.get("operation")
            proposed = [Concept(c.get("name") or c["terms"][0], tuple(c["terms"]))
                        for c in answer.get("concepts", []) if c.get("terms")]
            # Guards without a model (third pass). A concept is kept only when the question
            # names it (its name or one of its terms): « impact, effet, ville » is dropped.
            # A language asked for is a filter, never a concept.
            asked = f" {fold(question)} "
            anchored = [c for c in proposed if any(f" {fold(w)} " in asked or fold(w) in asked.split()
                                                   for w in (c.name, *c.terms) if len(w) > 2)]
            proposed = anchored or proposed[:1]
            for words, code in (("neerlandais neerlandophone flamand nl", "nl"),
                                ("francais francophone", "fr"), ("anglais anglophone", "en")):
                if any(f" {w} " in asked.replace("?", " ") for w in words.split()):
                    operation, model_language, proposed = "restreindre", code, []
            if operation == "chercher":
                model_concepts = proposed[:2]
            elif operation == "restreindre":
                model_concepts = model_concepts + proposed
                langue = answer.get("langue")
                model_language = langue if langue in ("fr", "nl", "en") else model_language
            elif operation == "élargir" and model_concepts and proposed:
                last = model_concepts[-1]
                model_concepts = model_concepts[:-1] + [Concept(last.name, last.terms + proposed[0].terms)]
            line = f"--- {question} | attendu {kind} | modèle {operation} ({seconds} s)"
            if kind != "fait" and operation in ("chercher", "restreindre", "élargir") and model_concepts:
                mine = find(model_concepts, model_language)
                ref_ids, my_ids = {c.id for c in reference}, {c.id for c in mine}
                common = len(ref_ids & my_ids)
                line += (f" | référence {len(ref_ids)}, modèle {len(my_ids)}, communs {common}"
                         f" | termes {[list(c.terms) for c in model_concepts]} langue {model_language}")
            print(line)
            if kind != "fait":
                continue
            articles = reference[:ARTICLES]
            with workspace_transaction(engine, workspace) as connection:
                rows = {r.id: r for r in connection.execute(
                    sa.text("SELECT i.id, i.title, coalesce(i.text, i.feed_content, i.summary, '') AS body,"
                            " s.name AS publisher FROM source_items i LEFT JOIN sources s ON s.id = i.source_id"
                            " WHERE i.id = ANY(:ids)"), {"ids": [c.id for c in articles]}).all()}
            texts = [f"{rows[c.id].title}. {rows[c.id].body}"[:BODY] for c in articles]
            numbered = "\n\n".join(f"[{n}] {rows[c.id].publisher} — {t}" for n, (c, t) in enumerate(zip(articles, texts), 1))
            context = "\n".join(history[:-1])
            fact, seconds = chat(
                FACT_SYSTEM,
                f"Conversation :\n{context}\n\nQuestion : {question}\n\nArticles :\n{numbered}",
                FACT_SCHEMA,
            )
            print(f"    fait ({seconds} s, {len(articles)} articles) : {fact.get('concordance')} — {fact.get('conclusion')}")
            dropped = 0
            for row in fact.get("lignes", []):
                n = row.get("article", 0)
                text = texts[n - 1] if 1 <= n <= len(texts) else ""
                passage_ok = bool(text) and fold(row.get("extrait", ""))[:80] in fold(text)
                digits = "".join(ch for ch in row.get("chiffre", "") if ch.isdigit())
                quoted = "".join(ch for ch in row.get("extrait", "") if ch.isdigit())
                figure_ok = (digits in quoted) if digits else (
                    fold(row.get("chiffre", "")) in fold(row.get("extrait", "")))
                if not passage_ok:
                    dropped += 1
                    continue
                source = rows[articles[n - 1].id].publisher if 1 <= n <= len(articles) else "?"
                print(f"      [{n}] {source} | {row.get('chiffre')} | {row.get('mesure')} | {row.get('quand', '')} | {row.get('ou', '')}"
                      f" | chiffre {'OK' if figure_ok else 'HORS EXTRAIT'}")
            if dropped:
                print(f"      ({dropped} ligne(s) retirée(s) : extrait absent de l'article)")


bench(UUID(sys.argv[1]))

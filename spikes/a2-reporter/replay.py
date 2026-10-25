# SPDX-License-Identifier: AGPL-3.0-or-later
"""A2 bench, reference: the twelve conversations of the design (« Otlet · A2 : Reporter »)
replayed on the engine of A1b, each step written by hand as the Reporter should translate it.
Prints, for each step, the size of its set and its titles; for a fact, the passages of the set
that hold the words of the question with a number or a date, to establish the reference.

Run in the worker container: python replay.py <workspace id> > replay.txt
"""

import re
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa

from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.domain.terms import Concept, widen
from otlet.platform import database as db
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction

AUSTEN = ("tempête Austen", "storm Austen", "Austen")
BXL = ("Bruxelles", "bruxellois", "bruxelloise", "Brussel", "Brusselse", "Brussels")
# Each conversation: steps of (question, kind, concepts added, language, fact words).
CONVERSATIONS = [
    ("1", [
        ("Les articles sur la tempête Austen", "chercher", [AUSTEN], None, None),
        ("Lesquels concernent Bruxelles ?", "restreindre", [BXL], None, None),
        ("Y a-t-il eu des blessés ?", "restreindre", [("blessé", "blessés", "gewond", "gewonden")], None, None),
        ("Combien ?", "fait", [], None, r"bless|gewond"),
    ]),
    ("2", [
        ("Tempête Austen", "chercher", [AUSTEN], None, None),
        ("Et en néerlandais ?", "restreindre", [], "nl", None),
        ("Combien d'interventions des pompiers à Bruxelles ?", "fait", [], None, r"interventi|brandweer"),
    ]),
    ("3", [
        ("Tempête Austen", "chercher", [AUSTEN], None, None),
        ("Quand l'alerte orange a-t-elle commencé ?", "fait", [], None, r"orange|alerte|code"),
    ]),
    ("4", [
        ("Le budget de Bruxelles", "chercher", [("budget", "begroting"), BXL], None, None),
        ("Et côté néerlandophone ?", "restreindre", [], "nl", None),
        ("Quel montant pour la prime aux bailleurs ?", "fait", [], None, r"prime|bailleur|enveloppe|millions"),
    ]),
    ("5", [
        ("Le budget fédéral et l'Arizona", "chercher", [("budget", "begroting"), ("Arizona", "fédéral")], None, None),
        ("Lesquels parlent de la TVA ?", "restreindre", [("TVA", "btw")], None, None),
        ("Quelle hausse est envisagée ?", "fait", [], None, r"TVA|%|pour ?cent"),
    ]),
    ("6", [
        ("Les manifestations d'étudiants", "chercher", [("manifestation", "manifestants", "betoging"), ("étudiants", "jeunes", "studenten")], None, None),
        ("À Liège seulement", "restreindre", [("Liège", "Luik", "liégeois")], None, None),
        ("Combien d'arrestations ?", "fait", [], None, r"arrest|interpell"),
    ]),
    ("7", [
        ("Max Verstappen", "chercher", [("Verstappen",)], None, None),
        ("Seulement le GT3", "restreindre", [("GT3", "GT World Challenge", "Portimão", "Portimao")], None, None),
        ("Quelle place à Portimão ?", "fait", [], None, r"place|position|pole|\d+e\b"),
    ]),
    ("8", [
        ("Verstappen à Austin", "chercher", [("Verstappen",), ("Austin", "Grand Prix des États-Unis", "GP des États-Unis")], None, None),
    ]),
    ("9", [
        ("Le piratage et l'IA", "chercher", [("piratage", "piraté", "cyberattaque", "hacker", "fuite de données"), ("IA", "intelligence artificielle", "AI")], None, None),
        ("Lesquels parlent de la Belgique ?", "restreindre", [("Belgique", "Belges", "belge", "België")], None, None),
        ("Combien de Belges touchés ?", "fait", [], None, r"Belges|milliers|touch"),
    ]),
    ("10", [
        ("Les nouveautés Honda", "chercher", [("Honda",)], None, None),
        ("Seulement les motos", "restreindre", [("moto", "motos", "CB650R", "CB250SS", "trail", "roadster")], None, None),
        ("Quand la CB650R sort-elle ?", "fait", [], None, r"CB650|disponib|sortie|arriv|prix"),
    ]),
    ("11", [
        ("Apple, les nouveaux MacBook", "chercher", [("Apple",), ("MacBook", "iMac", "keynote", "présentation", "événement")], None, None),
        ("Quand est la présentation ?", "fait", [], None, r"octobre|événement|présent|rendez-vous"),
    ]),
    ("12", [
        ("Actiris et les crèches", "chercher", [("Actiris",), ("crèche", "crèches", "kinderopvang", "kinderdagverblijf")], None, None),
        ("Combien d'emplois menacés ?", "fait", [], None, r"emploi|banen|jobs|travailleurs|personeel"),
    ]),
]
NUMBER = re.compile(r"\d[\d .,]*\d|\d")


def main(workspace: UUID) -> None:
    engine = db.create_engine(Settings.from_env().require_database_url())
    store = PostgresAssistantStore(engine)
    glossary = [stored.entry for stored in store.glossary(workspace)]
    since = datetime.now(UTC) - timedelta(days=30)
    for key, steps in CONVERSATIONS:
        print(f"\n=================== Conversation {key}")
        concepts: list[Concept] = []
        language = None
        current: list = []
        for question, kind, added, lang, fact in steps:
            concepts += [Concept(t[0], tuple(t)) for t in added]
            language = lang or language
            if kind != "fait":
                found = store.candidates(workspace, widen(concepts, glossary), since, 400)
                if language:
                    found = [c for c in found if (c.language or "").startswith(language)]
                current = found
                nl = sum(1 for c in current if (c.language or "").startswith("nl"))
                print(f"--- {question} [{kind}] -> {len(current)} articles ({nl} NL)")
                for c in current[:0]:
                    print(f"    {c.dated:%d/%m} [{(c.language or '?')[:2]}] {c.publisher} | {c.title[:110]}")
                continue
            print(f"--- {question} [fait] sur {len(current)} articles")
            with workspace_transaction(engine, workspace) as connection:
                rows = connection.execute(
                    sa.text(
                        "SELECT i.id, i.title, coalesce(i.text, i.feed_content, i.summary, '') AS body,"
                        " s.name AS publisher FROM source_items i LEFT JOIN sources s ON s.id = i.source_id"
                        " WHERE i.id = ANY(:ids)"
                    ),
                    {"ids": [c.id for c in current]},
                ).all()
            pattern = re.compile(fact, re.IGNORECASE)
            for row in rows:
                text = f"{row.title}. {row.body}"
                hits = []
                for sentence in re.split(r"(?<=[.!?])\s+", text):
                    if pattern.search(sentence) and NUMBER.search(sentence):
                        hits.append(" ".join(sentence.split())[:260])
                if hits:
                    print(f"  * {row.publisher} | {row.title[:90]}")
                    for hit in hits[:4]:
                        print(f"      - {hit}")


if __name__ == "__main__" and not globals().get("A2_BENCH") and "A2_BENCH" not in __import__("os").environ:
    main(UUID(sys.argv[1]))

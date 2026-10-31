# SPDX-License-Identifier: AGPL-3.0-or-later
"""A question as an operation, kept to what the question says (ADR-0044 §3, §4)."""

import json

from otlet.assistant.domain.terms import Concept
from otlet.reporter.domain.questions import (
    Operation,
    State,
    Translated,
    check_operation,
    guarded,
    next_state,
    read_operation,
)

AUSTEN = Concept("tempête Austen", ("tempête Austen", "storm Austen", "Austen"))
BXL = Concept("Bruxelles", ("Bruxelles", "Brussel"))


def answer(operation: str, *concepts: tuple[str, list[str]], langue: str | None = None) -> str:
    return json.dumps(
        {
            "operation": operation,
            "concepts": [{"name": n, "terms": t} for n, t in concepts],
            "langue": langue,
        }
    )


def test_an_answer_is_read_and_cleaned() -> None:
    raw = answer("chercher", ("Austen", [" tempête  Austen", "Austen", "austen", ""]))
    # One list of terms is still read; the model is asked for one list by language.
    assert check_operation(raw) != []
    assert read_operation(raw) == Translated(
        Operation.CHERCHER, (Concept("Austen", ("tempête Austen", "Austen")),), None
    )
    assert check_operation('{"operation": "deviner", "concepts": []}')
    assert check_operation("pas du json")


def test_only_three_languages_are_languages() -> None:
    """The model answered « toutes »: taken for a language, it emptied every set (bench)."""
    assert read_operation(answer("restreindre", langue="toutes")).language is None
    assert read_operation(answer("restreindre", langue="nl")).language == "nl"


def test_a_concept_the_question_does_not_name_is_dropped() -> None:
    """Bench, conversation 3: « Quel impact sur la ville ? » gave a concept « impact, effet »."""
    translated = Translated(
        Operation.RESTREINDRE,
        (
            Concept("impact", ("impact", "effet", "conséquence")),
            Concept("Bruxelles", ("Bruxelles",)),
        ),
        None,
    )
    kept = guarded("Lesquels concernent Bruxelles ?", translated)
    # A place is searched by all its names (bench, 2026-10-30).
    assert [c.name for c in kept.concepts] == ["Bruxelles"]
    assert {"Bruxelles", "brussel", "bruxellois"} <= set(kept.concepts[0].terms)


def test_a_search_keeps_its_first_concept_when_none_is_named() -> None:
    translated = Translated(Operation.CHERCHER, (AUSTEN, BXL), None)
    assert guarded("La tempête de vendredi", translated).concepts == (AUSTEN,)


def test_a_language_asked_is_a_filter() -> None:
    translated = Translated(Operation.CHERCHER, (Concept("néerlandais", ("néerlandais",)),), None)
    assert guarded("Et en néerlandais ?", translated) == Translated(Operation.RESTREINDRE, (), "nl")


def test_the_state_follows_the_operations() -> None:
    state = next_state(State(), Translated(Operation.CHERCHER, (AUSTEN,), None))
    state = next_state(state, Translated(Operation.RESTREINDRE, (), "nl"))
    assert state == State((AUSTEN,), "nl")
    state = next_state(state, Translated(Operation.RESTREINDRE, (BXL,), None))
    assert state == State((AUSTEN, BXL), "nl")
    state = next_state(state, Translated(Operation.ELARGIR, (Concept("x", ("Brussels",)),), None))
    assert state.concepts[-1].terms == ("Bruxelles", "Brussel", "Brussels")
    # A fact or a sort does not change the set; a new search starts in every language.
    assert next_state(state, Translated(Operation.FAIT, (), None)) == state
    assert next_state(state, Translated(Operation.CHERCHER, (BXL,), None)) == State((BXL,), None)


def test_a_period_named_is_a_filter() -> None:
    """« les actualités de piratage de ces derniers jours » kept 30 days (Joël, 2026-10-25)."""
    from otlet.reporter.domain.questions import asked_period

    assert asked_period("quels sont les actualités de piratage de ces derniers jours ?") == 7
    assert asked_period("La météo du jour en Belgique ?") == 1
    assert asked_period("Tempête Austen") is None
    concept = Concept("piratage", ("piratage",))
    translated = guarded(
        "Le piratage de ces derniers jours", Translated(Operation.CHERCHER, (concept,), None)
    )
    assert translated.days == 7
    assert next_state(State(), translated) == State((concept,), None, 7)


def test_a_period_names_no_concept_and_a_named_subject_is_searched() -> None:
    """« Quel sont les dernières actualités des jeux vidéo cette semaine ? » (Joël, 2026-10-25):
    a concept « semaine, week », then « jeux vidéo » searched by « console, PC, mobile »."""
    question = "Quel sont les dernières actualités des jeux vidéo cette semaine ?"
    week = Concept("semaine", ("semaine", "week"))
    games = Concept("jeux vidéo", ("nouveau jeu", "console", "PC"))
    kept = guarded(question, Translated(Operation.CHERCHER, (week, games), None))
    assert kept.concepts == (Concept("jeux vidéo", ("jeux vidéo", "jeu", "console", "PC")),)
    assert kept.days == 7
    only_week = guarded(question, Translated(Operation.CHERCHER, (week,), None))
    assert only_week.concepts == () and only_week.days == 7


def test_a_month_named_is_a_period_and_no_concept() -> None:
    """« Quels jeux vidéos sont sortis depuis octobre ? » searched « octobre 2023 »."""
    from datetime import date

    from otlet.reporter.domain.questions import asked_period

    today = date(2026, 10, 29)
    assert asked_period("Quels jeux vidéos sont sortis depuis octobre ?", today) == 29
    assert asked_period("Que s'est-il passé en novembre ?", today) == 363
    months = Concept("octobre", ("octobre", "octobre 2025", "sortie octobre 2024"))
    games = Concept("jeux vidéo", ("jeux vidéo",))
    question = "Quels jeux vidéos sont sortis depuis octobre ?"
    kept = guarded(question, Translated(Operation.CHERCHER, (games, months), None), today)
    assert kept.concepts == (games,) and kept.days == 29


def test_a_word_of_the_question_no_term_searches_is_shown_and_brought_back() -> None:
    """Only « Belgique » was searched for the teaching in Belgium (Joël, 2026-10-29)."""
    from otlet.reporter.domain.questions import unsearched

    question = "Quels sont les derniers faits concernant l'enseignement en Belgique ?"
    belgium = Concept("Belgique", ("Belgique", "België"))
    assert unsearched(question, [belgium]) == ["enseignement"]
    school = Concept("éducation", ("éducation", "école", "onderwijs"))
    kept = guarded(question, Translated(Operation.CHERCHER, (belgium, school), None))
    assert [c.name for c in kept.concepts] == ["Belgique", "enseignement"]
    assert {"Belgique", "België", "belge"} <= set(kept.concepts[0].terms)
    assert kept.concepts[1].terms == ("enseignement", "éducation", "école", "onderwijs")
    assert unsearched(question, list(kept.concepts)) == []


def test_a_concept_naming_a_subject_and_a_place_is_split() -> None:
    """« budget de la région Bruxelles-Capitale » searched budget OR Brussels: the budgets of
    Mons and Seneffe, a storm in Brussels (Joël, 2026-10-29)."""
    from otlet.reporter.domain.questions import split_mixed

    mixed = Concept(
        "budget de la région Bruxelles-Capitale",
        (
            "budget de la région Bruxelles-Capitale",
            "budget",
            "Bruxelles-Capitale",
            "Brussel-Hoofdstad",
            "Brussels-Capital Region",
            "budget régional",
            "budget de la région",
            "budget 2024",
        ),
    )
    assert split_mixed(mixed) == (
        Concept("budget", ("budget", "budget régional", "budget de la région", "budget 2024")),
        Concept(
            "Bruxelles-Capitale",
            ("Bruxelles-Capitale", "Brussel-Hoofdstad", "Brussels-Capital Region"),
        ),
    )
    assert split_mixed(AUSTEN) == (AUSTEN,)
    question = "Je veux en savoir plus sur le budget de la région Bruxelles-Capitale"
    kept = guarded(question, Translated(Operation.CHERCHER, (mixed,), None))
    assert [c.name for c in kept.concepts] == ["budget", "Bruxelles-Capitale"]


def test_a_place_the_set_holds_restricts_nothing_more() -> None:
    budget = Concept("budget", ("budget",))
    region = Concept("Bruxelles-Capitale", ("Bruxelles-Capitale", "Brussel-Hoofdstad"))
    state = State((budget, region))
    again = Concept("Bruxelles Capitale", ("Bruxelles Capitale",))
    assert next_state(state, Translated(Operation.RESTREINDRE, (again,), None)) == state


def test_a_search_of_what_the_set_searches_is_a_question_about_the_set() -> None:
    """« qui parle de budget » searched « acteurs, ministres » and left the set."""
    from otlet.reporter.domain.questions import about_the_set

    state = State((Concept("budget", ("budget",)), Concept("Bruxelles", ("Bruxelles",))))
    actors = Translated(Operation.CHERCHER, (Concept("acteurs", ("acteurs", "ministres")),), None)
    assert about_the_set("qui parle de budget", actors, state)
    assert not about_the_set("Et l'enseignement ?", actors, state)
    assert not about_the_set("Et le MR ?", actors, state)
    assert not about_the_set("qui parle de budget", actors, State())


def test_brussels_is_not_found_in_wallonie_bruxelles() -> None:
    """« Bruxelles-Capitale n'a rien à voir avec Wallonie-Bruxelles » (Joël, 2026-10-29)."""
    from otlet.reporter.domain.questions import only_false_friends

    terms = ("Bruxelles", "Brussel", "bruxellois")
    fwb = "Fédération Wallonie-Bruxelles : le budget 2027 au cœur d'un premier vif échange"
    assert only_false_friends(fwb, terms)
    assert not only_false_friends(fwb + " ; le gouvernement de Bruxelles réagit", terms)
    assert not only_false_friends("Brusselse regering : le budget", ("Brusselse regering",))
    assert not only_false_friends("Le budget régional, sans nommer la ville", terms)


def test_words_between_quotes_are_searched_as_written() -> None:
    """« les actualités concernant le jeux "GTA VI" » (Joël, 2026-10-29): the phrase as it is
    written, and GTA 6 with it."""
    from otlet.reporter.domain.questions import numbered, quoted

    question = 'Quelles sont les actualités concernant le jeux "GTA VI" ?'
    assert quoted(question) == ["GTA VI"]
    assert quoted("Et « Grand Theft Auto » ?") == ["Grand Theft Auto"]
    assert numbered("GTA VI") == ["GTA VI", "GTA 6"]
    assert numbered("Windows 11") == ["Windows 11", "Windows XI"]
    assert numbered("Vi") == ["Vi"]
    games = Concept("GTA VI", ("GTA VI", "GTA 6", "Grand Theft Auto VI"))
    kept = guarded(question, Translated(Operation.CHERCHER, (games,), None))
    assert kept.concepts == (Concept("GTA VI", ('"GTA VI"', '"GTA 6"', '"Grand Theft Auto VI"')),)
    # A phrase the model left out is a concept of its own, first.
    other = guarded(question, Translated(Operation.CHERCHER, (Concept("jeu", ("jeux",)),), None))
    assert other.concepts[0] == Concept("GTA VI", ('"GTA VI"', '"GTA 6"'))


def test_the_failures_of_the_evening_of_2026_10_29() -> None:
    """Joël's conversations after the reading was deployed."""
    from otlet.reporter.domain.questions import about_the_set

    # « perte d'emploi » came with « Bruxelles », never asked, and a concept « parlant ».
    question = "Je veux trouver des articles parlant de perte d'emploi"
    jobs = Concept("perte d'emploi", ("Bruxelles", "perte d'emploi", "chômage", "licenciement"))
    talking = Concept("parlant", ("parlant", "Brussel", "werkloosheid"))
    kept = guarded(question, Translated(Operation.CHERCHER, (jobs, talking), None))
    assert kept.concepts == (
        Concept("perte d'emploi", ("perte d'emploi", "chômage", "licenciement")),
    )
    # « uniquement en Belgique » restricts, though « Belgique » holds « Bruxelles ».
    belgium = Concept("Belgique", ("Belgique", "België", "Bruxelles"))
    state = next_state(State(kept.concepts), Translated(Operation.RESTREINDRE, (belgium,), None))
    assert [c.name for c in state.concepts] == ["perte d'emploi", "Belgique"]
    # The place named in the question is a concept of its own.
    budget = Concept(
        "budget", ("budget", "Région de Bruxelles-Capitale", "Brussels-Capital Region")
    )
    question = "Je veux en savoir plus sur le budget de la région Bruxelles-Capitale"
    kept = guarded(question, Translated(Operation.CHERCHER, (budget,), None))
    assert kept.concepts[0] == Concept("budget", ("budget",))
    # The place by all its names: Bruzz writes « Brussel » (bench, 2026-10-30).
    assert kept.concepts[1].name == "Bruxelles-Capitale"
    assert {"Région de Bruxelles-Capitale", "brussel", "bruxelles"} <= set(kept.concepts[1].terms)
    # « véhicule » is searched by « véhicules »: a follow-up that names nothing new keeps the set.
    cars = State((Concept("véhicules électriques", ("véhicules électriques",)),))
    model = Translated(Operation.CHERCHER, (Concept("modèle", ("modèle", "model")),), None)
    assert about_the_set("et quel est le véhicule éléctrique le moins cher ?", model, cars)
    # The same concept twice is kept once.
    gta = Concept("GTA", ("GTA",))
    assert guarded("GTA VI", Translated(Operation.CHERCHER, (gta, gta), None)).concepts == (gta,)


def test_the_bench_of_2026_10_29() -> None:
    """Questions chosen by Claude, answered by qwen3:14b: what the rules now keep."""
    from otlet.reporter.domain.questions import points_back, unsearched

    # « SNCB » stayed in the name of the concept, never in its terms.
    strikes = Concept("grèves SNCB", ("grève", "lock-out", "protest"))
    kept = guarded(
        "Quoi de neuf sur les grèves à la SNCB ?",
        Translated(Operation.CHERCHER, (strikes,), None),
    )
    assert [c.name for c in kept.concepts] == ["grèves SNCB", "SNCB"]
    # « école » was dropped by the model.
    ai = Concept("intelligence artificielle", ("IA", "AI", "kunstmatige intelligentie"))
    kept = guarded(
        "Que dit-on de l'intelligence artificielle à l'école ?",
        Translated(Operation.CHERCHER, (ai,), None),
    )
    assert [c.name for c in kept.concepts] == ["intelligence artificielle", "école"]
    # A word joined to a pronoun names nothing.
    assert unsearched("Que se passe-t-il chez Tesla ?", [Concept("Tesla", ("Tesla",))]) == []
    assert points_back("Qu'en pensent les enseignants ?")
    assert points_back("Qui s'y oppose ?")
    assert not points_back("Et les voitures chinoises ?")


def test_the_second_bench_of_2026_10_29() -> None:
    """Questions drawn from Joël's recent briefs."""
    from otlet.reporter.domain.questions import about_the_set

    # « October » and « oktober » are no terms of « jeux vidéo ».
    games = Concept("jeux vidéo", ("jeux vidéo", "release", "October", "oktober 2026"))
    kept = guarded(
        "Quels jeux vidéo sont sortis depuis octobre ?",
        Translated(Operation.CHERCHER, (games,), None),
    )
    assert kept.concepts == (Concept("jeux vidéo", ("jeux vidéo", "release")),)
    # « nouveautés », once split from « nouveautés Apple », is no concept.
    news = Concept("nouveautés Apple", ("nouveautés", "Apple", "Apple produits"))
    kept = guarded(
        "Les nouveautés Apple du 28 octobre", Translated(Operation.CHERCHER, (news,), None)
    )
    assert [c.name for c in kept.concepts] == ["Apple"]
    # « Et la Switch 2 ? » narrows the consoles to one of their terms: not about the set.
    consoles = State((Concept("consoles de jeux vidéo", ("Nintendo", "Switch", "PS5")),))
    switch = Translated(Operation.CHERCHER, (Concept("Switch 2", ("Switch 2",)),), None)
    assert not about_the_set("Et la Switch 2 ?", switch, consoles)


def test_a_name_with_a_number_is_a_phrase() -> None:
    switch = Concept("Switch 2", ("Switch 2", "Nintendo"))
    kept = guarded("Et la Switch 2 ?", Translated(Operation.CHERCHER, (switch,), None))
    assert kept.concepts == (Concept("Switch 2", ('"Switch 2"', "Nintendo")),)


def test_the_third_bench_of_2026_10_30() -> None:
    """Questions on the items of 30 October."""
    from otlet.reporter.domain.questions import points_back, split_mixed

    hospitals = Concept(
        "hôpitaux en Flandre", ("hôpitaux en Flandre", "hôpitaux flamands", "Vlaamse ziekenhuizen")
    )
    kept = guarded(
        "La situation financière des hôpitaux en Flandre",
        Translated(Operation.CHERCHER, (hospitals,), None),
    )
    assert kept.concepts[0] == Concept("hôpitaux", ("hôpitaux", "ziekenhuizen"))
    assert kept.concepts[1].name == "Flandre"
    assert {"Vlaanderen", "vlaamse"} <= {t.casefold() for t in kept.concepts[1].terms} | {
        "Vlaanderen"
    }
    philippe = Concept("Edouard Philippe", ("Edouard Philippe", "Philippe", "Edouard"))
    assert split_mixed(philippe) == (philippe,)
    assert points_back("Qui sont les victimes ?")
    assert points_back("Sur les écouteurs ?")
    assert not points_back("Et AWS ?")
    view = Concept("opinion des indépendants", ("opinion des indépendants", "zelfstandigen"))
    kept = guarded(
        "Qu'en pensent les indépendants ?", Translated(Operation.RESTREINDRE, (view,), None)
    )
    assert kept.concepts == (Concept("indépendants", ("indépendants", "zelfstandigen")),)


def test_terms_are_asked_in_every_language() -> None:
    """« hôpitaux » alone missed « Vlaamse ziekenhuizen » (bench, 2026-10-30)."""
    by_language = json.dumps(
        {
            "operation": "chercher",
            "concepts": [
                {
                    "name": "hôpitaux",
                    "fr": ["hôpitaux"],
                    "nl": ["ziekenhuizen"],
                    "en": ["hospitals"],
                }
            ],
        }
    )
    assert check_operation(by_language) == []
    assert read_operation(by_language).concepts == (
        Concept("hôpitaux", ("hôpitaux", "ziekenhuizen", "hospitals")),
    )
    missing = by_language.replace('["ziekenhuizen"]', "[]")
    assert check_operation(missing) == [
        "concepts[0]: give terms in nl (a proper name is repeated as it is)"
    ]


def test_an_acronym_of_the_name_is_a_concept_of_its_own() -> None:
    """« grèves à la SNCB » searched strikes OR SNCB (bench, 2026-10-30)."""
    from otlet.reporter.domain.questions import split_mixed

    strikes = Concept(
        "grèves à la SNCB",
        ("grèves à la SNCB", "grèves", "grèves ferroviaires", "stakingen", "strikes"),
    )
    assert split_mixed(strikes) == (
        Concept("grèves", ("grèves", "grèves ferroviaires", "stakingen", "strikes")),
        Concept("SNCB", ("SNCB",)),
    )


def test_a_country_holds_its_regions_and_towns() -> None:
    """« uniquement en Belgique » lost GSK, « à Wavre » (bench, 2026-10-29)."""
    belgium = Concept("Belgique", ("Belgique",))
    kept = guarded("uniquement en Belgique", Translated(Operation.RESTREINDRE, (belgium,), None))
    terms = {t.casefold() for t in kept.concepts[0].terms}
    assert {"belgique", "wavre", "bruxelles", "vlaanderen", "liege"} <= terms
    assert "france" not in terms


def test_the_bench_of_2026_10_30_afternoon() -> None:
    """Names the model left out are searched; « Pourquoi … ? » is no fact."""
    from otlet.reporter.domain.questions import proper_names

    assert proper_names("Que rachète Ahold Delhaize ?") == ["Ahold Delhaize"]
    assert proper_names("Que change la ministre pour les CPAS ?") == ["CPAS"]
    assert proper_names("Quels jeux vidéo ?") == []
    closing = Concept("fermeture de journal", ("fermeture", "sluiting"))
    kept = guarded(
        "Pourquoi Novaïa Gazeta ferme-t-elle ?", Translated(Operation.FAIT, (closing,), None)
    )
    assert kept.operation is Operation.CHERCHER
    assert [c.name for c in kept.concepts][-1] == "Novaïa Gazeta"
    buying = Concept("rachat", ("rachat", "overname"))
    kept = guarded("Que rachète Ahold Delhaize ?", Translated(Operation.CHERCHER, (buying,), None))
    assert [c.name for c in kept.concepts] == ["rachat", "Ahold Delhaize"]
    # The subject stays when the question named none of the model's concepts.
    driver = Concept("conducteur de train", ("conducteur de train", "treinconducteur"))
    kept = guarded(
        "Le conducteur du train en Espagne avait-il prévenu ?",
        Translated(Operation.CHERCHER, (driver,), None),
    )
    assert [c.name for c in kept.concepts] == ["conducteur de train", "Espagne"]


def test_a_word_rescued_takes_the_model_terms_close_to_it() -> None:
    driver = Concept("conducteur de train", ("conducteur de train", "Espagne", "Spanje"))
    warned = Concept("avait", ("avait", "prévenir", "avertir", "waarschuwen"))
    kept = guarded(
        "Le conducteur du train en Espagne avait-il prévenu ?",
        Translated(Operation.CHERCHER, (driver, warned), None),
    )
    assert kept.concepts[-1] == Concept(
        "prévenu", ("prévenu", "prévenir", "avertir", "waarschuwen")
    )


def test_only_a_period_keeps_the_subject_of_the_conversation() -> None:
    """« Les articles d'aujourd'hui ? » searched the word « aujourd'hui », over 7 days."""
    from otlet.reporter.domain.questions import asked_period, only_a_period

    question = "Les articles d'aujourd'hui ?"
    assert asked_period(question) == 1 and asked_period("Les articles d’aujourd’hui ?") == 1
    assert only_a_period(question) and only_a_period("Et hier ?") and only_a_period("Vandaag ?")
    for asked, days in (
        ("sur les 7 derniers jours", 7),
        ("les 30 derniers jours", 30),
        ("sur 2 semaines", 14),
        ("depuis 3 mois", 90),
        ("de laatste 7 dagen", 7),
        ("the last 7 days", 7),
    ):
        assert asked_period(asked) == days and only_a_period(asked), asked
    assert asked_period("Les 5 meilleurs écrans") is None
    assert not only_a_period("Les étudiants des 7 derniers jours")
    recent = Concept("derniers jours", ("derniers jours",))
    asked = "sur les 7 derniers jours"
    assert guarded(asked, Translated(Operation.RESTREINDRE, (recent,), None)).days == 7
    assert not only_a_period("Les orages d'aujourd'hui ?")
    assert not only_a_period("Les intempéries")
    date_concept = Concept("date", ("aujourd'hui", "vandaag", "today"))
    kept = guarded(question, Translated(Operation.RESTREINDRE, (date_concept,), None))
    assert kept.concepts == () and kept.days == 1


def test_a_question_takes_terms_out_of_the_set() -> None:
    from otlet.reporter.domain.questions import asked_period, excluded_terms, holds_excluded

    assert excluded_terms("En supprimant ce qui concerne Apple") == ("apple",)
    assert excluded_terms("Sans Apple, iPhone et MacBook ?") == ("apple", "iphone", "macbook")
    assert excluded_terms("Sauf les articles sur Samsung") == ("samsung",)
    assert excluded_terms("Zonder Apple") == ("apple",)
    # A word of a subject is not an exclusion: « sans-abri », or in the middle of a question.
    assert excluded_terms("Les sans-abri à Bruxelles") == ()
    assert excluded_terms("Sans-abri à Bruxelles") == ()
    assert excluded_terms("Les budgets sans TVA") == ()
    assert holds_excluded("Apple dévoile un écran", ("apple",))
    assert holds_excluded("Les écrans Apple.", ("apple",))
    assert holds_excluded("Une tarte aux pommes", ("pomme",))
    assert not holds_excluded("Pineapple express", ("apple",))
    assert asked_period("Des annonces concernant de nouveaux écrans ce mois-ci ?") == 31


def test_dates_named_in_a_question() -> None:
    from datetime import date

    from otlet.reporter.domain.questions import (
        asked_dates,
        asks_sort,
        excluded_terms,
        only_a_period,
    )

    today = date(2026, 10, 30)
    both = (date(2026, 10, 29), date(2026, 10, 30))
    question = "uniquement les articles du 29 et du 30 octobre"
    assert asked_dates(question, today) == both
    assert asked_dates("du 29 au 30 octobre", today) == both
    assert asked_dates("Du 29/10/2026 au 30/10/2026", today) == both
    assert asked_dates("le 29 octobre", today) == (date(2026, 10, 29), date(2026, 10, 29))
    assert asked_dates("depuis le 15 octobre", today) == (date(2026, 10, 15), today)
    assert asked_dates("du 28 septembre au 2 octobre", today) == (
        date(2026, 9, 28),
        date(2026, 10, 2),
    )
    assert asked_dates("28, 29 et 30 octobre", today) == (date(2026, 10, 28), today)
    # A date to come: the last one.
    assert asked_dates("le 12 novembre", today) == (date(2025, 11, 12), date(2025, 11, 12))
    assert asked_dates("Les 5 meilleurs écrans", today) is None
    assert asked_dates("Le 31 février", today) is None
    assert only_a_period(question)
    assert not only_a_period("Les processeurs du 29 octobre")
    date_concept = Concept("date", ('"29 et 30 octobre"', '"29 en 30 oktober"'))
    kept = guarded(question, Translated(Operation.RESTREINDRE, (date_concept,), None), today)
    assert (kept.concepts, kept.date_from, kept.date_to) == ((), *both)
    assert asks_sort("Trie-les") and asks_sort("Trier") and not asks_sort("Trie les écrans")
    assert excluded_terms("en supprimant les articles Apple et Macbook") == ("apple", "macbook")


def test_nothing_but_a_period_and_what_is_new_is_no_subject() -> None:
    from otlet.reporter.domain.questions import asked_period, only_a_period

    for question in ("Quelles-sont les actualités du jour ?", "Quel-est l'actualité du jour"):
        assert asked_period(question) == 1 and only_a_period(question)
    new = Concept("nouveaux moniteurs", ("nouveaux moniteurs", "New York", "nouvel An", "new TV"))
    kept = guarded("Les moniteurs", Translated(Operation.CHERCHER, (new,), None))
    assert kept.concepts[0].name == "moniteurs"
    assert kept.concepts[0].terms == ("moniteurs", "New York", "nouvel An", "new TV")


def test_a_new_subject_keeps_the_period_until_another_is_named() -> None:
    from datetime import date

    today = next_state(State(), Translated(Operation.CHERCHER, (), None, 1))
    assert today == State(days=1)
    students = next_state(today, Translated(Operation.CHERCHER, (AUSTEN,), None))
    assert (students.concepts, students.days) == ((AUSTEN,), 1)
    week = next_state(students, Translated(Operation.CHERCHER, (BXL,), None, 7))
    assert (week.concepts, week.days) == ((BXL,), 7)
    day = date(2026, 10, 29)
    dated = next_state(week, Translated(Operation.CHERCHER, (AUSTEN,), None, None, (), day, day))
    assert (dated.days, dated.date_from, dated.date_to) == (None, day, day)
    assert next_state(dated, Translated(Operation.CHERCHER, (BXL,), None)).date_from == day
    # On a set without a subject, a language chosen and what was taken out stay.
    narrowed = next_state(
        State(language="fr", days=1, excluded=("x",)), Translated(Operation.CHERCHER, (BXL,), None)
    )
    assert (narrowed.language, narrowed.excluded) == ("fr", ("x",))
    # On a subject, a new subject starts again in every language.
    again = next_state(
        State((AUSTEN,), "fr", 7, excluded=("x",)), Translated(Operation.CHERCHER, (BXL,), None)
    )
    assert (again.language, again.excluded, again.days) == (None, (), 7)


def test_the_budget_of_brussels_capitale_is_a_subject_and_a_place() -> None:
    from otlet.reporter.domain.questions import is_place

    question = "Quelle nouvelle sur le budget de la région de bruxelles capitale ?"
    concept = Concept(
        "budget de la région de bruxelles capitale",
        ("budget", "begroting", "bruxelles capitale"),
    )
    kept = guarded(question, Translated(Operation.CHERCHER, (concept,), None))
    assert [is_place(c) for c in kept.concepts] == [False, True]
    subject = kept.concepts[0]
    assert "capitale" not in subject.name and "budget" in subject.terms
    assert "begroting" in subject.terms


def test_a_question_that_names_the_subject_as_a_complement_stays_in_the_set() -> None:
    from otlet.reporter.domain.questions import refers_back, without_the_subject

    state = State((Concept("accident de train", ("accident",)), Concept("Espagne", ("Espagne",))))
    assert refers_back("les raisons de l'accident ?", state)
    assert refers_back("Les victimes du train ?", state)
    # A new subject, even with a word in common.
    assert not refers_back("Et les accidents de voiture ?", State((Concept("train", ("train",)),)))
    assert not refers_back("le budget fédéral", State((Concept("budget", ("budget",)),)))
    games = State((Concept("jeux vidéo", ("jeux vidéo",)),))
    assert not refers_back("Quelles sont les actualités des jeux vidéo cette semaine ?", games)
    concepts = (Concept("cause", ("cause",)), Concept("accident", ("accident",)))
    assert [c.name for c in without_the_subject(concepts, state)] == ["cause"]

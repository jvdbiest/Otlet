# SPDX-License-Identifier: AGPL-3.0-or-later
"""The values of a brief's audience, tone and channel (Joël, 2026-10-19, phase 1): closed lists,
each value with a definition the model receives, so that drafts are written, and compared, on
the same terms. A brief keeps the key; phase 2 makes these lists the first values of each
workspace, editable. None of them may lift the writing charter: no value asks for promotion,
emphasis or judgements of the model's own."""

from dataclasses import dataclass, replace

from otlet.writing.domain.brief import BriefFields, Length


@dataclass(frozen=True, slots=True)
class Choice:
    key: str
    label: str
    definition: str  # what the model receives, after the label
    length_max: Length | None = None  # a channel that cannot hold a longer article


AUDIENCES = (
    Choice(
        "general_public",
        "Grand public",
        "Lecteur sans connaissance particulière du sujet. Vocabulaire courant, termes techniques"
        " expliqués brièvement, contexte rappelé.",
    ),
    Choice(
        "beginner",
        "Débutant",
        "Découvre le sujet et veut apprendre. Chaque notion est définie, les explications vont"
        " pas à pas.",
    ),
    Choice(
        "informed_amateur",
        "Amateur éclairé",
        "Connaît les bases et suit le sujet avec intérêt. Va au-delà des généralités, sans"
        " redéfinir les notions courantes du domaine.",
    ),
    Choice(
        "professional",
        "Professionnel du secteur",
        "Travaille dans le domaine. Vocabulaire du métier sans explication ; priorité aux faits"
        " utiles à sa pratique : chiffres, normes, dates, conséquences concrètes.",
    ),
    Choice(
        "expert",
        "Expert",
        "Maîtrise le sujet en profondeur. Précision maximale, nuances et limites des sources"
        " signalées, aucun rappel des bases.",
    ),
    Choice(
        "decision_maker",
        "Décideur",
        "Doit trancher ou arbitrer. L'essentiel et ses conséquences d'abord (coûts, délais,"
        " risques), les détails ensuite.",
    ),
    Choice(
        "student",
        "Étudiant",
        "Apprend le sujet de façon structurée. Plan clair, notions définies, distinction nette"
        " entre faits établis et points débattus.",
    ),
    Choice(
        "journalist",
        "Journaliste",
        "Cherche des faits vérifiables. Chiffres, dates et citations attribués, sources clairement"
        " identifiées, aucune mise en forme promotionnelle.",
    ),
    Choice(
        "consumer",
        "Consommateur",
        "Utilise le produit ou le service dont il est question. Ce qui change concrètement pour"
        " lui d'abord (prix, disponibilité, compatibilité, démarches), sans promotion.",
    ),
    Choice(
        "young_audience",
        "Jeune public",
        "Enfants de 8 à 12 ans. Phrases courtes, mots simples, aucun détail choquant ;"
        " explications simples sans ajouter de faits.",
    ),
)

TONES = (
    Choice(
        "neutral",
        "Neutre",
        "Factuel, sans adjectif de jugement, ni familiarité ni emphase.",
    ),
    Choice(
        "educational",
        "Pédagogique",
        "Explique pas à pas, annonce ce qui vient, reformule les notions difficiles, sans"
        " condescendance.",
    ),
    Choice(
        "formal",
        "Formel",
        "Registre soutenu, vouvoiement, phrases complètes, aucune expression familière.",
    ),
    Choice(
        "relaxed",
        "Détendu",
        "Registre courant et accessible, phrases courtes, tournures orales légères admises. Reste"
        " factuel : ni superlatif ni jugement non attribué.",
    ),
    Choice(
        "lively",
        "Vivant",
        "Rythme dynamique, phrases variées, verbes d'action. Aucune exagération ni promesse.",
    ),
    Choice(
        "analytical",
        "Analytique",
        "Relie les faits, causes et conséquences présents dans les sources ; distingue le constat"
        " de l'interprétation, toujours attribuée.",
    ),
    Choice(
        "technical",
        "Technique",
        "Termes précis du domaine, chiffres et unités exacts, détails de fonctionnement tirés des"
        " sources.",
    ),
    Choice(
        "institutional",
        "Institutionnel",
        "Voix d'une organisation : sobre, mesurée, à la troisième personne, sans opinion"
        " personnelle.",
    ),
    Choice(
        "conversational",
        "Conversationnel",
        "S'adresse directement au lecteur (« vous »), questions de transition permises avec"
        " modération ; le contenu reste factuel.",
    ),
)
TONE_DEFAULT = "neutral"

# A draft stays an article (title, lead, sections): the definitions of the social networks say
# how it is written for them; the post itself comes with publishing (U07).
CHANNELS = (
    Choice(
        "website",
        "Site web ou blog",
        "Article complet : titre, sections avec intertitres, paragraphes développés ; longueur"
        " selon le réglage du brief.",
    ),
    Choice(
        "newsletter",
        "Newsletter",
        "Accroche courte en tête, sections brèves faciles à parcourir, une idée par paragraphe.",
    ),
    Choice(
        "linkedin",
        "LinkedIn",
        "Publication professionnelle courte : l'essentiel dans les deux premières lignes,"
        " paragraphes d'une ou deux phrases, intertitres brefs.",
    ),
    Choice(
        "facebook",
        "Facebook",
        "Publication courte et directe : l'information principale en premier, phrases simples,"
        " intertitres brefs.",
        Length.SHORT,
    ),
    Choice(
        "instagram",
        "Instagram",
        "Légende d'un visuel : quelques phrases courtes, l'essentiel en premier, intertitres"
        " brefs.",
        Length.SHORT,
    ),
    Choice(
        "x",
        "X",
        "Texte très court, à décliner ensuite en messages de 280 caractères au plus : une"
        " information principale par paragraphe, phrases brèves.",
        Length.SHORT,
    ),
)

VOCABULARY = {"audience": AUDIENCES, "tone": TONES, "channel": CHANNELS}
LENGTH_ORDER = (Length.SHORT, Length.MEDIUM, Length.LONG)


def choice(field: str, key: str) -> Choice | None:
    """The value of a field (audience, tone or channel) by its key; None for an unknown one."""
    return next((c for c in VOCABULARY[field] if c.key == key), None)


def capped(length: Length, channel: str) -> Length:
    """The length of an article, held to what its channel can carry (Joël, 2026-10-19)."""
    found = choice("channel", channel) if channel else None
    if found is None or found.length_max is None:
        return length
    return min(length, found.length_max, key=LENGTH_ORDER.index)


# Briefs written before the lists held free text (Joël, 2026-10-19). Read through `settled`, a
# text that names a value becomes its key; any other moves to the writing instructions, so that
# nothing is lost. The brief keeps it so at its next save. (A migration could not do it: row
# security shows it no brief.)
LEGACY_NAMES = {
    "audience": {
        "grand public": "general_public",
        "tout public": "general_public",
        "débutant": "beginner",
        "débutants": "beginner",
        "amateur éclairé": "informed_amateur",
        "passionné": "informed_amateur",
        "passionnés": "informed_amateur",
        "professionnel": "professional",
        "professionnels": "professional",
        "professionnel du secteur": "professional",
        "expert": "expert",
        "experts": "expert",
        "décideur": "decision_maker",
        "décideurs": "decision_maker",
        "étudiant": "student",
        "étudiants": "student",
        "journaliste": "journalist",
        "journalistes": "journalist",
        "consommateur": "consumer",
        "consommateurs": "consumer",
        "client potentiel": "consumer",
        "enfant": "young_audience",
        "enfants": "young_audience",
        "jeune public": "young_audience",
    },
    "tone": {
        "neutre": "neutral",
        "informatif": "neutral",
        "pédagogique": "educational",
        "formel": "formal",
        "professionnel": "formal",
        "détendu": "relaxed",
        "vivant": "lively",
        "enthousiaste": "lively",
        "analytique": "analytical",
        "technique": "technical",
        "institutionnel": "institutional",
        "conversationnel": "conversational",
    },
    "channel": {
        "site web": "website",
        "site": "website",
        "blog": "website",
        "site web ou blog": "website",
        "newsletter": "newsletter",
        "linkedin": "linkedin",
        "facebook": "facebook",
        "instagram": "instagram",
        "x": "x",
        "twitter": "x",
        "x / twitter": "x",
    },
}
LEGACY_LABELS = {"audience": "Public", "tone": "Ton", "channel": "Canal visé"}


def settled(fields: BriefFields) -> BriefFields:
    """The fields of a stored brief, with any free text of an older brief settled."""
    values = {"audience": fields.audience, "tone": fields.tone, "channel": fields.channel}
    if all(not v or choice(f, v) is not None for f, v in values.items()):
        return fields
    kept = []
    for field, text in list(values.items()):
        if not text or choice(field, text) is not None:
            continue
        key = LEGACY_NAMES[field].get(text.strip().lower(), "")
        if not key:
            kept.append(f"{LEGACY_LABELS[field]} : {text.strip()}")
        values[field] = key
    instructions = "\n".join([fields.instructions, *kept]).strip()
    return replace(
        fields,
        audience=values["audience"],
        tone=values["tone"],
        channel=values["channel"],
        instructions=instructions,
        length=capped(fields.length, values["channel"]),
    )

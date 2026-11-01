# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hand-written reference of reporter_wide_read.py; approximate."""
RULES = {
    "La situation financière des hôpitaux en Flandre": [r"ziekenhui|hôpita|hospita", r"vlaa|flandre|flamand|flemish|vlaanderen", r"geld|winst|financ|déficit|tekort|pensioen|fusie|fusion|budget|besparing"],
    "Quelle nouvelle sur le budget de la région de bruxelles capitale ?": [r"begroting|budget|financ|dette|schuld|belasting|fiscal|économi", r"brussel|bruxell", r"^(?!.*(fédéral|federale|wallonie-bruxelles|fwb)).*$"],
    "Que dit-on de l'intelligence artificielle à l'école ?": [r"\bia\b|\bai\b|intelligence artificielle|kunstmatige|chatgpt|chatbot", r"école|school|élève|leerling|enseign|onderwijs|leraar|leraren|étudiant|student|classe|univers"],
    "L'accident de train en Espagne": [r"espagne|spanje|spain|espagnol|spaans|madrid|urda", r"train|trein|ferrovi|spoor|rail"],
    "Les essais de motos récents": [r"^(essai|test|review|rijtest|getest)|l.essai|\bessai\b|\btest\b", r"moto|motorfiets|motorcycle|honda|yamaha|kawasaki|ducati|ktm|triumph|cfmoto|suzuki|bmw r|scooter|trail|roadster|sportive"],
    "Les pertes d'emploi en Belgique": [r"pertes? d.emploi|licenci|emplois? (menacés|supprimés)|suppressions? d.emplois|banen|ontslag|job cuts|layoff|jobs? (cut|lost)|faillite|faillissement|restructur|herstructur|fermeture"],
    "Pourquoi risque t'il de faire très froid dans les jours qui viennent ?": [r"froid|gelée|\bgel\b|0°c|vortex|hiver 2026|météo va se bloquer", r"météo|prévi|attendu|semaine prochaine|novembre|climat|gelées|vortex|hiver|plan grand froid|températures"],
    "Les élections de mi-mandat aux États-Unis": [r"mi-mandat|midterm|tussentijdse"],
    "La tempête Austen en Belgique": [r"austen"],
    "Les résultats de Proximus": [r"proximus"],
    "Le piratage de Binance": [r"binance"],
    "Le concert d'Angèle à Bruxelles": [r"angèle"],
}

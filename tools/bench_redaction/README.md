# Banc de rédaction

Mesure la qualité des brouillons sur un jeu de briefs de référence, pour juger un changement de prompt ou de modèle sur des chiffres plutôt que sur une seule génération (décision de Joël, 2026-10-19, après l'audit qualité du moteur de génération).

## Ce qu'il mesure

Pour chaque brief de `briefs.json`, le banc construit le prompt exactement comme le produit (règles d'Otlet, charte par défaut, brief, longueur liée à la matière), appelle le modèle, puis mesure la première réponse :

| Mesure | Lecture |
| --- | --- |
| `unsupported_per_100` | noms, dates et nombres absents des sources, pour 100 mots (garde-fou U05) |
| `copy_share`, `copied_passages` | part des suites de 8 mots reprises d'une source ; passages de 12 mots ou plus |
| `judgements_per_100` | adjectifs de jugement absents des sources, pour 100 mots |
| `items_kept`, `names_kept` | part des éléments attendus (films d'une liste, noms cités par la source) |
| `length_ratio` | mots obtenus face à la longueur utilisée |
| `ids_in_text`, `english_words` | fuites de forme |
| erreurs de forme | les refus que le produit renverrait au modèle |

Les mesures repèrent des indices, pas des preuves : relire les noms signalés.

## Lancer

```sh
OTLET_SSH="ssh -i ~/.ssh/otlet_nas otlet@192.168.129.252" OTLET_DB=otlet-x01-db-1 sh tools/bench_redaction/export.sh
python tools/bench_redaction/run.py --endpoint http://localhost:11434/v1 --model qwen3:14b --repeat 2
```

`export.sh` copie les textes des sources dans `data/`, sur la machine seulement : ce sont des articles d'autrui, jamais versionnés. Les résultats vont dans `results/` (un `.jsonl` par essai, un `.md` de synthèse), hors du dépôt aussi ; une synthèse utile se recopie dans la documentation.

Python 3.13 sans dépendance : le banc importe le code du domaine de `backend/src`.

## Ajouter un brief

Une entrée dans `briefs.json` : ses sources par URL (des éléments collectés par Otlet), ses champs de brief, ce qu'il doit garder (`expect`), et pourquoi il est là (`why`). Puis relancer `export.sh`.

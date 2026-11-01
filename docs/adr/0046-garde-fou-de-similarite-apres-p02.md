# ADR-0046 — Garde-fou de similarité après P02

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-11-01 |
| Décideur | Joël |
| Documents touchés | ADR-0024 (points 1, 5, 6) ; ADR-0045 ; U05 et P02 du backlog d'É1 ; `RISKS.md` §4.8 |
| Origine | Rapport P02 (conclu : partiel) |

## Contexte

P02 a mesuré le garde-fou sur le corpus réel. Au score en fenêtre de 5 phrases, potion et MiniLM détectent 93 à 95 % des paraphrases et des traductions, sans faux positif et presque sans bloquer de brouillon réel. Le score moyen échoue sur les traductions. Mais les seuils calibrés laissent passer plus de la moitié des reprises partielles, le cas réel des brouillons. Une lecture hors verdict (P02 §4.3) montre que des seuils plus bas sépareraient bien mieux, surtout avec MiniLM.

## Décision proposée

1. **Modèle** : MiniLM-L12, déjà dans l'image (ADR-0045), à la place de potion. Mêmes critères tenus, 760 Mio au pic contre 1 690 Mio sur le NAS, 33 s contre 28 s par brouillon à 5 sources.
2. **Score** : la fenêtre de 5 phrases, pour chaque source, et non la moyenne de l'article.
3. **Volet lexical** : la plus longue sous-séquence commune au seuil de 0,70 remplace les 5-grammes.
4. **Complément P02b, avant toute mise en service** : mesurer les seuils de 0,85 en même langue et 0,80 entre langues sur un échantillon neuf, jamais vu, avec plus de négatifs. Mêmes critères que P02, C7 compris. Environ 40 sources, soit 80 appels et une trentaine de minutes. Rapport commité avant la mesure (ADR-0018).
5. **Produit (décision de Joël du 2026-11-01)** : blocage à la validation et à la sortie, jamais à la génération, levable avec une justification gardée en trace. Passages signalés paragraphe par paragraphe, face à la source concernée.

## Conséquences

- Pas de seconde dépendance ni de second modèle dans le worker.
- Si P02b échoue, le garde-fou reste un avertissement, sans blocage.
- Un brouillon qui passe n'est pas vérifié sur le fond : ce contrôle reste un sujet ouvert (FOND1).

## Options écartées

- **Mettre en service les seuils calibrés de P02** : ils laissent passer la plupart des brouillons jugés trop proches.
- **Fixer 0,85 et 0,80 sans remesure** : choisis en voyant les données, ils ne prouvent rien.
- **Garder potion** : aucun gain mesuré sur les critères, pour 930 Mio de plus au pic.

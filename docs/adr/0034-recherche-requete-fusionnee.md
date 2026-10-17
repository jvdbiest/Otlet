# ADR-0034 — Recherche plein texte : une seule requête pour toutes les langues

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-17 |
| Décideur | Joël |
| Documents touchés | ADR-0033, ADR-0021, ADR-0032 §4 ; migration de `search_candidates` |
| Origine | Rapport P01c (conclu : échec partiel) |

## Contexte

Depuis l'ADR-0033, la recherche utilise son index. P01c reste pourtant au-dessus du seuil de 300 ms pour trois familles sur quatre : 6,4 s au p95 pour un mot fréquent, avec 4 clients sur la VM du NAS.

L'analyse de P01c (§4) montre la cause. `search_candidates` teste le texte dans huit configurations de langue, par huit conditions reliées par OU. Pour un mot comme « monde », presque toutes donnent le même mot réduit. Le planificateur additionne pourtant leurs estimations : il attend 55 584 éléments au lieu de 12 361, juge qu'il vaut mieux lire toute la table, et décompresse alors chaque vecteur (2,5 s pour une seule recherche). Les réglages de session (JIT, plans génériques, parcours complet interdit) ne corrigent pas ce choix.

## Décision proposée

1. **Une seule requête.** La fonction calcule une fois les huit variantes, retire les doublons, et les réunit en une seule requête plein texte (`a | b | …`). Elle la teste par une seule condition, que l'index sert toujours. Le reste de l'ADR-0033 ne change pas : le même rôle, le même filtre sur l'espace et la même fenêtre prise dans la fonction.
2. **La fenêtre de classement, à choisir par Joël.**
   - **1 000 (inchangée)** : le classement porte sur les 1 000 éléments les plus récents qui correspondent. Essai d'information : Q1 à 393 ms au p95, les autres familles entre 172 et 302 ms.
   - **300** : le classement ne porte que sur les 300 plus récents ; un article plus ancien mais très pertinent peut ne pas apparaître dans les 50 premiers résultats. Essai d'information : Q1 à 329 ms, les autres entre 126 et 246 ms.
3. **Remesure P01d** : le protocole de P01c, le même corpus et les mêmes requêtes.

Avec un seul client, ce qui correspond à l'usage personnel d'É1, la requête fusionnée donne de 72 à 139 ms au p95 pour les quatre familles (essai d'information).

## Conséquences

- La correction est petite : une migration qui remplace le corps de la fonction, et un test qui vérifie qu'un mot présent dans plusieurs langues ne fait plus lire toute la table.
- Les essais d'information laissent prévoir que Q1 restera un peu au-dessus de 300 ms avec 4 clients sur la VM du NAS, même avec une fenêtre de 300. Seule P01d le dira. Si c'est le cas, il restera les leviers de `TECH_CHOICES.md` §8.4 (partitionnement par mois), ou une décision sur la charge de référence : 4 clients simultanés sur 2 vCPU représentent une petite équipe, pas l'usage personnel d'É1.

## Options écartées

- **Index sur la date, table de recherche étroite, fenêtre de 30 jours** : essayés dans P01c (`results-p01c/trials.txt`). Chacun réduit un peu le temps, mais laisse la lecture complète de la table possible, et donc la traîne.
- **Réglages du planificateur par fonction** (`enable_seqscan = off`, plans forcés) : essayés, sans effet suffisant ; ils masqueraient l'erreur d'estimation au lieu de la retirer.

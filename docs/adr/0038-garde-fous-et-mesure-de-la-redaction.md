# ADR-0038 — Rédaction : contrôles après génération et mesure, plutôt que retouches du prompt

| | |
|---|---|
| Statut | Accepté (2026-10-19) |
| Date | 2026-10-19 |
| Décideur | Joël |
| Documents touchés | ADR-0024 (garde-fous de similarité) ; backlog d'É1 (U04, U05) ; `tools/bench_redaction/` |
| Origine | Document partagé « Audit qualité du moteur de génération » : 64 générations et 12 essais contrôlés |

## Contexte

L'audit montre que les erreurs des brouillons viennent surtout du modèle, qui comble avec ses connaissances (« Stephen King » dans 5 des 19 versions d'un top 10 dont la source ne le nomme pas), de la longueur demandée au-delà de la matière des sources, et de l'absence de tout contrôle du fond après génération. La charte divise environ par deux les jugements non attribués sans empêcher les inventions. Les retouches du prompt, jugées sur une génération à la fois, suivaient en partie le bruit d'un essai à l'autre.

## Décision

1. **Premier lot de U05, avancé avant toute nouvelle retouche du prompt.** Après chaque génération : les noms propres, dates et nombres que les sources n'écrivent pas (ni le brief de l'auteur), et la recopie (part des suites de 8 mots reprises, passages de 12 mots ou plus). Contrôles lexicaux et déterministes, montrés en Avertissement avec un lien vers le paragraphe ; ils n'empêchent rien, l'auteur décide. Le reste de U05 (similarité inter-langues, citations, mots interdits) suit ADR-0024.
2. **La longueur suit la matière.** Un brouillon a au plus 80 % des mots de ses sources : la longueur demandée est ramenée à la plus longue que la matière permet, et une matière trop mince (un résumé de quelques lignes) donne un brouillon court et un Avertissement. Le brief montre la matière disponible et grise les longueurs qu'elle ne porte pas.
3. **La Synthèse conseille le croisement, sans l'exiger.** Une section sur une seule source n'est plus renvoyée au modèle : c'est un Avertissement qui propose le Panorama. Le choix du mode disparaît du brief à une seule source.
4. **Une règle d'attribution ciblée**, comme celle des listes : une sélection, un classement, un avis est attribué à son auteur, et ses jugements ne sont jamais repris à son compte.
5. **Un banc de mesure.** `tools/bench_redaction/` rejoue un jeu de briefs de référence avec le prompt du produit et mesure chaque brouillon (inventions, recopie, jugements, couverture, longueur, forme). Toute nouvelle version du prompt ou tout nouveau modèle s'y juge, deux essais au moins par brief. Les textes des sources n'y sont jamais versionnés.

## Conséquences

- Prompt redaction-11. Le détail de chaque génération garde la matière, la longueur demandée et utilisée, les noms et nombres absents des sources, la recopie.
- Les contrôles lexicaux donnent des faux positifs (un nom traduit d'une source anglaise : « Cisjordanie » pour « West Bank ») : ce sont des points à vérifier, pas des fautes.
- Ce qui peut attendre (rédaction en deux passes, juge d'ancrage par un second modèle) se décidera sur les chiffres du banc.

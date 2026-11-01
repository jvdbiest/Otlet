# TEXTE1c — La variante E3, sur des pages nouvelles

| | |
|---|---|
| Statut | Conclue : partiel |
| Durée maximale | 1 h de mesure |
| Temps passé | 2 h de préparation et d'analyse (journal de temps, TEXTE1c) ; mesure en quelques minutes |
| Ouverte le / conclue le | 2026-11-01 / 2026-11-01 |
| Choix concernés | Collecte U01 (`readability-lxml`), rédaction U04, recherche (S1) |
| Commande de rejeu | `spikes/texte1/run-texte1c.sh`, puis `run-texte1c.sh --summary` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

L'hypothèse E3, née après coup dans `docs/spikes/TEXTE1b.md` §8, tient-elle sur des pages que ni elle ni personne n'a encore vues ? Joël a demandé une validation indépendante (2026-11-01), avec les mêmes seuils, avant toute décision sur l'extraction.

## 2. Critères de réussite

Les seuils de TEXTE1b, inchangés.

| Critère | Seuil |
|---|---|
| Couverture médiane de la référence | ≥ 90 % |
| Pages avec moins de 50 % de la référence | ≤ 5 % |
| Pollution médiane | ≤ 15 % |
| Pages qui perdent plus de 20 points de couverture sur l'extraction actuelle | ≤ 5 % |
| Les Numériques, RTBF, Audiofanzine, Futura : part des pages sous la moitié du texte le plus long trouvé, sur le pire des quatre | ≤ 5 % |
| Temps d'extraction, p95 sur .252 | ≤ 300 ms |

**Succès** : E3 tient les 6 critères : l'hypothèse est confirmée et le changement d'extraction peut être proposé à Joël. **Partiel** : E3 fait nettement mieux qu'E0 sans tenir les 6. **Échec** : E3 ne fait pas nettement mieux qu'E0, ou recule.

## 3. Protocole

**Environnement.** Celui de TEXTE1b : VM .252, conteneur jetable de l'image du worker, sans réseau, `trafilatura` 2.0.0 à côté pour le banc seul. Aucun modèle, rien d'écrit dans la Veille.

**Jeu figé, nouveau.** 480 textes tirés au hasard, 40 par site, parmi ceux que les règles autorisaient, **sans aucune des 520 pages de TEXTE1b**. Pages relues le 2026-11-01, une toutes les 3 s, toutes obtenues. 12 sites : L'Avenir n'atteint plus 70 textes une fois ses pages déjà tirées retirées. Les pages restent sur la VM (`~/s-texte1c`) ; elles seront effacées après la conclusion, avec celles de TEXTE1b.

**Référence, nouvelle.** Pour 4 pages par site (48), Claude a noté les blocs qui forment l'article (`spikes/texte1/gold1c.json`), avec les règles de TEXTE1b, d'après la liste des blocs de chaque page, avant toute extraction de ces pages. Les menus les plus courants sont masqués dans cette liste pour la lecture ; les numéros de blocs ne changent pas.

**Mesures.** Celles de TEXTE1b : couverture et pollution sur des suites de 3 mots ; proportion et sites avec le même repère.

**Variantes, fixées.**
- **E0, l'extraction actuelle** : `ReadabilityReader` du produit.
- **E2** : `trafilatura.extract`, sans commentaires ni tableaux.
- **E3** : E2, sauf si son texte fait moins de la moitié de ce que la page marque comme article (`articleBody` d'au moins 200 signes, sinon les longs paragraphes du plus grand `<article>`) ; alors ce texte marqué.

Aucun réglage d'E3 après la fusion de ce protocole.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si E3 réussit, le changement et la relecture des articles touchés seront proposés à Joël à part, en respectant les mêmes règles (robots, réserve TDM).

## 4. Mesures

| Critère | Seuil | E0, actuelle | E2, trafilatura | E3, avec repli |
|---|---|---|---|---|
| Couverture médiane | ≥ 90 % | ✅ 93,7 % | ✅ 99,0 % | ✅ 99,0 % |
| Pages sous 50 % de la référence | ≤ 5 % | ✅ 2,1 % | ✅ 2,1 % | ✅ 0 % |
| Pollution médiane | ≤ 15 % | ✅ 5,8 % | ✅ 7,0 % | ✅ 7,0 % |
| Pages qui perdent plus de 20 points sur E0 | ≤ 5 % | ✅ 0 % | ✅ 2,1 % | ✅ 0 % |
| Pire des 4 sites, pages sous la moitié | ≤ 5 % | ❌ 22 % | ❌ 32 % | ❌ 15 % |
| Temps, p95 | ≤ 300 ms | ✅ 93 ms | ✅ 42 ms | ✅ 46 ms |

Les 4 sites surveillés, pages sous la moitié du texte le plus long :

| Site | E0 | E2 | E3 |
|---|---|---|---|
| Les Numériques | 5 % | 15 % | 15 % |
| Futura Sciences | 22 % | 0 % | 0 % |
| Audiofanzine | 18 % | 2 % | 0 % |
| RTBF Info | 2 % | 32 % | 0 % |

Le repère pondéré par site donne 11,3 % pour E0, 4,1 % pour E2 et 1,6 % pour E3.

Fichiers : `spikes/texte1/results/summary1c.txt`. Les pages restent sur la VM.

## 5. Conclusion

**Partiel.** E3 tient 5 critères sur 6 et fait nettement mieux qu'E0 sur des pages nouvelles : couverture médiane de 93,7 % à 99,0 %, plus aucune page sous la moitié de la référence, aucune page en recul. Elle rate le critère des 4 sites à cause de Les Numériques (15 %).

## 6. Conséquences

| Document ou choix | Conséquence | ADR |
|---|---|---|
| Extraction du produit | À soumettre à Joël : passer à E3, malgré le critère raté (§8) | À proposer s'il accepte |

Le code de `spikes/texte1/` reste un banc ; rien n'est repris dans `backend/` à cette étape.

## 7. Ce que la preuve n'a pas couvert

- Un seul auteur de la référence, sur 4 pages par site : les résultats par site viennent du repère automatique, qui signale aussi de faux cas (TEXTE1b §4).
- Le même auteur a conçu E3 et écrit cette référence, sans voir d'extraction de ces pages.
- Les masques de lecture et la coupe à 60 blocs ont pu cacher des blocs d'article ; 10 pages dépassent 60 blocs.
- L'effet sur la recherche, le tri et la rédaction n'est pas mesuré ici.

## 8. Après la conclusion : relecture, hors protocole

Le seuil reste raté et la conclusion reste « partiel ». Cette relecture sert à la décision de Joël (`spikes/texte1/texte1c_after.py`, `results/exploration1c.txt`).

- **Les Numériques.** Les 6 pages en cause ont toutes la même forme : E0 est plus long parce qu'il garde les tableaux de prix (de 22 à 123 prix par page), et E3 s'en tient à l'article. Le repère prend ce texte plus long pour l'article : ici, il signale le défaut d'E0, pas celui d'E3. Sur les 4 pages de référence du site, E3 est à 95 % de couverture ou plus.
- **Reste d'E3.** Next.ink : plus de texte en trop sur les pages à mur payant (jusqu'à 65 % sur une page, contre 10 % pour E0). Une page de Les Numériques garde 75 % de texte en trop, contre 85 % pour E0.
- **La proportion, sur les 100 pages de référence de TEXTE1b et TEXTE1c.** Avec E0, 5 pages sur 100 gardent moins de la moitié de l'article, et 17 sur 100 moins de 70 %. C'est moins que les 8 à 13 % estimés avant : les repères fondés sur la longueur comptaient de faux cas. L'échantillon reste petit.

## 9. Dans le produit : revérification et essai réel (2026-11-01)

Décision de Joël : passer à E3 (ADR-0047). Le code du produit diffère du banc : filtre des éléments cachés avant l'extraction, `trafilatura` 2.3.1 et non 2.0.0.

**Revérification sur les pages figées, sans modèle.**

| | TEXTE1c (480 pages) | TEXTE1b (519 pages) |
|---|---|---|
| Couverture médiane | 99,1 % | 98,9 % |
| Pages sous la moitié de la référence | 0 % | 0 % |
| Pollution médiane | 6,3 % | 7,5 % |
| Pages qui reculent de plus de 20 points | 0 % | 1,9 % |
| Temps, p95 | 123 ms | 120 ms |

Une page de texte vide : aucune. Pic de mémoire d'un processus qui lit toutes ces pages : 107 Mo.

**Essai réel sur .252.** Les 28 sources des deux briefs « [Banc TRI1] » relues aux règles du produit, puis une nouvelle version de chaque brouillon avec qwen3:14b.

- **Froid : version 2.** Le vortex polaire, dont le texte était faux, entre dans le brouillon, avec la nuance qui manquait : un temps frais, sans vague de froid massive annoncée. Le mouron disparaît. Restent la raclette, article retenu qui ne répond pas, et une phrase sans appui attribuée à l'IRM (« son intensité actuelle pourrait accentuer les risques »).
- **Ukraine : pas de nouvelle version.** Deux essais, quatre appels, tous arrêtés au délai de 600 s. Le modèle était tombé de 20 à 2,6 jetons par seconde sur le brouillon du froid, à prompt comparable, sans cause établie. Cet échec ne dit rien de l'extraction.
- **Pages « en direct ».** 10 sources de l'Ukraine ont reçu le direct du jour au lieu du leur : elles ont été remises à leur ancien texte. Les 18 autres sources gardent le nouveau.

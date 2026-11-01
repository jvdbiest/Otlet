# TEXTE1c — La variante E3, sur des pages nouvelles

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 1 h de mesure |
| Temps passé | à remplir |
| Ouverte le / conclue le | 2026-11-01 / à remplir |
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

À remplir après la mesure.

## 5. Conclusion

À remplir.

## 6. Conséquences

À remplir.

## 7. Ce que la preuve n'a pas couvert

- Un seul auteur de la référence, sur 4 pages par site : les résultats par site viennent du repère automatique, qui signale aussi de faux cas (TEXTE1b §4).
- Le même auteur a conçu E3 et écrit cette référence, sans voir d'extraction de ces pages.
- Les masques de lecture et la coupe à 60 blocs ont pu cacher des blocs d'article ; 7 pages dépassent 60 blocs.
- L'effet sur la recherche, le tri et la rédaction n'est pas mesuré ici.

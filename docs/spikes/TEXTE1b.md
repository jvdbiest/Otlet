# TEXTE1b — Une extraction plus complète du texte des articles

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 2 h de mesure |
| Temps passé | à remplir |
| Ouverte le / conclue le | 2026-11-01 / à remplir |
| Choix concernés | Collecte U01 (`readability-lxml`), rédaction U04, recherche (S1) |
| Commande de rejeu | `spikes/texte1/run-texte1b.sh`, puis `run-texte1b.sh --summary` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Quelle part des textes collectés est réellement touchée, sur quels sites, et que gagne-t-on avec une extraction plus complète ? Suite de `docs/spikes/TEXTE1.md`, qui a établi la cause (le parsing) et estimé environ 11 % de textes sous la moitié de l'article.

## 2. Critères de réussite

Une variante réussit si elle tient tous les critères, sur la référence écrite à la main (52 pages) et sur les pages figées.

| Critère | Seuil |
|---|---|
| Couverture médiane de la référence | ≥ 90 % |
| Pages avec moins de 50 % de la référence | ≤ 5 % |
| Pollution médiane (texte retenu hors de la référence) | ≤ 15 % |
| Pages où la variante perd plus de 20 points de couverture sur l'extraction actuelle | ≤ 5 % |
| Les Numériques, RTBF, Audiofanzine, Futura : part des pages sous la moitié du texte le plus long trouvé, sur le pire des quatre | ≤ 5 % |
| Temps d'extraction, p95 sur .252 | ≤ 300 ms |

**Succès** : une variante tient les 6 critères. **Partiel** : une variante améliore nettement la couverture sans tenir les 6. **Échec** : aucune ne fait mieux que l'extraction actuelle.

## 3. Protocole

**Environnement.** VM .252. Aucun modèle, aucun accès réseau pour les extractions, rien d'écrit dans la Veille. Conteneur jetable de l'image du worker ; `trafilatura` 2.0.0 (Apache-2.0) n'y est installé que pour le banc, et n'entre pas dans le produit.

**Jeu figé.** 520 textes tirés au hasard, 40 par site, pour les 13 sites de plus de 70 textes en 30 jours, parmi ceux que les règles autorisaient (`full_text`). Pages relues le 2026-11-01, une toutes les 3 s, comme le worker les lit ; 519 obtenues, 1 délai dépassé. Les pages restent sur la VM (`~/s-texte1/pages.jsonl`) et ne sont pas versionnées ; elles seront effacées après la conclusion.

**Référence.** Pour 4 pages par site (52), Claude a noté les blocs qui forment l'article (`spikes/texte1/gold.json`) : chapô et corps, sans titre, légendes, liens « à lire aussi », commentaires ni menus. Écrite d'après la liste des blocs de chaque page, avant toute extraction de ces pages par les variantes. Une page coupée par un mur payant se juge sur sa partie visible.

**Mesures.** Sur des suites de 3 mots, sans casse ni accents :
- **couverture** : part de la référence présente dans le texte extrait ;
- **pollution** : part du texte extrait absente de la référence.

**Proportion et sites.** Sur les 519 pages : part des pages où l'extraction fait moins de la moitié du texte le plus long trouvé pour cette page (`articleBody` ou `<article>`, ou `trafilatura`, ou l'extraction actuelle), par site, puis pondérée par le nombre de textes de chaque site. La référence dira si ce repère est fiable.

**Variantes.**
- **E0, l'extraction actuelle** : `ReadabilityReader` du produit.
- **E1, repli sur la page** : E0, sauf si son texte fait moins de la moitié de ce que la page marque comme article (`articleBody` d'au moins 200 signes, sinon les longs paragraphes du plus grand `<article>`).
- **E2, autre bibliothèque** : `trafilatura.extract`, sans commentaires ni tableaux.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si une variante réussit, le changement et la relecture des articles touchés seront proposés à Joël à part, en respectant les mêmes règles (robots, réserve TDM).

## 4. Mesures

À remplir après la mesure.

## 5. Conclusion

À remplir.

## 6. Conséquences

À remplir.

## 7. Ce que la preuve n'a pas couvert

- Un seul auteur de la référence, sur 4 pages par site : les résultats par site viennent du repère automatique, pas de la référence.
- Une page de 2026-11-01 peut différer de celle de la collecte : pas d'effet sur la comparaison des variantes.
- Une page qui garde plus de 70 blocs n'a été lue que sur ses 70 premiers (3 pages de Les Numériques, 3 de Futura, 1 du Repaire) : leur référence peut être incomplète.
- L'effet sur la recherche, le tri et la rédaction n'est pas mesuré ici.

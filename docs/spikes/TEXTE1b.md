# TEXTE1b — Une extraction plus complète du texte des articles

| | |
|---|---|
| Statut | Conclue : partiel |
| Durée maximale | 2 h de mesure |
| Temps passé | 3 h de préparation et d'analyse (journal de temps, TEXTE1b) ; mesure en quelques minutes |
| Ouverte le / conclue le | 2026-11-01 / 2026-11-01 |
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

**Environnement.** VM .252. Aucun modèle, aucun accès réseau pour les extractions, rien d'écrit dans la Veille. Conteneur jetable de l'image du worker, sans réseau ; `trafilatura` 2.0.0 (Apache-2.0) est posé à côté pour le banc seul et n'entre pas dans le produit.

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

| Critère | Seuil | E0, actuelle | E1, repli sur la page | E2, trafilatura |
|---|---|---|---|---|
| Couverture médiane | ≥ 90 % | ✅ 91,5 % | ✅ 92,8 % | ✅ 98,8 % |
| Pages sous 50 % de la référence | ≤ 5 % | ❌ 7,7 % | ❌ 5,8 % | ✅ 3,8 % |
| Pollution médiane | ≤ 15 % | ✅ 8,4 % | ✅ 7,8 % | ✅ 8,1 % |
| Pages qui perdent plus de 20 points sur E0 | ≤ 5 % | ✅ 0 % | ✅ 0 % | ❌ 5,8 % |
| Pire des 4 sites, pages sous la moitié | ≤ 5 % | ❌ 28 % | ❌ 28 % | ❌ 21 % |
| Temps, p95 | ≤ 300 ms | ✅ 82 ms | ✅ 87 ms | ✅ 43 ms |

**Proportion réelle.** Sur la référence (52 pages, 4 par site, sans pondération) : 7,7 % des pages gardent moins de la moitié de l'article avec E0 (4 pages), et 23 % moins de 70 % (12 pages). Le repère automatique, pondéré par site, donne 13,0 %, mais il est imprécis : sur les 52 pages, il en signale 8 quand la référence en compte 4, et 3 seulement en commun. Il compte comme article le texte en trop de `trafilatura`, surtout sur Next.ink (72 % de pollution sur deux pages à mur payant). La proportion utile est donc une fourchette : **environ 8 à 13 % sous la moitié, et près d'un quart des textes amputés d'au moins 30 %**, sur peu de pages de référence.

**Sites**, part des pages sous la moitié du texte le plus long (repère automatique) :

| Site | E0 | E1 | E2 |
|---|---|---|---|
| Futura Sciences | 28 % | 28 % | 0 % |
| Next.ink (repère trompeur, voir plus haut) | 28 % | 28 % | 0 % |
| Motor Tribu | 25 % | 25 % | 2 % |
| La Libre Belgique | 22 % | 15 % | 2 % |
| L'Avenir | 18 % | 18 % | 0 % |
| La DH | 15 % | 10 % | 0 % |
| Audiofanzine | 15 % | 8 % | 2 % |
| Les Numériques | 12 % | 0 % | 15 % |
| Auto-Moto | 10 % | 0 % | 10 % |
| RTBF Info | 3 % | 0 % | 21 % |
| Bruzz | 0 % | 0 % | 2 % |
| Le repaire des motards | 0 % | 0 % | 0 % |
| LeMonde.fr | 0 % | 0 % | 0 % |

**Pertes d'E2.** 3 pages sur 52 reculent de plus de 20 points : 2 de RTBF (de 87 % à 29 %, de 80 % à 49 %) et 1 d'Auto-Moto (de 99 % à 79 %).

Fichiers : `spikes/texte1/results/summary.txt`. Les pages restent sur la VM.

## 5. Conclusion

**Partiel.** Aucune variante ne tient les 6 critères. E2 améliore nettement la couverture (de 91,5 % à 98,8 %) et divise par deux les pages sous la moitié, sans plus de pollution en médiane et en moins de temps ; elle rate deux critères, à cause de RTBF surtout. E1 apporte peu seule, mais elle corrige exactement les sites où E2 perd.

## 6. Conséquences

| Document ou choix | Conséquence | ADR |
|---|---|---|
| Extraction du produit (`readability-lxml`) | Inchangée à cette étape. Remplacement à soumettre à Joël, une fois E3 validée (§8) | À proposer si validée |
| `trafilatura` | Licence compatible (Apache-2.0), mais pas de dépendance ajoutée sans décision | |

Le code de `spikes/texte1/` reste un banc ; rien n'est repris dans `backend/` à cette étape.

## 7. Ce que la preuve n'a pas couvert

- Un seul auteur de la référence, sur 4 pages par site : les résultats par site viennent du repère automatique, pas de la référence.
- Une page de 2026-11-01 peut différer de celle de la collecte : pas d'effet sur la comparaison des variantes.
- Une page qui garde plus de 70 blocs n'a été lue que sur ses 70 premiers (3 pages de Les Numériques, 3 de Futura, 1 du Repaire) : leur référence peut être incomplète.
- L'effet sur la recherche, le tri et la rédaction n'est pas mesuré ici.

## 8. Après la conclusion : une piste, hors protocole

E3 : E2, sauf si son texte fait moins de la moitié de ce que la page marque comme article ; alors ce texte marqué. Idée venue **après** avoir vu les résultats, sur les mêmes pages : c'est une hypothèse, pas un résultat (`spikes/texte1/texte1b_after.py`, `results/exploration.txt`).

Sur les mêmes pages : couverture médiane 98,8 %, 1,9 % de pages sous la moitié, pollution médiane 8,1 %, 3,8 % de pages qui reculent, RTBF de 21 % à 0 %. Restent Les Numériques à 15 %, une page de RTBF à 49 %, et la pollution de Next.ink. Elle devrait être jugée sur d'autres pages, avec les mêmes seuils et une nouvelle référence.

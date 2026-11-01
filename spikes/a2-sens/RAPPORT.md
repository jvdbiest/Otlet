# Spike ADR-0045 — Recherche par le sens : rapport

Date : 2026-10-30. Matériel : VM du PC (.252, 4 vCPU i7-14700K, 8 Go) et VM du NAS (.249, Celeron J4025, 2 vCPU, 4 Go, référence basse). Données : les 4 213 éléments des 30 derniers jours de la Veille de Joël, exportés en lecture seule (`items.jsonl`). Aucun fournisseur IA, aucune écriture dans l'instance.

## Méthode

- `encode.py` encode le titre et les 300 premiers caractères du résumé de chaque élément avec un encodeur multilingue local (fastembed 0.7.3, ONNX, licence Apache-2.0).
- `evaluate.py` compare trois manières de trouver la matière de 7 questions qui ont échoué aux bancs du Reporter des 29 et 30 octobre :
  - **mots** : l'ensemble que trouve le moteur actuel avec les termes que qwen3:14b a donnés (prompt reporter-3, règles d'ADR-0044) ;
  - **sens** : les éléments les plus proches de la question, par le cosinus ;
  - **hybride** : les deux listes fusionnées par rang réciproque (RRF, k = 60).
- La **référence** de chaque question est une règle écrite à la main sur le titre et le résumé, dans les trois langues. Elle est approximative. Les premiers titres de chaque méthode ont aussi été relus à l'œil (`eval-*.txt` sur la VM).

## Résultats (éléments de référence trouvés dans les 30 premiers)

| Question | Référence | Mots | Sens (MiniLM) | Hybride (MiniLM) | Hybride (mpnet) |
|---|---|---|---|---|---|
| Situation financière des hôpitaux en Flandre | 3 | 0 | **3** (rangs 1 à 3) | **3** | 3 |
| Budget de la région Bruxelles-Capitale | 13 | 6 | 9 | 8 | 6 |
| Grèves à la SNCB | 1 (aucune grève SNCB réelle) | 0 | 0 | 0 | 0 |
| IA à l'école | 10 | 0 | 2 | 2 | 1 |
| Victimes de l'accident de train en Espagne | 22 | 15 | 19 (les 2 articles sur les victimes en tête) | **20** | 20 |
| Essais de motos récents | 24 | 7 | 5 | 6 | 10 |
| Pertes d'emploi en Belgique | 38 | 5 | 6 | **10** | 11 |

Relu à l'œil :
- Pour les hôpitaux, le sens place en tête les trois articles flamands (« Geldproblemen dwingen Vlaamse ziekenhuizen tot fusies », « Kleine ziekenhuizen maken nauwelijks nog winst », « De erfenis van de publieke ziekenhuizen: pensioenlasten »). Les mots n'en trouvaient aucun.
- Pour les grèves SNCB, le sens ne ramène plus la « Dacia Striker », mais des préavis de grève, des actions syndicales et des manifestations. Il n'y a pas de grève SNCB dans la Veille.
- Pour l'IA à l'école, le sens ramène des articles sur l'IA en général : le gain est faible.

## Coût

| | MiniLM-L12 multilingue (384 dim.) | mpnet-base multilingue (768 dim.) |
|---|---|---|
| Encodage, VM du PC | 15 ms par élément | 45 ms par élément |
| Encodage, VM du NAS | **322 ms par élément** (lots de 8) | non mesuré (3 fois plus lent attendu) |
| Mémoire au pic | 950 Mo (PC, lots de 32) ; **725 Mo** (NAS, lots de 8) | 1 930 Mo |
| Modèle sur disque | 0,22 Go | 1,0 Go |
| Index pour 4 213 éléments | 6,5 Mo | 12,9 Mo |

Sur le NAS, le flux d'environ 1 300 éléments par jour coûte environ 7 minutes d'encodage par jour, en tâche de fond. La reprise des 4 213 éléments existants coûte environ 23 minutes, une seule fois.

## Conclusions

1. **Le sens corrige ce que les mots ne peuvent pas corriger** : la langue (les hôpitaux flamands) et la reformulation (les victimes). L'hybride est le meilleur ou à égalité sur 5 questions sur 7. Il ne recule nettement sur aucune.
2. **MiniLM suffit.** mpnet n'apporte un gain que pour les motos, recule sur le budget bruxellois, et coûte trois fois plus de temps et deux fois plus de mémoire.
3. **Le coût à surveiller est la mémoire**, pas le temps : 725 Mo de plus dans le worker sur une machine de 4 Go. À mesurer avec la pile complète (ADR-0025), par exemple en chargeant le modèle seulement pendant l'encodage.
4. Le sens ne remplace ni les règles (opération, langue, période, lieu), ni la lecture par le modèle (« Vérifier en lisant »), qui reste utile pour écarter le bruit.

## Recommandation

Retenir l'option 1 d'ADR-0045 avec MiniLM-L12 multilingue. Mise en œuvre par étapes :
1. une migration qui active pgvector et ajoute le vecteur aux éléments ;
2. une tâche qui encode après chaque collecte, puis une reprise de l'existant ;
3. la fusion hybride dans le moteur de l'Assistant et du Reporter, les termes restant visibles ;
4. une mesure de mémoire de la pile complète sur le NAS avant de fermer le lot.

## Après la décision : sens-2 à sens-4 (2026-10-30)

- **Par question ou par concept** (`evaluate_concepts.py`) : chercher le sens concept par concept est plus précis (hôpitaux : 3 justes sur 4 ; victimes : 18 sur 23), mais trouve moins (budget bruxellois : 4 contre 8 ; emploi : 7 contre 10). Retenu : le sens de la question qui ouvre une recherche, les restrictions posées ensuite s'appliquant aussi aux éléments trouvés par le sens.
- **Seuil** (`closeness.py`) : les éléments pertinents des bancs sont presque tous au-dessus de 0,6 de proximité ; une question sur rien de la Veille (« curling en Mongolie ») plafonne à 0,53, et les grèves SNCB, absentes, à 0,58. Retenu : les 60 plus proches, s'ils dépassent 0,6.
- **Banc réel (sens-3, qwen3:14b, 9 sujets)** : les trois articles flamands sur les hôpitaux sortent dans les 6 premiers (aucun avant) ; « Qui sont les victimes ? » garde les deux articles qui les identifient ; les pertes d'emploi gagnent l'article néerlandais sur les licenciements collectifs ; aucune régression sur Tesla et le budget fédéral. L'IA à l'école reste bruitée.
- **Mémoire sur le NAS (sens-4)**, avec l'encodeur retenu (ONNX Runtime, sans fastembed) : sens d'une question en 3,9 s, modèle compris, 767 Mo au pic, rendus ensuite ; encodage en tâche de fond à 327 ms par élément. La pile d'Otlet au repos sur la VM .252 : worker 150 Mo, API 300 Mo, base 180 Mo. Le pic reste dans une machine de 4 Go. Il est transitoire : 2 à 4 secondes par question, quelques minutes par passe d'encodage.

## Le Reporter lit plus loin (2026-11-01)

Question de Joël : « Pourquoi risque t'il de faire très froid dans les jours qui viennent ? ». Cinq articles qui répondent étaient absents de l'ensemble de 56. Rejeu sans modèle et en lecture seule sur la VM .252 (`reporter_wide.py`, `reporter_wide_read.py`), avec les concepts conservés de chaque question.

**Deux causes.** Le modèle avait créé un concept obligatoire « risque » (risque, raison, cause, reden…) à partir de la question. Et surtout, quatre des cinq articles n'écrivent pas « froid » : seul le sens peut les trouver, or ils sont entre 0,37 et 0,53 de proximité, et le seuil de 0,6 ne laissait passer qu'un élément de toute la Veille. Le classement par le sens était pourtant bon : les articles sur la météo occupent les premiers rangs.

**Règles retenues, pour le Reporter seul.** La recherche de la Veille et les dossiers de l'Assistant ne changent pas.
- Les mots qui posent la question ne nomment plus de concept : le verbe devant son pronom (« risque t'il », « risquent-ils »), les mots de question, et ce qui est à venir (« dans les jours qui viennent »).
- Le sens : quand les mots ont trouvé quelque chose et que le meilleur élément atteint 0,55, on garde, parmi les 30 plus proches, ceux qui atteignent le meilleur moins 0,25, sans descendre sous 0,4. Au-dessus de 0,6, rien ne change. Si les mots ne trouvent rien, l'ancien seuil s'applique : « les élevages de lamas sur Mars » n'ajoute rien.

**Résultats sur 74 questions distinctes (262 tours).** Pertinents dans les 30 premiers / dans l'ensemble / taille de l'ensemble, d'après des règles écrites à la main et donc approximatives.

| Question | Avant | Après |
|---|---|---|
| Froid dans les jours qui viennent | 4 / 5 / 57 | 10 / 13 / 171 |
| Tempête Austen en Belgique | 29 / 38 / 49 | 30 / 41 / 53 |
| Budget de la Région bruxelloise | 9 / 9 / 56 | 9 / 9 / 78 |
| Concert d'Angèle à Bruxelles | 3 / 3 / 6 | 4 / 4 / 33 |
| Élections de mi-mandat | 20 / 27 / 47 | 20 / 33 / 63 |
| Résultats de Proximus | 4 / 4 / 4 | 4 / 4 / 4 |
| Piratage de Binance | 7 / 9 / 96 | 9 / 9 / 100 |
| Essais de motos | 4 / 11 / 64 | 4 / 12 / 66 |
| Pertes d'emploi en Belgique | 8 / 8 / 21 | 8 / 9 / 39 |
| Accident de train en Espagne | 19 / 19 / 22 | 19 / 19 / 22 |
| IA à l'école | 1 / 1 / 13 | 2 / 2 / 38 |
| Hôpitaux en Flandre | 3 / 3 / 8 | 3 / 3 / 20 |

- **Les cinq articles de la question : 0 avant, 4 après**, aux rangs 1, 21, 36 et 53. Le cinquième (« La météo va se bloquer… », 0,37) reste dehors.
- Aucune question de référence ne recule, aucun ensemble ne rétrécit, et la moitié des questions gardent leurs 30 premiers à l'identique. La règle des mots ne change qu'un tour sur 262, celui du froid.
- **Le prix : du bruit en queue de liste.** L'ensemble médian passe de 30,5 à 39,5 éléments. Relus à l'œil, les ajouts sont souvent voisins du sujet sans y répondre (les radars pour les péages, les manifestations pour les dockers). Quand la Veille n'a rien sur le sujet, ils sont hors sujet (« Qui a reçu le prix Nobel de physique 2026 ? »). Le tri coûtera plus de temps de modèle sur ces ensembles.

**Limites.**
- Les concepts conservés sont déjà passés par les règles : la mesure ne voit pas ce que le modèle répondrait à nouveau. Un essai réel reste à faire.
- Les seuils ont été choisis en regardant ces mêmes questions, dont celle du froid ; ils ne sont pas validés sur des questions à part.
- Sans le concept « risque », le mot « froid » seul trouve 148 articles, dont beaucoup ne font que le citer (« douche froide », un test de machine à café). Le cinquième article et ce bruit demandent autre chose.
- Un autre mot de la question reste exigé : « Les prix risquent-ils de grimper ? » exige toujours « grimper ».
- **Ukraine et présidentielle bulgare** (brief du 2026-11-01) : ces articles écrivent « Ukraine », donc la recherche les trouve à raison, et aucune règle de recherche ne doit les exclure. Le changement fait même monter l'un d'eux du rang 56 au rang 29 pour « Quelles sont les dernières actualités concernant l'Ukraine ? ». Ce cas relève du jugement du tri, pas de la recherche.

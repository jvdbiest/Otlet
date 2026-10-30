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

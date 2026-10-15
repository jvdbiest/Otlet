# S5b — Complément : mémoire de potion

| | |
|---|---|
| Statut | Conclue : échec (mémoire), qualité inchangée ; potion int8 retenu selon l'ADR-0024 |
| Durée maximale | 4 h (ADR-0024, point 2) |
| Temps passé | journal de temps, tâche S5b |
| Ouverte le / conclue le | 2026-10-15 / 2026-10-15 |
| Choix concernés | TC-10, budget mémoire solo (`TECH_CHOICES.md` §3.2), ADR-0024 |
| Commande de rejeu | sur la machine de mesure, depuis une copie de `spikes/s5-similarity` : `nohup sh run-s5b.sh > run-s5b.log 2>&1 &` |

> Les sections 1 à 3 sont commitées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

`potion-multilingual-128M`, chargé avec des poids réduits, tient-il sous 500 Mo sans perdre la qualité mesurée en S5 ?

## 2. Critères de réussite

| # | Critère | Seuil | Source |
|---|---|---|---|
| D1 | Mémoire du modèle, mesurée comme C1 de S5 | **≤ 500 Mo** | ADR-0024, point 2 |
| D2 | Détection sur la moitié de mesure, seuils calibrés comme en S5 | **≥ 90 %** | S5, C3 |
| D3 | Faux positifs sur la moitié de mesure | **≤ 5 %** | S5, C4 |
| D4 | Volume quotidien (2 000 éléments) vectorisé sur 2 vCPU | **≤ 30 min** | S5, C2 |

Une variante réussit si elle tient D1 à D4 à la fois. S5b réussit si au moins une variante réussit.

**Critère de décision (validation de Joël, ADR-0024)** : la mémoire qui compte est celle de la pile complète. Si S5b échoue et que la pile complète reste sous 3,4 Go, potion reste le modèle par défaut.

## 3. Protocole

- **Même corpus, mêmes scores, même calibration** que S5 (`docs/spikes/S5.md` §3) : les fonctions de `s5.py` sont réutilisées sans modification.
- **Chargement** par `model2vec` 0.9.0 (MIT), qui lit les poids d'origine de `minishlab/potion-multilingual-128M` et sait les convertir au chargement. Trois variantes, dans cet ordre :
  1. `float32` : référence, pour séparer l'effet de la bibliothèque de celui de la réduction ;
  2. `float16` : poids en demi-précision ;
  3. `int8` : poids quantifiés sur 8 bits.
- La réduction du vocabulaire au français et à l'anglais, envisagée par l'ADR-0024, est **écartée** : il faudrait construire une liste de jetons à partir d'un corpus, ce qui sort des 4 h. La quantification `int8` vise le même gain sans toucher au vocabulaire.
- **D1** : RSS du processus après chargement et vectorisation des 2 000 éléments, moins la RSS avant le chargement, comme en S5. Une variante par conteneur, limité à 2 vCPU, sur la VM du NAS. Encodage sans multiprocessus, par lots de 64 passages comme en S5.
- **Information** : écart des scores sémantiques de chaque variante avec ceux de la variante `float32`, sur les 200 paires.
- Résultats JSON dans `spikes/s5-similarity/results/`, préfixe `s5b-`.

### 3.1 Si échec

Application de l'ADR-0024 tel qu'accepté : potion reste le modèle par défaut si la pile complète reste sous 3,4 Go. Le chargement retenu est alors le plus léger des chargements mesurés qui tient D2 à D4.

## 4. Mesures

Exécution du 2026-10-15 sur la VM du NAS (Celeron J4025, 2 vCPU), conteneur limité à 2 vCPU, `model2vec` 0.9.0. Résultats bruts : `spikes/s5-similarity/results/s5b-*.json` et `run-s5b.log`.

| Critère | Seuil | float32 | float16 | int8 |
|---|---|---|---|---|
| D1 mémoire du modèle | ≤ 500 Mo | 1 236 Mio ✗ | 993 Mio ✗ | 870 Mio ✗ |
| D2 détection (moitié de mesure) | ≥ 90 % | 90 % ✓ | 90 % ✓ | 90 % ✓ |
| D3 faux positifs | ≤ 5 % | 0 % ✓ | 0 % ✓ | 0 % ✓ |
| D4 2 000 éléments (47 251 passages) | ≤ 30 min | 21 s ✓ | 25 s ✓ | 21 s ✓ |
| Seuils calibrés (même langue / langues différentes) | — | 0,640 / 0,549 | 0,640 / 0,549 | 0,639 / 0,548 |

**Information** : écart des scores sémantiques avec la variante float32, sur les 200 paires : au plus 0,0007 en float16 et 0,011 en int8 (en moyenne 0,0002 et 0,002). Les paires détectées sont les mêmes pour les trois variantes : 88 % en même langue, 92 % en langues différentes. Pour mémoire, le chargement ONNX de `fastembed` mesuré en S5 occupait 1 344 Mio.

**Durée** : environ 1 h de travail sur 4 h ; le calcul a pris 3 min.

## 5. Conclusion

**Échec.** Aucune variante ne descend sous 500 Mo. La qualité, elle, ne bouge pas.

- Réduire les poids ne gagne que ce qu'ils pèsent : 512 Mo en float32, 256 en float16, 128 en int8. La mémoire passe ainsi de 1 236 à 870 Mio. Il reste environ 740 Mio, qui ne viennent pas des poids. Ils viennent vraisemblablement du tokenizer et de son vocabulaire de 500 353 jetons. C'est une déduction : la mémoire du tokenizer seul n'a pas été mesurée.
- La réduction du vocabulaire, écartée du protocole, est donc le seul levier restant sous 500 Mo. Elle n'est plus nécessaire à la décision.
- **Application de l'ADR-0024 (§3.1)** : potion reste le modèle par défaut, chargé par `model2vec` en **int8**, le plus léger des chargements qui tiennent D2 à D4 (870 Mio). La pile complète, déduite en additionnant des mesures séparées, resterait à environ 1,1 Go au repos et à 2,4 Go en charge réelle estimée (S1 1,10 Go + 870 Mio + 400 Mo de travail du worker), sous les 3,4 Go du profil solo. Cette somme doit être vérifiée par une mesure de la pile entière quand le worker chargera le modèle.

## 6. Conséquences

| Document ou choix | Conséquence | ADR |
|---|---|---|
| TC-10 | Modèle par défaut : potion-multilingual-128M chargé par `model2vec` (MIT) en int8, à la place du chargement ONNX de `fastembed` | ADR-0024 (accepté), point 3 tel que validé par Joël |
| Budget mémoire solo (`TECH_CHOICES.md` §3.2) | La ligne du modèle passe de 150 à 500 Mo à environ 870 Mio ; le total de la pile reste le critère | ADR-0024 (accepté) |

## 7. Ce que la preuve n'a pas couvert

- La mémoire de la pile entière avec le modèle chargé dans le worker, qui reste à mesurer.
- La mémoire du tokenizer seul, et la réduction du vocabulaire au français et à l'anglais.
- Une mesure dans le worker réel, où le modèle partagerait le processus avec les autres tâches.

## Validation de Joël (2026-10-15)

Conclusion validée. Potion est retenu, et le chargement int8 devient le mode par défaut, puisqu'il donne les mêmes résultats que float32 et float16 avec moins de mémoire. Le critère déterminant est le fonctionnement correct de la pile complète sur une configuration réaliste (ADR-0025).

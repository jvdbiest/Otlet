# S5b — Complément : mémoire de potion

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 4 h (ADR-0024, point 2) |
| Temps passé | journal de temps, tâche S5b |
| Ouverte le / conclue le | 2026-10-15 / — |
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

À remplir après la mesure.

## 5. Conclusion

À rédiger.

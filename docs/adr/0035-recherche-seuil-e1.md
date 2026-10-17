# ADR-0035 — Recherche plein texte : clore L2 pour É1, ou poursuivre

| | |
|---|---|
| Statut | Accepté (2026-10-17) |
| Date | 2026-10-17 |
| Décideur | Joël |
| Documents touchés | ADR-0021 (L2 de S1), ADR-0033, ADR-0034 ; `ROADMAP.md` §5.1 (S1) ; `TECH_CHOICES.md` §8.4 ; backlog d'É1 (P01) |
| Origine | Rapport P01d (conclu : échec, de peu) |

## Contexte

Le seuil de L2 vient de S1 : p95 < 300 ms pour chaque lecture principale, avec **4 clients simultanés**, sur la machine de référence basse (2 vCPU). La série P01 à P01d a corrigé trois défauts réels de la recherche (ADR-0033, migration 0013, ADR-0034). Sur le corpus réel de P01, P01d mesure maintenant :

| Famille | 4 clients (critère) | 1 client (information) |
|---|---|---|
| Q1 Mot fréquent | 415 ms | 128 ms |
| Q2 Mot rare | 295 ms | 95 ms |
| Q3 Deux ou trois mots | 178 ms | 70 ms |
| Q4 Expression | 324 ms | 118 ms |

Le temps qui reste est du calcul : lire les éléments d'un mot fréquent pour garder les 1 000 plus récents, puis les classer, et revérifier la position des mots d'une expression. Quatre recherches à la fois se partagent 2 vCPU.

É1 est une tranche verticale **personnelle** : un seul utilisateur, qui lance rarement deux recherches à la fois.

## Options

1. **Clore L2 pour É1 (recommandé).** Considérer que la recherche répond au besoin d'É1 : moins de 130 ms au p95 pour un utilisateur, et 295 à 415 ms quand quatre recherches arrivent ensemble. Le critère à 4 clients reste celui du profil d'équipe ; il est remesuré avant d'ouvrir Otlet à plusieurs utilisateurs, et lors de la mesure de la pile complète d'I4 (VM vierge, P04). L'écart est consigné dans ADR-0021.
2. **Poursuivre maintenant.** Une remesure P01e après un ou plusieurs leviers : partitionner les éléments par mois (`TECH_CHOICES.md` §8.4, levier 1), classer moins d'éléments (fenêtre plus petite, que Joël a écartée dans l'ADR-0034), ou un classement moins coûteux. Chacun demande du temps sur I1, avec un gain attendu de l'ordre de 100 ms sur Q1.

## Décision

Décision de Joël du 2026-10-17 : « Je considère P01 comme suffisamment conclue pour É1. » L'option 1 : la recherche est acceptée pour É1. Le seuil de 300 ms avec 4 clients n'est pas modifié. Il redevient un critère au moment où Otlet sert plusieurs utilisateurs, et il est remesuré à I4.

## Conséquences

- I1 peut se clore sans nouvelle remesure, avec la semaine d'usage de X02.
- Le risque est connu et chiffré : 415 ms au p95 pour un mot fréquent quand quatre recherches tombent en même temps.
- Le banc et le corpus de P01 sont gardés (`spikes/p01-search`, `~/p01-corpus` sur la VM du NAS) pour la remesure.

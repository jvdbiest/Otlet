# Journal de temps

Sans mesure, aucun critère d'arrêt de la roadmap ne fonctionne (`ROADMAP.md` §13.2). Coût visé : 15 minutes par semaine.

## Saisie

Une ligne par session de travail dans `journal-temps.csv`, saisie à la fin de la session.

| Colonne | Format | Règle |
|---|---|---|
| `date` | AAAA-MM-JJ | Jour de la session |
| `heures` | décimal au quart d'heure (`1.75`) | Temps de travail concentré, pauses exclues ; le temps passé avec un assistant de programmation compte |
| `domaine` | voir ci-dessous | Un seul par ligne ; scinder la session si besoin |
| `etape` | `E0`, `E1`, `E2`, `L1b` | Étape de la roadmap en cours |
| `tache` | ID du backlog (`S1.4`, `B05`) ou `-` | Obligatoire pour `preuve` et `fonction` |
| `note` | texte court, sans virgule | Facultatif |

| Domaine | Contenu | Critères |
|---|---|---|
| `preuve` | Tâches des preuves de concept S1 à S7 | CA1, vélocité |
| `fonction` | Code, tests et documentation des fonctions et du socle | CA1, vélocité |
| `compte` | Parcours de compte : inscription, connexion, 2FA, récupération, sessions | CA5 |
| `entretien` | Mises à jour de dépendances, CI cassée, correctifs, petites refontes | CA6 |
| `projet` | Prérequis matériels, revues du registre, financement, juridique, gouvernance, communication | Part « projet » |
| `absence` | Semaine non travaillée annoncée : une ligne à `0` dans la semaine | Exclut la semaine des moyennes de CA2 |

Exemple :

```csv
date,heures,domaine,etape,tache,note
2026-10-12,1.5,fonction,E0,B01,premier commit
2026-10-12,0.5,projet,E0,-,location du VPS
2026-12-28,0,absence,E0,-,congés
```

## Revue hebdomadaire

```sh
python tools/journal_temps.py
```

Le script affiche les heures brutes des huit dernières semaines, les alertes CA2 (moyenne trop basse) et CA3 (plafond de 20 h dépassé quatre semaines de suite), la répartition du mois par domaine (CA5, CA6), le cumul de l'étape face aux seuils de CA1, et pour chaque tâche commencée les heures réelles contre l'estimation (⚠ au-delà de +10 %).

Mettre à jour le statut des tâches (`a_faire`, `en_cours`, `fait`) dans `backlog-E0.csv`. Une tâche est `fait` quand son critère « fini quand » du plan est vrai.

## Vélocité

Vélocité = somme des estimations des tâches faites ÷ somme des heures réelles passées dessus. Supérieure à 1 : plus rapide que l'estimation. Elle est calculée à P1 sur tout É0 et sert à recalibrer É1 (`ROADMAP.md` §2.4).

## Confidentialité

Le journal est public avec le dépôt : dates et durées seulement, jamais d'horaires. Pour le garder privé, ajouter `docs/projet/journal-temps.csv` à `.gitignore`.

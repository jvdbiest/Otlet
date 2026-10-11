# Journal de temps

Sans mesure, aucun critère d'arrêt de la roadmap ne fonctionne (`ROADMAP.md` §13.2). Règle retenue par Joël le 2026-10-11 : **une estimation grossière par tâche terminée**, pas de saisie par session.

## Saisie

Une ligne par tâche terminée dans `journal-temps.csv`, saisie quand la tâche passe à `fait`.

| Colonne | Format | Règle |
|---|---|---|
| `date` | AAAA-MM-JJ | Jour où la tâche est terminée |
| `heures` | décimal (`3` ou `2.5`) | Estimation grossière du temps passé sur la tâche ; le temps passé avec un assistant de programmation compte |
| `domaine` | voir ci-dessous | Un seul par ligne |
| `etape` | `E0`, `E1`, `E2`, `L1b` | Étape de la roadmap en cours |
| `tache` | ID du backlog (`S1.4`, `B05`) ou `-` | Obligatoire pour `preuve` et `fonction` |
| `note` | texte court, sans virgule | Facultatif |

| Domaine | Contenu | Critères |
|---|---|---|
| `preuve` | Tâches des preuves de concept S1 à S7 | CA1, vélocité |
| `fonction` | Tâches du socle et des fonctions (code, tests, documentation) | CA1, vélocité |
| `compte` | Parcours de compte : inscription, connexion, 2FA, récupération, sessions ; vide en É0 | CA5 |
| `entretien` | Facultatif : un gros chantier d'entretien noté comme une tâche | CA6 (indicatif) |
| `projet` | Facultatif : prérequis matériels, juridique, gouvernance, communication | Part « projet » (indicatif) |

Exemple :

```csv
date,heures,domaine,etape,tache,note
2026-10-11,3,fonction,E0,B02,estimation grossière
```

## Ce qui est mesuré, ce qui est jugé

- **Calculé par le script** : heures réelles contre estimation par tâche (⚠ au-delà de +10 %), cumul de l'étape face aux seuils de CA1, vélocité.
- **Jugement de Joël** : CA2 et CA3 (heures hebdomadaires trop basses ou au-delà du plafond de 20 h) et la part « entretien » de CA6. Ils ne sont plus calculés ; Joël les signale lui-même à chaque point de décision.

## Revue

```sh
python tools/journal_temps.py
```

Le script affiche le cumul de l'étape face aux seuils de CA1, pour chaque tâche commencée les heures réelles contre l'estimation, les tâches `fait` sans ligne au journal, et la vélocité.

Mettre à jour le statut des tâches (`a_faire`, `en_cours`, `fait`) dans `backlog-E0.csv`. Une tâche est `fait` quand son critère « fini quand » du plan est vrai.

## Vélocité

Vélocité = somme des estimations des tâches faites ÷ somme des heures réelles passées dessus, sur les seules tâches qui ont une ligne au journal. Supérieure à 1 : plus rapide que l'estimation. Elle est calculée à P1 sur tout É0 et sert à recalibrer É1 (`ROADMAP.md` §2.4).

## Confidentialité

Le journal est public avec le dépôt : une durée par tâche, jamais d'horaires. Pour le garder privé, ajouter `docs/projet/journal-temps.csv` à `.gitignore` ; le script fonctionne pareil.

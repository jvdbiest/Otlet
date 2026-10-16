# ADR-0030 — Les tâches périodiques de maintenance sont lancées par les workers

| | |
|---|---|
| Statut | Accepté (2026-10-16) |
| Date | 2026-10-16 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §12.5 ; `TECH_CHOICES.md` §9.4 ; ADR-0022 |
| Origine | Tâche F04 du plan d'É1 (`docs/projet/plan-E1.md`) |

## Contexte

L'architecture prévoit un rôle `scheduler` : un seul planificateur actif grâce à un verrou de leader, des échéances en base, et des règles de rattrapage par type (`ARCHITECTURE.md` §12.5). Ce rôle sert aux échéances du domaine : publications planifiées dans le fuseau de la marque, fins de délai de grâce, collectes.

F04 a besoin de tâches périodiques plus simples, sans fuseau ni règle de rattrapage : la relance des tâches bloquées, chaque minute (ADR-0022), et la purge des sessions expirées, chaque heure (ADR-0029). Procrastinate sait les lancer lui-même : chaque worker tente de créer l'exécution due, et une ligne unique par échéance garantit qu'une seule réussit.

## Décision

1. **Les tâches périodiques de maintenance** (relance des tâches bloquées, purges) sont déclarées avec une expression cron UTC dans le registre des tâches (`otlet.jobs.application.registry`). Ce sont les workers qui les lancent, à la manière de Procrastinate.
2. **Le rôle `scheduler` reste réservé aux échéances du domaine**, avec verrou de leader et règles de rattrapage, comme prévu au §12.5. D'ici là, il continue à seulement démarrer et battre. Il recevra son premier travail avec la première échéance du domaine : la collecte planifiée des sources (U01) ou, au plus tard, les publications planifiées.

## Validation de Joël (2026-10-16)

« Je valide les tâches périodiques de maintenance exécutées par les workers, et je conserve le rôle de planificateur pour les opérations métier importantes (collectes, publications planifiées, rattrapage après incident). »

## Conséquences

- Pas de verrou de leader à écrire pour la maintenance : l'unicité vient de Procrastinate, testée en S2 sous arrêts brutaux.
- Une tâche de maintenance manquée pendant un arrêt est lancée une fois au redémarrage (la dernière échéance due), ce qui convient aux relances et aux purges.
- Deux mécanismes de périodicité coexisteront : la cron des workers pour la maintenance, le planificateur pour le domaine. La frontière est la suivante : une échéance qui dépend d'un fuseau, d'une règle de rattrapage ou d'une donnée d'un espace relève du planificateur.

## Options écartées

- Tout faire passer par le rôle `scheduler` dès F04 : il faudrait écrire le verrou de leader et le rattrapage pour deux tâches qui n'en ont pas besoin.
- Supprimer le rôle `scheduler` : les échéances du domaine en ont besoin (`ARCHITECTURE.md` §12.5).

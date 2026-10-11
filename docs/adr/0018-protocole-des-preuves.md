# ADR-0018 — Protocole des preuves de concept

| | |
|---|---|
| Statut | Accepté |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | `ROADMAP.md` §5.1, PP6 ; `RISKS.md` §8.1 |
| Origine | Plan d'exécution d'É0 §2 |

## Contexte

Une preuve sans seuil fixé d'avance finit toujours par « réussir » ; une preuve sans échéance absorbe le calendrier.

## Décision

1. Avant toute mesure, le rapport `docs/spikes/Sx.md` est commité avec la question, les seuils, le protocole et la durée maximale (gabarit : `docs/spikes/MODELE.md`). Les seuils peuvent être ajustés à ce moment-là, **jamais après** ; l'historique Git en fait foi.
2. Le temps passé est suivi au journal de temps par identifiant de tâche (`S1.4`…). À la durée maximale, la preuve **conclut** avec ce qu'elle a mesuré : succès, échec ou partiel.
3. Les mesures brutes de synthèse (JSON) sont versionnées ; chaque preuve se rejoue par une commande unique.
4. Une conclusion qui contredit un document validé produit un ADR « proposé », soumis à Joël. Le travail continue sur la preuve suivante pendant la décision, sauf dépendance directe (plan d'É0 §2).
5. Le code d'une preuve reste dans `spikes/` (ADR-0014).

## Conséquences

- Un échec documenté est un résultat valide ; il déclenche la colonne « Si échec » de `ROADMAP.md` §5.1.
- Le dépassement d'une durée maximale de plus de 10 % sans décision écrite de Joël empêche la clôture d'É0.

## Options écartées

- Seuils fixés après une première exploration : biais de confirmation.
- Prolonger une preuve « presque concluante » : c'est la dérive que CA1 cherche à arrêter.

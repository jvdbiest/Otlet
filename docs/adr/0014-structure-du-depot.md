# ADR-0014 — Structure du dépôt et isolement du code des preuves

| | |
|---|---|
| Statut | Accepté |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §7 ; `TECH_CHOICES.md` §5.4, §19 |
| Origine | Plan d'exécution d'É0 §3 |

## Contexte

Une seule image OCI (TC-13) contient le back-end Python et l'interface construite ; les preuves de concept produisent du code de mesure qui ne doit pas devenir du code produit par inertie.

## Décision

1. **Monodépôt** : `backend/`, `frontend/`, `deploy/`, `spikes/`, `tools/`, `docs/`.
2. Back-end : `backend/src/otlet/`, un sous-paquet par module de l'architecture, chacun en `domain/`, `application/`, `adapters/` ; `platform/` pour le noyau technique partagé ; `entrypoints/` (API, worker, planificateur, ligne de commande) au sommet.
3. **Le code de `spikes/` n'est jamais importé par `backend/`**. Ce qui est conservé d'une preuve est réécrit dans `backend/` avec ses tests. Exception : le squelette de S6, écrit directement comme code définitif.
4. `spikes/` n'est soumis ni au typage strict ni à la couverture ; chaque preuve doit s'exécuter par une commande unique documentée dans son rapport.
5. Code, identifiants et commentaires en anglais ; documentation et messages de commit en français jusqu'au lot 1b.

## Conséquences

- Les modules sont créés à leur première utilisation (É1), pas d'avance.
- Les noms anglais des modules sont fixés par ADR-0017 en même temps que les contrats d'imports.

## Options écartées

- Dépôts séparés back-end / interface : deux CI, deux versions à synchroniser, pour un seul mainteneur.
- Preuves dans des dépôts jetables : on perd la traçabilité entre mesure et décision.

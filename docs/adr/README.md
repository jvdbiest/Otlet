# Registre des décisions

Les documents de `docs/design/` sont figés à leur version 1.0 (2026-10-11). Ils sont la base d'hypothèses du projet ; toute modification passe par un ADR de ce dossier (ADR-0012).

## Décisions antérieures (dans les documents de conception)

| Référence | Où |
|---|---|
| ADR-01 à ADR-11 (architecture) | `docs/design/ARCHITECTURE.md` §25 |
| D1 à D13 (fonctionnel) | `docs/design/FUNCTIONAL_ANALYSIS.md` |
| DA1 à DA10 (architecture) | `docs/design/ARCHITECTURE.md` §27 |
| TC-01 à TC-18, DT1 à DT14 (technique) | `docs/design/TECH_CHOICES.md` §26 et §27 |
| DR1 à DR9 (risques) | `docs/design/RISKS.md` |
| DRM1 à DRM7 (roadmap) | `docs/design/ROADMAP.md` §15 |

## Décisions du dépôt

La numérotation continue celle de l'architecture.

| ADR | Titre | Statut |
|---|---|---|
| [0012](0012-decisions-dans-le-depot.md) | Décisions consignées dans le dépôt | Accepté |
| [0013](0013-licence-et-dco.md) | Licence AGPL-3.0-or-later et DCO | Accepté |
| [0014](0014-structure-du-depot.md) | Structure du dépôt et isolement des preuves | Accepté |
| [0015](0015-forge-et-integration-continue.md) | Forge et intégration continue | Accepté, mis en œuvre (B04) |
| [0016](0016-chaine-d-outils.md) | Chaîne d'outils | Accepté |
| [0017](0017-contrats-d-imports.md) | Contrats d'imports | Accepté |
| [0018](0018-protocole-des-preuves.md) | Protocole des preuves de concept | Accepté |
| [0019](0019-secrets-dechiffres-par-le-worker.md) | Les secrets sont déchiffrés par le worker seul | Accepté (S6) |
| [0020](0020-demarrage-et-tls-de-la-pile-solo.md) | Démarrage et TLS de la pile solo | Accepté (S6) |
| [0021](0021-rls-et-recherche-plein-texte-apres-s1.md) | RLS maintenue, recherche plein texte à classement borné | Accepté (S1) |
| [0022](0022-file-de-taches-procrastinate.md) | File de tâches : Procrastinate, avec relance des tâches bloquées | Proposé (S2) |
| [0023](0023-format-de-document-et-editeur.md) | Format « Document plateforme v1 » et éditeur Tiptap | Proposé (S3) |

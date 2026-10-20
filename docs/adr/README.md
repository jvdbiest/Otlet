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
| [0022](0022-file-de-taches-procrastinate.md) | File de tâches : Procrastinate, avec relance des tâches bloquées | Accepté (S2) |
| [0023](0023-format-de-document-et-editeur.md) | Format « Document plateforme v1 » et éditeur Tiptap | Accepté (S3) |
| [0024](0024-modele-d-embeddings-et-seuils-apres-s5.md) | Modèle d'embeddings statique et seuils du garde-fou | Accepté (S5) |
| [0025](0025-qualite-avant-profil-materiel.md) | La qualité du produit prime sur le profil matériel | Accepté |
| [0026](0026-idempotence-des-connecteurs-cms.md) | Idempotence des connecteurs CMS par marqueur natif, « WordPress d'abord » confirmé | Accepté (S7) |
| [0027](0027-passerelle-ia.md) | Passerelle IA : adaptateurs maison, budget à réservation, fournisseurs bloqués par défaut | Accepté (S4) |
| [0028](0028-comptes-identites-et-contexte-utilisateur.md) | Comptes à identités multiples et contexte de sécurité de l'utilisateur | Accepté (F01) |
| [0029](0029-sessions-et-protections-de-connexion.md) | Sessions serveur, CSRF et limitation des tentatives de connexion | Accepté (F02) |
| [0030](0030-taches-periodiques-de-maintenance.md) | Les tâches périodiques de maintenance sont lancées par les workers | Accepté (F04) |
| [0031](0031-collecte-des-sources.md) | Collecte des sources : client protégé, règles des sites et statut juridique | Accepté (U01) |
| [0032](0032-sujets-score-doublons-recherche.md) | Sujets, score lexical expliqué, doublons et recherche | Proposé (U02) |
| [0033](0033-recherche-plein-texte-sous-rls.md) | Recherche plein texte par une fonction dédiée, sous RLS | Accepté (P01) |
| [0034](0034-recherche-requete-fusionnee.md) | Recherche plein texte : une seule requête pour toutes les langues | Accepté (P01c) |
| [0035](0035-recherche-seuil-e1.md) | Recherche plein texte : clore L2 pour É1, ou poursuivre | Proposé (P01d) |
| [0036](0036-editeur-versions-et-mise-en-forme.md) | Éditeur : enregistrer une version, mise en forme libre, images et exports | Accepté (X03) |
| [0037](0037-bibliotheque.md) | Bibliothèque : l'article au centre, le brief comme atelier | Accepté (X04) |
| [0038](0038-garde-fous-et-mesure-de-la-redaction.md) | Rédaction : contrôles après génération et mesure, plutôt que retouches du prompt | Accepté (U05 lot 1) |
| [0039](0039-declarations-de-droits.md) | Déclaration de droits sur un texte réservé par son éditeur | Accepté (U01) |

# ADR-0028 — Comptes à identités multiples et second contexte de sécurité, celui de l'utilisateur

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-16 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §8.1, §19.2 et §19.3 ; ADR-0021 (politique de RLS) ; `TECH_CHOICES.md` §5.3 |
| Origine | Tâche F01 du plan d'É1 (`docs/projet/plan-E1.md`) |

## Contexte

L'ADR-0021 rend la RLS forcée obligatoire sur toutes les tables métier, filtrées par l'espace courant (`app.workspace_id`). Or un compte n'appartient pas à un espace : il appartient à l'instance, et il peut être membre de plusieurs espaces (`ARCHITECTURE.md` §19.3). La roadmap demande aussi un « modèle de comptes à identités multiples dès le départ » (`ROADMAP.md` §5.2) : un mot de passe en É1, puis OpenID Connect et les clés de sécurité, sans refaire les comptes.

Il manque donc trois choses : une barrière pour les tables de comptes, qui n'ont pas d'espace ; un moyen de lister ses espaces avant d'en avoir choisi un ; un moyen de retrouver une identité à la connexion, avant tout contexte.

## Décision

1. **Un compte, plusieurs identités.** La table `users` porte le compte. La table `user_identities` porte les manières de se connecter : `kind` (`password`, plus tard `oidc`, `webauthn`), `issuer` (vide pour une identité locale), `subject` (identifiant de connexion normalisé) et `credential` (empreinte de mot de passe ou clé publique). Le triplet (`kind`, `issuer`, `subject`) est unique. Un nouveau type d'identité ne demande pas de migration.
2. **Un second contexte, celui de l'utilisateur** (`app.user_id`). Il est posé dans la même transaction et dans le même aller-retour que l'espace, par `otlet.platform.database.scoped_transaction`. Il est lui aussi local à la transaction.
3. **RLS forcée sur toutes les tables**, sauf `alembic_version` et `instance_settings`. Un test vérifie cette règle sur le schéma réel.
   - Tables métier : la ligne de l'espace courant, rien d'autre (`otlet.platform.rls.workspace_scoped`).
   - `users` et `user_identities` : le compte de l'utilisateur courant. Les membres de l'espace courant voient aussi les autres comptes de l'espace, mais pas leurs identités.
   - `workspaces` et `workspace_members` : l'espace courant, plus les espaces dont l'utilisateur courant est membre, pour qu'il puisse passer de l'un à l'autre. L'écriture reste limitée à l'espace courant.
4. **Connexion par une seule fonction**, `find_identity(kind, issuer, subject)`. Elle appartient au propriétaire du schéma (`SECURITY DEFINER`) et seul le rôle applicatif peut l'appeler. Elle renvoie l'identité trouvée et l'état du compte, rien d'autre. C'est le seul chemin pour lire une identité sans contexte. Les politiques des tables de comptes l'autorisent par `current_user = 'otlet_owner'`, un rôle que le rôle applicatif ne peut pas prendre.
5. **Identifiants UUIDv7** générés par PostgreSQL 18 (`uuidv7()`), conformément à `ARCHITECTURE.md` §8.5.

## Conséquences

- « Sans contexte = zéro ligne » vaut pour toutes les tables, y compris les comptes. Cette règle est testée en CI (`tests/platform/test_accounts_schema.py`).
- Toute nouvelle table métier doit appeler `rls.workspace_scoped` dans sa migration. À défaut, le test de couverture échoue.
- La connexion (F02) appellera `find_identity`, vérifiera l'empreinte Argon2id, puis ouvrira les transactions suivantes avec le contexte de l'utilisateur.
- Le rôle applicatif peut encore modifier le compte de l'utilisateur courant, dont `is_instance_admin`. C'est l'application qui contrôle ce droit (F02). Des privilèges par colonne pourront compléter ce contrôle si la revue ASVS d'É2 le demande.
- La RLS ajoute un aller-retour par transaction, comme l'ADR-0021 l'a déjà accepté. Le second contexte ne coûte pas d'aller-retour supplémentaire.

## Options écartées

- Tables de comptes sans RLS : la règle « sans contexte = zéro ligne » aurait une exception là où une fuite coûte le plus.
- Rôle de connexion séparé, autorisé à contourner la RLS : un mot de passe de base de plus à gérer, pour l'effet d'une seule fonction.
- Identifiant de connexion porté par `users` (une seule identité) : il faudrait migrer les comptes à l'arrivée d'OpenID Connect, ce que la roadmap exclut.

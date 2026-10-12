# ADR-0019 — Les secrets sont déchiffrés par le worker seul

| | |
|---|---|
| Statut | Accepté (2026-10-12) |
| Date | 2026-10-12 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §25 (ADR-11) ; `RISKS.md` §4.12 (R-S03), M-06, DR6 |
| Origine | Rapport S6, critère C3 |

## Contexte

ADR-11 chiffre les secrets avec une clé maîtresse donnée à l'instance, donc à l'API comme au worker. Une compromission du processus API, le plus exposé, livrerait alors les mots de passe d'application WordPress et les clés Ghost de toutes les marques (R-S03). DR6 proposait de réserver le déchiffrement au worker, sous réserve de S6. S6 l'a démontré : depuis le conteneur API, aucune ouverture n'est possible, ni par la commande prévue ni avec tout ce que le conteneur contient. Le worker, lui, ouvre le même secret (`docs/spikes/S6.md` §4).

## Décision

1. Chaque instance a une paire de clés X25519, générée à l'installation par `deploy/configure.sh`.
2. L'API et tout rôle exposé scellent les secrets avec la clé publique : échange X25519 éphémère, HKDF-SHA256, AES-256-GCM, nom du secret authentifié, identifiant de clé stocké.
3. La clé privée est montée, en secret Compose, dans le seul conteneur worker, jamais dans l'image ni dans une variable d'environnement.
4. Le contrat d'imports `secrets-worker-only` interdit à `otlet.entrypoints.api` d'importer `otlet.platform.secrets.opening`.
5. L'enveloppe d'ADR-11 reste : les clés de données par espace (É1) seront scellées de la même façon.

## Conséquences

- R-S03 est à recoter à la revue du registre (P1) : la compromission de l'API seule ne donne plus les jetons de publication.
- Toute fonction qui utilise un secret en clair (test de connexion CMS, appel IA) s'exécute dans le worker, jamais dans une requête HTTP.
- La clé privée doit être sauvegardée à part (`installation.md`, `mise-a-jour.md`). Sa perte rend les secrets irrécupérables.
- Reste à écrire en É1 : la rotation de la paire de clés.

## Options écartées

- Clé maîtresse partagée (ADR-11 tel quel) : ne protège pas contre la compromission de l'API.
- Gestionnaire de secrets externe obligatoire (Vault, etc.) : contraire à l'auto-hébergement simple.

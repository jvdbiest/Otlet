# ADR-0020 — Démarrage et TLS de la pile solo

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-12 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §20.3 et §20.4 |
| Origine | Rapport S6 |

## Contexte

`ARCHITECTURE.md` §20.3 prévoit une adresse e-mail pour les certificats. §20.4 prévoit des migrations au démarrage précédées d'une sauvegarde, sans dire qui les exécute quand plusieurs conteneurs démarrent. S6 a aussi montré qu'une instance jointe par adresse IP était inaccessible en HTTPS : sans nom de domaine, les clients n'envoient pas de SNI, et Caddy refusait la connexion (`docs/spikes/S6.md` §4, incidents).

## Décision

1. Pas d'adresse e-mail pour les certificats : Let's Encrypt ne l'exige pas et n'envoie plus d'avis d'expiration. La configuration de déploiement se limite au domaine, au mot de passe de la base et à la paire de clés des secrets.
2. Caddy reçoit `default_sni` égal à `OTLET_DOMAIN`, pour qu'une instance jointe par adresse IP (réseau local, NAS) fonctionne en HTTPS avec l'autorité locale de Caddy.
3. Ordre de démarrage dans Compose : `db`, puis `backup` (copie `pg_dump`, cinq gardées), puis `migrate` (service ponctuel, `otlet migrate upgrade`), puis `api` et `worker`, puis `caddy`. Un échec de la sauvegarde ou de la migration empêche l'application de démarrer.
4. Le retour arrière fait descendre le schéma avec la nouvelle version, avant de relancer l'ancienne (`docs/exploitation/mise-a-jour.md`).

## Conséquences

- Une sauvegarde à chaque démarrage, même sans migration : coût négligeable en solo, à revoir pour de grosses bases.
- Lancer une ancienne version sur un schéma plus récent bloque le démarrage au lieu de corrompre les données.

## Options écartées

- Migrations lancées par le processus API au démarrage : course entre plusieurs processus Uvicorn et le worker.
- Sauvegarde par `pg_dump` dans l'image applicative : le client PostgreSQL de Debian n'a pas la même version majeure que le serveur 18.

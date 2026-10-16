# ADR-0029 — Sessions serveur, CSRF et limitation des tentatives de connexion

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-16 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §19.2 ; `TECH_CHOICES.md` TC-14 ; ADR-0028 |
| Origine | Tâche F02 du plan d'É1 (`docs/projet/plan-E1.md`) |

## Contexte

É1 demande une identité minimale mais définitive (`ROADMAP.md` §5.2) : un compte administrateur, Argon2id, des sessions serveur, une protection CSRF, une limitation de débit de base et la ré-authentification. Le compte et ses identités existent depuis F01 (ADR-0028). Il reste à fixer la forme des sessions, la protection contre les requêtes intersites, le compteur d'échecs et les durées.

## Décision

1. **Mots de passe** : Argon2id par `argon2-cffi`, avec son profil par défaut (RFC 9106 « faible mémoire » : t = 3, m = 64 Mio, p = 4). Une empreinte faite avec d'anciens paramètres est refaite à la connexion suivante. Longueur : de 12 à 128 caractères, sans règle de composition, conformément à l'ASVS.
2. **Sessions serveur** : un jeton aléatoire de 256 bits, porté par un cookie `__Host-otlet_session` (`Secure`, `HttpOnly`, `SameSite=Strict`, chemin `/`). La base ne garde que son empreinte SHA-256, dans `user_sessions`, sous la RLS de l'utilisateur. Le cookie est lu par la seule fonction `find_session`, comme l'identité l'est par `find_identity`.
3. **Durées** : la session expire après 12 heures d'inactivité, et dans tous les cas 7 jours après la connexion. Une session expirée est supprimée dès qu'on la présente. Un compte désactivé perd aussitôt ses sessions.
4. **CSRF, deux barrières** : toute requête qui modifie un état est refusée si le navigateur la déclare venue d'un autre site (en-tête `Sec-Fetch-Site`). Toute requête authentifiée qui modifie un état doit en plus porter l'en-tête `X-CSRF-Token`, dérivé du jeton de session et renvoyé par `/api/auth/session`. Ce jeton ne demande aucun stockage et meurt avec la session.
5. **Limitation des tentatives** : au plus 5 échecs par identifiant de connexion et 20 par adresse cliente, sur une fenêtre de 15 minutes. Au-delà, la réponse est 429, avec `Retry-After`. Le compteur est en base (`auth_throttle`) et partagé par tous les processus de l'API. Il n'est accessible que par trois fonctions du propriétaire du schéma. Une connexion réussie remet à zéro le compteur de l'identifiant.
6. **Réponses indistinguables** : un identifiant inconnu, un mauvais mot de passe et un compte désactivé reçoivent la même réponse. Pour un identifiant inconnu, une empreinte leurre est vérifiée, afin que le temps de réponse soit le même.
7. **Ré-authentification** : les actions sensibles exigent un mot de passe saisi depuis moins de 10 minutes. La connexion compte comme saisie. Première action concernée : le changement de mot de passe, qui ferme aussi les autres sessions du compte.
8. **Compte administrateur** : il est créé par `otlet admin create`, le mot de passe étant lu sur l'entrée standard. Il n'y a pas de création de compte par le Web en É1.

## Conséquences

- L'interface (X01) appellera `/api/auth/login`, puis gardera en mémoire le jeton CSRF renvoyé, et l'ajoutera à chaque requête qui modifie un état.
- La fenêtre fixe du compteur permet jusqu'à deux fois la limite à cheval sur deux fenêtres. C'est accepté pour une limitation de base ; une fenêtre glissante pourra la remplacer sans changer l'API.
- Derrière Caddy, l'adresse cliente vue par l'API est celle du proxy tant que les en-têtes transmis ne sont pas déclarés de confiance. Le compteur par adresse est alors commun à tous les clients. Il faudra régler la confiance accordée aux en-têtes du proxy avant d'exposer l'instance (É2).
- Les sessions expirées qui ne sont jamais représentées restent en base : une purge planifiée viendra avec le planificateur (F04).
- Coût mémoire : une vérification Argon2id réserve 64 Mio pendant quelques dizaines de millisecondes, à chaque connexion seulement.

## Options écartées

- Jetons signés sans état (JWT) : impossibles à révoquer un par un, ce qui va contre la déconnexion et la fermeture des sessions au changement de mot de passe.
- Compteur d'échecs en mémoire : l'API tourne avec deux processus, et le compteur serait remis à zéro à chaque redémarrage.
- Jeton CSRF stocké en base : la dérivation du jeton de session apporte la même garantie sans écriture.

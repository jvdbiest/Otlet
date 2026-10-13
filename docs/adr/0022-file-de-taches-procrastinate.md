# ADR-0022 — File de tâches : Procrastinate, avec relance des tâches bloquées

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-13 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §9.3 (TC-06) ; `RISKS.md` R-T12, V8 |
| Origine | Rapport S2 (conclu : succès) |

## Contexte

S2 a soumis Procrastinate 3.10 et DBOS Transact 3.2 aux mêmes scénarios (`docs/spikes/S2.md` §4) : enfilage dans la transaction applicative, 1 000 tâches sous arrêts brutaux, annulation ciblée, connexions soumises à la RLS. Les deux tiennent tous les seuils. DBOS reprend plus vite (5 à 14 s contre 41 à 91 s), mais seulement quand l'exécuteur arrêté redémarre sous le même identifiant. Son modèle de flux de travail recouvre le moteur de pipelines du projet. Procrastinate demande une relance périodique des tâches bloquées, qu'il ne fait pas lui-même.

## Décision proposée

1. **Procrastinate** reste le moteur de la file, derrière l'interface du module `jobs` ; aucun autre module ne l'importe (contrat d'imports à ajouter avec le module).
2. Le module `jobs` fournit une **tâche périodique de relance des tâches bloquées**. Un worker est déclaré disparu après 30 s sans battement, envoyé toutes les 10 s, et la relance tourne chaque minute. La reprise attendue est donc d'au plus 2 minutes, sous le seuil de 5 minutes.
3. L'enfilage se fait **sur la connexion de la transaction métier** : la connexion psycopg sous-jacente à la session SQLAlchemy de `workspace_transaction`.
4. Les règles de `TECH_CHOICES.md` §9.3 restent en vigueur. En particulier, tout effet externe est protégé par une clé d'idempotence et écrit hors de la clôture de la tâche ; un test dédié provoquera un arrêt exactement entre les deux.
5. **DBOS** est le repli documenté si Procrastinate venait à manquer, à condition d'utiliser la base de l'application comme base système.

## Conséquences

- Aucun composant supplémentaire, et une seule base, comme le prévoit ADR-02.
- La relance des tâches bloquées devient du code du projet, à tester en É1.
- Le délai de reprise d'environ 1 à 2 minutes est acceptable pour la collecte et la rédaction. Pour la publication, la machine à états de l'agrégat Publication (états « inconnu », « à vérifier ») reste la protection contre les doublons, et non la file.

## Options écartées

- DBOS par défaut : la reprise est plus rapide, mais elle dépend de l'identité de l'exécuteur. Le modèle « flux de travail » ferait doublon avec les pipelines du projet. Le projet est jeune et porté par une entreprise.
- Module interne : aucun manque bloquant ne le justifie (TC-06).

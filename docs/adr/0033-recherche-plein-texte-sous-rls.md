# ADR-0033 — Recherche plein texte par une fonction dédiée, sous RLS

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-17 |
| Décideur | Joël |
| Documents touchés | ADR-0021, ADR-0032 §4 ; `TECH_CHOICES.md` §7.4, §8.4 ; `RISKS.md` M-12 ; `otlet.platform.roles` |
| Origine | Rapport P01 (conclu : échec) |

## Contexte

P01 a mesuré la recherche de la veille sur un corpus réel de 100 000 éléments : 13 à 14 s au p95, pour un seuil de 300 ms, quelle que soit la requête (`docs/spikes/P01.md` §4). Le plan montre la cause. La fonction de l'opérateur `@@`, `ts_match_vq`, n'est pas déclarée étanche (*leakproof*). Sous une politique RLS, PostgreSQL n'évalue une condition non étanche qu'après la politique, et ne peut donc pas parcourir l'index GIN avec elle. Chaque recherche lit toute la table. Sans RLS, la même requête utilise l'index.

La RLS est la seconde barrière d'isolation entre espaces (ADR-0021, M-12). Elle doit rester active pour toutes les autres lectures.

## Décision proposée

1. **Un rôle dédié** `otlet_search` (sans connexion, `BYPASSRLS`, sans autre privilège que la lecture des colonnes utiles de `source_items`) est créé par `otlet db provision`, qui s'exécute déjà en superutilisateur.
2. **Une fonction** `search_candidates(q text, window int)`, `SECURITY DEFINER`, détenue par ce rôle, avec un `search_path` fixe, renvoie les identifiants des éléments candidats. Elle lit l'espace courant elle-même (`app.workspace_id`) : l'appelant ne peut pas en choisir un autre. Sans contexte, elle ne renvoie rien. Seul `otlet_app` peut l'appeler.
3. **La requête de la recherche** garde son classement, sa jointure au tri et aux sujets, sous RLS comme aujourd'hui : seule la sélection des candidats passe par la fonction.
4. **Tests** : le test d'isolation vérifie qu'un mot présent dans deux espaces ne renvoie que les éléments du sien, et rien sans contexte. Un test vérifie, avec `EXPLAIN` sous le rôle applicatif, que l'index GIN est utilisé.
5. **Remesure P01b** : même protocole, même corpus, même seuil, après la correction.

Le même modèle existe déjà : `find_identity` (ADR-0028) et `unwatched_items` (ADR-0032 §5) sont des fonctions du propriétaire qui lisent au-delà de la RLS pour un besoin précis.

## Conséquences

- Pour la recherche, l'isolation repose sur le filtre explicite de la fonction, et non plus sur la politique. C'est une seule fonction, courte, couverte par le test d'isolation.
- Un rôle de plus à provisionner. Un hébergement PostgreSQL géré qui refuse `BYPASSRLS` n'est pas visé en É1 (auto-hébergement par Compose).
- Les autres conditions non étanches sous RLS (`pg_trgm` des doublons, `pgvector` plus tard) devront être vérifiées de la même façon.

## Options écartées

- **Déclarer `ts_match_vq` étanche** (`ALTER FUNCTION … LEAKPROOF`, au provisionnement). Vérifié sur une base jetable : l'index redevient utilisable sans changer la requête. Écartée parce qu'elle modifie une fonction du catalogue de PostgreSQL, sur une propriété que ses auteurs n'ont pas garantie, et qu'elle doit être reposée après chaque création de base. Elle reste un repli si la fonction dédiée posait problème.
- **Les leviers de `TECH_CHOICES.md` §8.4** (moins de candidats, partitionnement par mois, moteur dédié) : aucun ne rend l'index utilisable sous RLS.
- **Retirer la RLS de `source_items`** : la seconde barrière disparaîtrait pour toutes les lectures, pas seulement pour la recherche.

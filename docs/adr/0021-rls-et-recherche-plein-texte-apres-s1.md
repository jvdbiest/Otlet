# ADR-0021 — RLS maintenue, recherche plein texte à classement borné

| | |
|---|---|
| Statut | Accepté (2026-10-13) |
| Date | 2026-10-13 |
| Décideur | Joël |
| Documents touchés | `ROADMAP.md` §5.1 (seuil S1 « surcoût RLS ≤ 20 % ») ; `TECH_CHOICES.md` §7.4, §8.4 ; `RISKS.md` M-12 |
| Origine | Rapport S1 (conclu : partiel) |

## Contexte

S1 confirme le profil solo pour la mémoire (1,1 Go pour 3,4 Go), l'isolation (RLS forcée, rôles séparés) et quatre lectures sur cinq (p95 de 13 à 50 ms). Deux seuils échouent (`docs/spikes/S1.md` §4) :

- **Recherche plein texte (L2)** : p95 de 2 054 ms avec RLS et de 1 196 ms sans. Le plan est identique dans les deux cas. Le coût vient de `ts_rank`, calculé sur 93 % des documents de la fenêtre, car le jeu synthétique rend chaque requête non sélective.
- **Surcoût relatif de la RLS** : +72 % sur L2, du fait de la contention sur un calcul pur, et +31 % sur L5. Ces 31 % correspondent à environ 4 ms, l'aller-retour `set_config` ajouté à deux requêtes très courtes.

## Décision

1. **La RLS forcée reste la seconde barrière d'isolation** sur toutes les tables métier. La politique est `workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid`, posée par `otlet.platform.database.workspace_transaction`.
2. **Le seuil « surcoût de la RLS ≤ 20 % » est complété d'un plancher absolu** : le surcoût est acceptable s'il est ≤ 20 % **ou** ≤ 5 ms au p95. Avec cette règle, L1, L3, L4 et L5 passent. L2 reste en échec, pour une autre cause.
3. **La recherche plein texte classe un ensemble borné** : présélection par l'index GIN et la fenêtre de dates, limitée aux 1 000 candidats les plus récents, puis `ts_rank` sur ces seuls candidats. L'adaptateur de recherche de la Veille le met en œuvre en É1. Nouveau levier 0 de `TECH_CHOICES.md` §8.4.
4. **L2 est remesurée sur un corpus réaliste** : le corpus libre de S5, complété d'éléments RSS réels si leur licence le permet. Ce sera au plus tard à la tranche verticale d'É1, avec le même seuil de 300 ms. En cas d'échec, `TECH_CHOICES.md` §8.4, leviers 5 et 6, s'applique.

## Validation de Joël (2026-10-13)

- La RLS reste **obligatoire** sur toutes les tables métier.
- Le seuil de surcoût de la RLS devient : **≤ 20 % ou ≤ 5 ms au p95**.
- Le classement borné à 1 000 candidats est retenu pour É1.
- La remesure de la recherche plein texte sur un corpus réaliste est **obligatoire avant toute conclusion définitive** sur la recherche plein texte. Jusque-là, L2 reste un échec ouvert de S1.

## Conséquences

- C3 de S1 est requalifié par le point 2, sans changer les mesures. Le rapport S1 reste « partiel » : seule cette décision le modifie.
- Le classement borné peut écarter un document très pertinent mais ancien de la fenêtre. Ce risque est accepté pour une veille d'actualité, et à surveiller.
- Un aller-retour supplémentaire par transaction reste le prix de la RLS. Il pourra être supprimé plus tard en posant le contexte dans le même envoi que la première requête.

## Options écartées

- Abandonner la RLS : on perdrait la seconde barrière contre une fuite entre espaces (R-S02), pour un gain de quelques millisecondes.
- Moteur de recherche dédié dès le lot 1 (Meilisearch, OpenSearch) : un composant de plus à installer et à sauvegarder, pour un problème que le corpus réel n'a peut-être pas.
- Relever le seuil de L2 au-dessus de 300 ms : le temps de recherche ressenti compte pour l'utilisateur, et ce serait masquer le problème.

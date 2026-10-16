# ADR-0032 — Sujets, score lexical expliqué, doublons et recherche

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-16 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §13.1, §13.3, §13.4 ; `FUNCTIONAL_ANALYSIS.md` F-VEI-01 à 03, F-VEI-09 ; ADR-0021, ADR-0030 |
| Origine | Tâche U02 du plan d'É1 (`docs/projet/plan-E1.md`) |

## Contexte

U02 range les éléments collectés par sujet, avec un score que l'utilisateur peut lire (F-VEI-02), écarte les reprises d'une même histoire (F-VEI-03) et ouvre la recherche plein texte (F-VEI-09) à classement borné (ADR-0021). En É1, le score est seulement lexical : la proximité sémantique viendra avec un profil d'embeddings.

## Décision

1. **Un sujet** porte un nom unique dans l'espace, une description, des mots-clés (au moins un, sauf quand il prend tous les éléments de ses sources), des exclusions, et en option des langues et des sources. La correspondance ignore la casse, les accents et le pluriel en -s ou -x. Une expression de plusieurs mots doit apparaître dans l'ordre. Un `*` final marque un début de mot. Deux termes qui ne diffèrent que par la casse ou les accents n'en font qu'un. Un sujet compte au plus 50 mots-clés et 50 exclusions, de 100 caractères chacun au plus ; le formulaire les compte en direct. Les sources choisies limitent, par défaut, les éléments où les mots-clés sont cherchés. **Complément du 2026-10-17, à la demande de Joël** : une case « Tous les éléments des sources cochées appartiennent au sujet » fait des sources la définition du sujet. Chaque élément de ces sources y entre, avec 1 point affiché comme « de l'une de ses sources (+1) » ; les mots-clés deviennent facultatifs et ne font qu'ajouter des points ; les exclusions et les langues s'appliquent toujours. La case demande au moins une source (code `no_sources`). Les sujets existants gardent la règle par défaut (migration 0011).
2. **Le score est la somme de ses raisons** : 3 points par terme présent dans le titre, et 1 point par occurrence dans le résumé ou le texte utilisable, jusqu'à 3 occurrences. Un sujet qui prend tous les éléments de ses sources (§1) donne 1 point de plus à chacun d'eux. S'y ajoute la fraîcheur, calculée à la lecture : +2 si l'élément a moins de 24 h, +1 s'il a moins de 72 h. Une exclusion présente n'importe où retire l'élément du sujet. Chaque raison est enregistrée et affichée (« « IA » dans le titre (+3) · récent (+2) »). Le texte d'un élément réservé n'est jamais lu : seuls son titre et son résumé comptent.
3. **Doublons** : un élément reprend une histoire déjà là, venue d'une autre source, s'il a la même adresse normalisée, le même texte (empreinte SHA-256 des mots, si le texte compte au moins 200 lettres), ou un titre presque identique (similarité trigramme ≥ 0,9, au moins 20 caractères, deux jours d'écart au plus). Il est alors rattaché au premier arrivé. Les listes montrent l'histoire une fois, avec « aussi dans N autres sources », et la fiche montre la même histoire ailleurs.
4. **Recherche** : chaque élément est indexé dans la configuration de sa langue (déclarée par le flux ou la page : français, anglais, allemand, néerlandais, espagnol, italien, portugais, sinon sans racinisation). Une recherche interroge toutes les configurations, garde les 1 000 éléments les plus récents qui correspondent, puis classe ceux-là seuls (ADR-0021).
5. **Déclenchement** : la collecte annonce chaque élément terminé (`watch.item_ready`). Un sujet créé ou modifié est appliqué aux éléments des 30 derniers jours (5 000 au plus). Une tâche de maintenance des workers, toutes les cinq minutes, reprend les éléments dont l'annonce s'est perdue (ADR-0030 : une réparation, pas une échéance du domaine). Elle lit tous les espaces par une seule fonction du propriétaire du schéma, `unwatched_items`, comme `claim_due_sources` en U01. Depuis U02b, un sujet retient quand son recalcul a été demandé et à quelle demande ses correspondances répondent : l'interface affiche « Recalcul en cours… » puis l'heure du recalcul. Un bouton « Recalculer » par sujet, et « Actualiser » dans la veille, qui collecte toutes les sources actives et recalcule tous les sujets.

## Conséquences

- Le score reste prévisible et vérifiable à la main, au prix de la finesse : un article qui traite du sujet sans en employer les mots n'y entre pas. La proximité sémantique corrigera cela plus tard.
- Les éléments collectés avant U02 n'ont pas de langue : ils restent indexés sans racinisation.
- Le seuil de 300 ms de la recherche reste à mesurer sur corpus réel (P01).

## Options écartées

- Pondérer par la confiance de la source (F-SRC-07) : il n'y a pas encore de niveau de confiance par source.
- Construire les sujets à partir de la recherche plein texte de PostgreSQL : la racinisation varie selon la langue, et l'explication serait moins lisible pour l'utilisateur.

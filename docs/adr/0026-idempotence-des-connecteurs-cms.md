# ADR-0026 — Idempotence des connecteurs CMS par marqueur natif, « WordPress d'abord » confirmé

| | |
|---|---|
| Statut | Accepté (2026-10-15) |
| Date | 2026-10-15 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §12.4 (ADR-08, machine à états de publication) ; `RISKS.md` R-T18, R-T08, R-S03, DR1 ; `ROADMAP.md` (connecteur WordPress du lot 1a) |
| Origine | Rapport S7 (conclu : partiel) |

## Contexte

S7 a soumis un connecteur prototype à 100 publications par configuration, dont 50 avec une panne au premier envoi (`docs/spikes/S7.md` §4). Sur WordPress 7.1, WordPress 6.9 et Ghost 6.69, il n'y a eu aucun doublon, 100 % des publications ont été rapprochées automatiquement, et aucune n'a été renvoyée à l'aveugle. WordPress n'offre pas de recherche par métadonnée (V1), ni Ghost de champ personnalisé (V2), mais des champs natifs suffisent à porter la clé d'idempotence. Wordfence, dans ses réglages par défaut, bloque les mots de passe d'application : le connecteur est alors refusé, sans explication pour l'utilisateur.

## Décision

1. **Clé d'idempotence portée par un marqueur natif**, sans extension côté CMS :
   - **WordPress** : `slug` `otlet-<clé>` pour les brouillons, plus un commentaire HTML `<!-- otlet:<clé> -->` en tête du contenu. En publication immédiate, le commentaire porte seul le marqueur, et le `slug` reste celui choisi par l'utilisateur.
   - **Ghost** : étiquette interne `#otlet-<clé>`, filtrable et invisible du public.
2. **Rapprochement** : après toute panne, deux recherches du marqueur espacées de 5 s. Un résultat unique fait passer la publication à « publié ». Plusieurs résultats la font passer à « à vérifier », avec le doublon signalé. Deux recherches vides autorisent un renvoi, journalisé avec ces deux recherches. Aucune autre voie de renvoi n'existe. Si la recherche du marqueur échoue, le repli heuristique (titre exact, fenêtre de 10 minutes, un seul candidat) s'applique ; sinon, la publication passe « à vérifier ».
3. **Pas d'extension WordPress compagnon** au lot 1.
4. **Diagnostic de connexion** dans le parcours d'ajout d'un site WordPress : des identifiants valides qui reçoivent `401 rest_not_logged_in` font afficher la cause probable, une extension de sécurité qui bloque les mots de passe d'application. Wordfence est nommé, avec le réglage à changer.
5. **Moindre privilège** :
   - WordPress : le parcours recommande un compte dédié de rôle **Auteur**. Il avertit si le mot de passe d'application appartient à un Administrateur.
   - Ghost : il signale que la clé d'intégration donne accès aux abonnés (R-S03).
6. **« WordPress d'abord » (DR1) est confirmé.**
7. **Avant la mise en service** : un test court de connexion et de publication sur un hébergement mutualisé réel, pendant É1 ou dès qu'un hébergement sera disponible, sans dépense engagée d'ici là (décision de Joël du 2026-10-15).

## Conséquences

- Le contrat « Vérifier l'existence » de la machine à états a une mise en œuvre native sur les deux CMS.
- Si l'utilisateur supprime ou retouche le marqueur dans son CMS, le rapprochement retombe sur l'heuristique, puis sur « à vérifier ». Le comportement reste sûr.
- La survie du commentaire HTML aux retouches dans l'éditeur de blocs, les autres extensions de sécurité et de SEO, et les pannes pendant la recherche restent à vérifier, au plus tard à la tranche verticale d'É1 (`docs/spikes/S7.md` §7).

## Options écartées

- **Extension WordPress compagnon** : aucun gain de rapprochement mesuré, et un composant PHP de plus à maintenir et à faire installer.
- **Métadonnées déclarées** (`register_post_meta`) : elles exigent du code côté serveur, ce que V1 exclut.
- **Rapprochement heuristique seul** : inutile quand le marqueur fonctionne, et ambigu sur des titres identiques.
- **Ghost d'abord** : Ghost n'est pas nettement plus simple. WordPress équipe la grande majorité des sites, et son risque propre, la connexion, est traité par le diagnostic.

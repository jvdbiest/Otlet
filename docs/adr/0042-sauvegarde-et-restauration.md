# ADR-0042 — Sauvegarde et restauration : un dossier choisi, des copies complètes, restaurer sans écraser

| | |
|---|---|
| Statut | Accepté (2026-10-23) ; mise en œuvre par versions (V1 d'abord) |
| Date | 2026-10-23 |
| Décideur | Joël |
| Documents touchés | F08 (backlog d'É1) ; ARCHITECTURE §20.4 (copie au démarrage) ; ADR-0036 et ADR-0040 (fichiers de la médiathèque) ; `deploy/compose.yaml`, `deploy/configure.sh` |
| Origine | Fil de Joël du 2026-10-23 ; document partagé « Otlet · F08 : sauvegarde et restauration » |

## Contexte

Otlet ne copie aujourd'hui que la base, à chaque démarrage, dans `deploy/backups` sur la même machine, et garde les cinq dernières copies. Les fichiers de la médiathèque (`files_data`) ne sont pas sauvegardés. Joël rédige de vrais articles depuis I2, d'où l'avance prise par F08 dans le plan. Il veut une conception orientée produit : une sauvegarde pilotée depuis l'interface, vers une destination qu'il choisit, et à terme une restauration depuis l'interface, y compris sélective. Dans un Otlet à plusieurs utilisateurs, restaurer toute l'instance pour réparer l'erreur d'une personne ramènerait en arrière le travail de tous les autres.

## Décision

1. **Un dossier, quel qu'il soit.** Otlet sauvegarde vers un dossier vu par son serveur, choisi à l'installation (`configure.sh` le demande ; `./backups` par défaut). Ce dossier peut être un disque local, un partage réseau monté sur la machine (un NAS, par exemple), ou un dossier synchronisé par un client installé sur cette machine. Otlet ne distingue pas ces cas. Depuis l'interface, on ne peut choisir qu'un sous-dossier de cette destination : un chemin libre du serveur serait une faille, et le conteneur n'écrit que là où on l'a branché.
2. **Réglages › Sauvegardes, pour l'administrateur.** La sauvegarde couvre toute l'instance. L'écran montre :
   - la destination et son état (accessible ou non, espace libre, essai d'écriture) ;
   - la fréquence et la conservation (par défaut, une copie par jour, 7 quotidiennes et 4 hebdomadaires gardées) ;
   - la dernière sauvegarde ;
   - « Sauvegarder maintenant » ;
   - la liste des sauvegardes, chacune avec son état de vérification et « Télécharger ».
3. **Des copies complètes et cohérentes**, un dossier daté par sauvegarde, contenant :
   - `database.dump` : la base complète, au format personnalisé de PostgreSQL ;
   - `files/` : les fichiers de la médiathèque, rangés par empreinte. Un fichier déjà présent dans une sauvegarde précédente n'est pas recopié, mais lié ;
   - `manifest.json` : versions d'Otlet et du schéma, date, durée, sommes de contrôle, comptes par espace et par bloc ;
   - `secrets` : les secrets de l'instance, dans une sauvegarde chiffrée seulement. Sans eux, les clés d'IA scellées seraient perdues lors d'un changement de machine.
4. **Chiffrement activé par défaut**, avec une phrase de passe définie par l'administrateur et jamais stockée dans la sauvegarde. L'écran avertit qu'une sauvegarde est perdue si la phrase de passe l'est.
5. **Contrôle d'intégrité** après chaque sauvegarde : les sommes de contrôle, puis le rechargement de la copie de la base. Le résultat apparaît dans la liste.
6. **Une sauvegarde automatique avant toute restauration**, ce qui rend la restauration elle-même réversible.
7. **Restaurer, c'est réintroduire, pas écraser.** Une restauration sélective ouvre la sauvegarde dans une base temporaire, la met au schéma actuel, puis compare par bloc avec la base vivante :
   - ce qui manque revient avec son identifiant d'origine ;
   - ce qui est identique est ignoré ;
   - ce qui a changé depuis est restauré à côté, jamais à la place (un brief en copie, un article par l'ajout de ses versions manquantes, un fichier corrompu remplacé quand son empreinte est fausse) ;
   - les dépendances suivent (les images d'un article, les éléments d'un brief).

   Les blocs sont définis dans le code : Médiathèque, Articles et Bibliothèque, Briefs, Veille, Réglages. On les choisit dans une portée, un espace ou toute l'instance. Avant d'agir, Otlet montre un résumé chiffré de ce qui sera réintroduit, ignoré ou restauré en copie.
8. **Des droits séparés.** L'API ne peut ni contourner la RLS ni remplacer la base (M-12), et cela ne change pas. Une restauration est exécutée par un processus distinct, avec le rôle propriétaire, comme l'actuel service `backup`. L'API dépose la demande et affiche l'avancement. La restauration complète passe par un mode maintenance ; la sélective n'en a pas besoin.
9. **Des versions de sauvegarde différentes.** Une sauvegarde plus ancienne est restaurée puis migrée. Une sauvegarde plus récente que le code est refusée, avec un message clair.
10. **Découpage et ordre** :
    - **V1** (F08) : la sauvegarde complète telle que décrite, et la restauration complète par une commande documentée, vérifiée en CI ;
    - **V2** : la restauration complète depuis l'interface, avec l'assistant de Joël (choix, résumé, saisie de « RESTAURER », ré-authentification, lancement) ;
    - **Corbeille de 30 jours** pour les briefs, articles, images et éléments de Veille, placée avant la V3 (Joël) : elle répond à la plupart des suppressions accidentelles sans la complexité d'une restauration sélective ;
    - **V3** : la restauration sélective, réservée d'abord à l'administrateur, puis ouverte au propriétaire d'un espace pour son propre espace.

    Ordre : F08 V1, A1a-1 (ADR-0041), F08 V2, corbeille, V3.

## Conséquences

- La copie au démarrage (service `backup`) reste, comme filet avant une migration. Elle écrira au même format, dans un sous-dossier de la destination.
- La corbeille changera le sens de plusieurs suppressions actuelles (articles archivés, images inutilisées, éléments de Veille archivés) : elles mettront à la corbeille, et la suppression définitive se fera au bout de 30 jours ou en vidant la corbeille. La trace anti-réimport des éléments de Veille sera posée dès leur passage à la corbeille.
- Chaque bloc de la V3 aura ses règles de conflit et de dépendance, et son test en CI (sauvegarder, supprimer, restaurer, comparer).
- Les restaurations seront inscrites au journal d'audit quand F07 existera.

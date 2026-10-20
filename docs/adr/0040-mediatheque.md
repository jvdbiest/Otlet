# ADR-0040 — Médiathèque : une image, deux vues

| | |
|---|---|
| Statut | Accepté (2026-10-20) |
| Date | 2026-10-20 |
| Décideur | Joël |
| Documents touchés | ADR-0036 §6 (images d'un article) ; ADR-0037 §7 (médiathèque renvoyée à plus tard) ; X04 ; migration 0034 |
| Origine | Fil de Joël du 2026-10-20 et document « Otlet · Médiathèque : UX, modèle de données, architecture » |

## Contexte

La Bibliothèque est devenue un module : articles, archives, et bientôt la publication. Les images, importées ou collées dans l'éditeur depuis X03b, n'avaient ni nom, ni provenance, ni liste, ni suppression. Joël veut une vraie médiathèque, base des fonctions à venir (réutilisation, OCR, images générées, publication), plutôt qu'une galerie en lecture seule.

## Décision

1. **Trois onglets dans la Bibliothèque** : Articles (par défaut), Médias, Archives, chacun à sa propre adresse. Les archives ne sont plus un mode de la page : Supprimer définitivement n'existe que dans Archives.
2. **Une image, deux vues.** Une seule table `media`. « Images des articles » montre les images apportées par le travail sur un article (éditeur, et plus tard source ou génération) ou montrées par un article. « Banque d'images » montre celles qu'une personne a gardées pour les réutiliser (`in_bank`). Une image peut être dans les deux ; l'ajouter ou la retirer de la banque ne la copie ni ne la déplace. Le nom « Banque d'images » est provisoire : il n'apparaît qu'à un endroit de l'interface.
3. **Ce qu'on dit d'une image** : nom (celui du fichier à l'import), description (elle préremplira le texte alternatif), auteur ou crédit, licence, adresse d'origine, provenance (`editor`, `library`, `source`, `generated`). Crédit et licence sont facultatifs ; la publication avertira quand ils manquent.
4. **Où une image est utilisée** est lu dans les blocs des versions des articles (index GIN `jsonb_path_ops` sur `document -> 'content'`), pas tenu dans une table : toujours exact, sans reprise des versions existantes. Le module `writing` répond par un port (`media_counts`, `media_usages`) que `media` définit.
5. **Suppression** : une image montrée par une version, même ancienne, d'un article ne se supprime pas. Elle se libère quand l'article est supprimé définitivement. Seule la ligne est supprimée : le fichier, rangé par empreinte, peut appartenir à un autre espace ; une tâche de nettoyage hors RLS l'effacera quand plus aucun espace ne le référence (à faire).
6. **Vignettes** : une WebP de 320 px au plus, faite à l'import, ou à la première demande pour les images plus anciennes. La grille ne charge jamais les originaux.
7. **Recherche** sur le nom, la description, le crédit et la licence ; le texte lu par OCR s'y ajoutera.

## Découpage

- Lot 1 (fait) : onglets, migration 0034, liste par vue avec recherche et filtre d'utilisation, vignettes, fiche d'une image (description, utilisations), ajout et retrait de la banque, import dans la banque, suppression des images inutilisées.
- Lot 2 : sélecteur d'images dans l'éditeur (la banque d'abord), étiquettes.
- Ensuite : OCR, images générées, récupération sous déclaration (ADR-0039), avertissement de crédit à la publication, nettoyage des fichiers orphelins, quota par espace.

## Conséquences

- La sauvegarde F08 doit couvrir `files_data` (vignettes comprises).
- Lister les usages parcourt les blocs des versions de l'espace : suffisant en É1 ; une table d'usages tenue à l'écriture reste possible si le volume l'exige.

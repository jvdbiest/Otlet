# ADR-0036 — Éditeur : enregistrer une version, mise en forme libre, images et exports

| | |
|---|---|
| Statut | Accepté (2026-10-18) |
| Date | 2026-10-18 |
| Décideur | Joël |
| Documents touchés | ADR-0023 (format et éditeur) ; `FUNCTIONAL_ANALYSIS.md` F-RED-04 ; backlog d'É1 (X03, X03b, X03c, U07) |
| Origine | Attentes de Joël sur l'éditeur, avant X03 (2026-10-18) |

## Contexte

U04 produit des versions écrites par le modèle. X03 permet de les retoucher. Joël a précisé ses attentes avant le développement :

- ne pas créer une version à chaque correction de quelques phrases ;
- un ruban de traitement de texte complet, avec police, taille, couleur, surlignage et barré ;
- des images insérées ou collées depuis une autre application, gardées avec l'article ;
- des exports PDF, TXT, DOCX avec images, HTML et Markdown ;
- le même éditeur dans la Bibliothèque (X04).

L'ADR-0023 a fixé le format (« Document plateforme v1 »), le moteur de rendu Python qui fait foi et l'éditeur Tiptap. Le format ne connaissait que le gras, l'italique, les liens et les références de source.

## Décision

1. **Versions.**
   - « Enregistrer » met à jour la version en cours.
   - « Enregistrer comme nouvelle version » crée une version et garde la précédente.
   - Une version écrite par l'IA ne change jamais : elle prouve ce que le modèle a rendu, ce dont le contrôle anti-plagiat (U05), la mention IA et la traçabilité (U06) ont besoin. Le premier « Enregistrer » sur une version IA crée donc la version de la personne, une seule fois ; les suivants mettent à jour celle-ci.
   - Un enregistrement porte la date de la version qu'il modifie : si la version a changé entre-temps (un autre onglet), il est refusé plutôt que d'écraser.
   - Otlet prévient avant de quitter un texte non enregistré.
2. **Origine des blocs**, recalculée par le serveur à chaque enregistrement, jamais reçue du navigateur : un bloc « ia » dont le texte change devient « ia_modifie » ; un bloc nouveau est « humain ». La part d'IA (D8) reste donc juste après retouche.
3. **Mise en forme ajoutée au format**, sans changer `version_schema` (les ajouts sont facultatifs, un document v1 existant reste valide) :
   - `strike` (barré) et `highlight` (surlignage, couleur prise dans une palette) passent partout, sites compris ;
   - `subscript` et `superscript` (indice, exposant, l'un ou l'autre) et l'alignement d'un paragraphe ou d'un titre (`align` : gauche, centré, droite, justifié) passent partout aussi ;
   - le titre de l'article reste en texte simple : les sites et les réseaux l'affichent tel quel ;
   - `text_style` (police, taille, couleur du texte) prend ses valeurs dans des listes fermées. Ce sont des choix de présentation : gardés dans Otlet et dans les exports, ils sont retirés du rendu de publication vers un site ou un réseau, où le thème du site décide et où les réseaux n'acceptent aucune mise en forme.
4. **Validation du document par le serveur** à chaque enregistrement : types de nœuds et de marques connus, valeurs prises dans les listes fermées, liens en `http` ou `https`, références vers des sources de l'article, taille bornée. Aucun HTML reçu n'est gardé.
5. **Presse-papiers.** Copier et Couper passent par le navigateur. Le bouton Coller demande l'autorisation du navigateur ; Ctrl+V marche toujours et passe par le nettoyeur de collage (ADR-0023 §5).
6. **Découpage.** X03 : l'éditeur, le ruban, les deux enregistrements, le collage depuis Word, le test de concordance. X03b : les images (insertion, collage depuis une application, stockage avec l'article, sauvegarde ; type réel vérifié, taille bornée, métadonnées retirées). X03c : les exports PDF, TXT, DOCX avec images, HTML et Markdown.

## Conséquences

- F-RED-04 garde son sens : chaque version voulue est conservée et comparable ; seules les versions de la personne s'enregistrent sur elles-mêmes.
- Chaque nouvelle marque existe en trois endroits (schéma, moteur, extension de l'éditeur), tenus ensemble par le test de concordance, qui couvre aussi ces marques.
- Le moteur a deux rendus : complet (Otlet, exports) et de publication (sans `text_style`).
- X03b ajoute un stockage de fichiers, compris dans la sauvegarde (F08).

## Options écartées

- **Une version à chaque enregistrement** : l'historique se remplit de versions presque identiques.
- **Enregistrer sur la version IA** : l'original du modèle serait perdu.
- **Police, taille et couleur libres** : des valeurs arbitraires dans le document, mal rendues par Word et par les sites ; les listes fermées gardent le rendu prévisible.
- **Publier police, taille et couleur vers les sites** : WordPress et Ghost les remplacent par leur thème, ou les gardent en styles en ligne qui jurent avec lui.

# ADR-0023 — Format « Document plateforme v1 » et éditeur Tiptap

| | |
|---|---|
| Statut | Accepté (2026-10-13) |
| Date | 2026-10-13 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §10.3 (TC-07) ; `ARCHITECTURE.md` §14.2, §14.5 |
| Origine | Rapport S3 (conclu : succès) |

## Contexte

S3 a fait passer un corpus de 30 documents (`docs/spikes/S3.md` §4), rendus par un moteur Python, par WordPress 7.1, WordPress 6.9 et Ghost 6.69. Tous les éléments obligatoires y ont survécu : titres, liens, citations avec leur source, bloc Sources, mention IA. Le même document, rendu par Tiptap avec le schéma du projet, est identique au rendu Python pour 30 documents sur 30. BlockNote, qui impose son propre modèle de blocs, ne l'est pour aucun.

## Décision

1. **Format** : « Document plateforme v1 », un JSON au schéma ProseMirror défini par le projet. Le schéma est publié en JSON Schema, avec des blocs à identifiant et origine, une citation à source obligatoire et une marque de référence de source. L'ébauche est `spikes/s3-document/schema/document-v1.schema.json`, réécrite en É1 dans le module de rédaction.
2. **Rendu** : le moteur Python fait foi. Il insère la mention IA et le bloc Sources. Une citation est rendue en `<blockquote>` suivie de son attribution « — titre lié » hors de la citation. Une référence de source est rendue en `<span class="otlet-source-ref">` ; sa numérotation éventuelle sera décidée en É1, dans le moteur et dans l'éditeur à la fois.
3. **Éditeur** : **Tiptap**, avec ses seuls paquets MIT. Les nœuds et marques du projet sont déclarés en extensions, et leur rendu reproduit celui du moteur Python.
4. **Test de concordance en CI** entre le rendu de l'éditeur et celui du moteur, sur le corpus de S3, avec la normalisation du rapport S3.
5. **Nettoyeur de collage** pour l'éditeur (`transformPastedHTML`) : il reprend les règles du nettoyeur Python, pour les listes Word, les styles de citation, les gras et italiques par style. Le collage Word perd sinon ses listes et ses citations.
6. BlockNote est écarté pour l'éditeur principal (voir ci-dessous).

## Conséquences

- Le format, le moteur et l'éditeur restent indépendants : abandonner Tiptap ne toucherait ni au format ni aux publications.
- Toute évolution d'un nœud se fait en trois endroits (schéma, moteur, extension), tenus ensemble par le test de concordance.
- S7 peut s'appuyer sur ce rendu pour WordPress et Ghost.

## Options écartées

- **BlockNote** : son modèle de blocs ne porte ni la citation typée ni la référence de source. Il faudrait des blocs personnalisés écrits en React, une concordance à reconstruire entièrement, et le paquet serveur exige React. Licence MPL-2.0, plus jeune.
- Faire porter le format par l'éditeur (JSON de Tiptap tel quel) : le format dépendrait d'une bibliothèque JavaScript, ce que TC-07 exclut.

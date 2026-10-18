# ADR-0037 — Bibliothèque : l'article au centre, le brief comme atelier

| | |
|---|---|
| Statut | Accepté (2026-10-18) |
| Date | 2026-10-18 |
| Décideur | Joël |
| Documents touchés | ADR-0036 ; `FUNCTIONAL_ANALYSIS.md` F-BIB-01 à 06 ; backlog d'É1 (X04) |
| Origine | Vision fonctionnelle de X04, validée par Joël (document partagé « Otlet · Bibliothèque (X04) : vision fonctionnelle ») |

## Décision

1. **Une seule source de vérité.** L'article existant (table `articles` et ses versions) est l'objet central. La Bibliothèque est une autre vue sur lui : aucune copie, ni de l'article ni de ses versions.
2. **Le brief est l'atelier, la Bibliothèque le contenu validé.** Un article y entre par « Envoyer en Bibliothèque », qui valide une version ; un brief, un article, plusieurs versions.
3. **Statuts d'É1** : brouillon, validé, archivé. « En relecture » viendra si le besoin apparaît.
4. **Version validée et version courante** sont affichées toutes deux dès qu'elles diffèrent ; seule la version validée part en export et en publication. Elle ne change jamais : l'enregistrer ajoute une version, comme pour une version écrite par l'IA.
5. **Classement** par sujets et étiquettes libres, pas de dossiers ; regroupement de la liste par date (aujourd'hui, cette semaine, ce mois-ci, puis par mois et par année).
6. **Recherche** sur le titre et le texte de la dernière version (texte brut gardé à chaque version) ; pas dans les anciennes versions en É1.
7. **Images** : elles appartiennent à l'espace ; la médiathèque séparée (réutilisation, usages, OCR) viendra plus tard.
8. **Exports** faits à la demande, jamais stockés (X03c).

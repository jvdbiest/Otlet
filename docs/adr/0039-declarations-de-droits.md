# ADR-0039 — Déclaration de droits sur un texte réservé par son éditeur

| | |
|---|---|
| Statut | Accepté (2026-10-20) |
| Date | 2026-10-20 |
| Décideur | Joël |
| Documents touchés | U01 (robots.txt, TDMRep) ; M-08 (saisie manuelle encadrée) ; `deploy/compose.yaml`, `deploy/.env.example` |
| Origine | Fil de Joël du 2026-10-20 : 209 des 214 éléments « résumé seulement » viennent d'une réserve de fouille de l'éditeur (`tdmrep.json`) |

## Contexte

La réserve de fouille de textes et de données (directive (UE) 2019/790, article 4) ne rend pas un texte inaccessible : elle soumet sa fouille à l'autorisation de l'éditeur. Otlet la respecte à chaque collecte. Une personne qui dispose de cette autorisation (accord de l'éditeur, licence, ses propres contenus) doit pouvoir utiliser le texte, sans qu'Otlet devienne un moyen de contourner les réserves.

## Décision

1. **Une déclaration par élément**, toujours faite par une personne sur la fiche de l'élément, jamais groupée ni automatique.
2. **Une base choisie** : accord de l'éditeur, licence, mes propres contenus, autre (précisée). Une référence facultative (numéro de licence, lien). L'engagement est accepté par une case : « Je certifie disposer des droits ou autorisations nécessaires pour importer et exploiter ce contenu dans Otlet. J'assume l'entière responsabilité de son utilisation. » L'interface rappelle que la responsabilité incombe à la personne, non à Otlet.
3. **Une trace conservée** (`rights_declarations`, sous RLS) : qui, quand, quel élément, quelle base, la référence, les mots exacts de l'engagement, la raison d'origine de la réserve.
4. **Aucun contournement technique** : la page est lue par le même extracteur, robots.txt respecté, sans connexion ni paywall. Seule la réserve de fouille est levée, sous la déclaration.
5. **Un texte marqué** : statut « manuel », raison `declared_rights`, « Importé sous votre responsabilité » dans la Veille, la fiche et les briefs.
6. **Une déclaration révocable** : la retirer efface le texte lu et rend la réserve ; la déclaration reste dans l'historique, marquée retirée.
7. **Un réglage d'instance** `OTLET_RIGHTS_DECLARATIONS`, activé par défaut en auto-hébergement ; l'administrateur d'une instance hébergée décide.

## Conséquences

- À faire valider par un juriste avant d'ouvrir une plateforme hébergée à d'autres personnes : la déclaration protège surtout en auto-hébergement.
- Plus tard, si le besoin vient : une déclaration par source, pour les accords permanents avec un éditeur.

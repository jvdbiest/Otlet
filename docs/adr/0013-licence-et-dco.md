# ADR-0013 — Licence AGPL-3.0-or-later et contributions sous DCO

| | |
|---|---|
| Statut | Accepté |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | `FUNCTIONAL_ANALYSIS.md` D2 ; `RISKS.md` DR8 ; `ROADMAP.md` DRM7 |
| Origine | Décisions D2, DR8, DRM7 |

## Contexte

D2 retient l'AGPL-3.0 ; DR8 et DRM7 imposent un dépôt public et le DCO dès le premier commit. Reste à choisir entre « version 3 seulement » et « version 3 ou ultérieure ».

## Décision

1. Licence du projet : **`AGPL-3.0-or-later`**. Texte intégral dans `LICENSE`.
2. Chaque fichier source porte l'en-tête `SPDX-License-Identifier: AGPL-3.0-or-later`.
3. Chaque commit porte une ligne `Signed-off-by` attestant le DCO 1.1 (`DCO`). La CI refuse un commit non signé, y compris ceux du mainteneur.
4. Aucun accord de cession de droits (CLA).

## Conséquences

- Sans CLA, aucun changement de licence n'est possible sans l'accord de tous les contributeurs ; « ou ultérieure » est la seule porte ouverte vers une future version de l'AGPL.
- Les dépendances doivent être compatibles AGPL-3.0 (filtre de `TECH_CHOICES.md` §1.1), vérifiées en CI (tâche B07).
- La question de la portée de l'AGPL sur les modules hors processus (Q-J5) reste ouverte jusqu'à la revue juridique.

## Options écartées

- `AGPL-3.0-only` : interdit toute évolution de licence sans accord unanime.
- CLA : frein pour les contributeurs, et inutile tant qu'aucun double licenciement n'est envisagé.

## Précision apportée en B06 (2026-10-12)

Les commits du robot de mises à jour (Dependabot, adresse d'auteur `49699333+dependabot[bot]@users.noreply.github.com`) sont dispensés de `Signed-off-by` : un changement de numéro de version dans un verrou n'est pas une contribution que le DCO atteste, et le robot ne sait pas signer. La dispense porte sur cette adresse exacte, réservée par GitHub ; un auteur qui se fait seulement appeler « dependabot » reste soumis à la règle. Tout autre commit d'une demande du robot, par exemple une correction du mainteneur, doit être signé.

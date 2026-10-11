# ADR-0012 — Les décisions sont consignées dans le dépôt

| | |
|---|---|
| Statut | Accepté |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | Tous ceux de `docs/design/` |
| Origine | ROADMAP PP9, RISKS R-O15 |

## Contexte

La phase de conception est close (point P0). Cinq documents et une revue critique sont validés. Les preuves de concept d'É0 ont le droit de les contredire (PP6). Réécrire ces documents à chaque découverte coûterait cher et effacerait l'historique de ce qui avait été décidé.

## Décision

1. Les documents de `docs/design/` sont figés à leur version 1.0. Ils ne sont plus réécrits.
2. Toute décision qui modifie, précise ou annule une de leurs affirmations fait l'objet d'un ADR dans `docs/adr/`, qui cite la section touchée.
3. Un ADR est **proposé** par le mainteneur et **accepté** par Joël. Un ADR accepté n'est pas modifié ; il est remplacé par un nouvel ADR qui le cite.
4. La numérotation continue celle d'`ARCHITECTURE.md` (ADR-01 à ADR-11) : les ADR du dépôt commencent à 0012.

## Conséquences

- Lire la conception à jour = lire le document de `docs/design/` puis les ADR qui le citent (index : `docs/adr/README.md`).
- Si les ADR qui touchent un même document dépassent une dizaine, une version 2.0 consolidée du document est envisagée à un point de décision.

## Options écartées

- Réécrire les documents en place : historique illisible, et la frontière entre hypothèse et mesure disparaît.
- Wiki de la forge : hors du dépôt, non versionné avec le code.

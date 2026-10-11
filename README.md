# Otlet

> **Pré-alpha. Non destiné à la production.** Aucune version n'est publiée ; le code présent sert aux preuves de concept de l'étape É0.

Plateforme Web libre et auto-hébergeable de **veille et de rédaction sourcée assistée par IA** : collecte depuis des sources de confiance, aide à la rédaction avec plusieurs fournisseurs d'IA au choix, sources originales toujours traçables, publication vers votre site et vos CMS. Chaque automatisation est désactivée par défaut et s'active individuellement ; rien n'est publié sans que vous l'ayez explicitement permis.

## État du projet

| | |
|---|---|
| Phase | Étape **É0** : preuves de concept S1 à S7 et socle ([plan](docs/projet/plan-E0.md)) |
| Prochain point de décision | **P1** : recalibrage du plan avec la vélocité mesurée |
| Capacité | Un développeur, 15 à 20 heures par semaine, sans financement ([roadmap](docs/design/ROADMAP.md)) |

## Documentation

La conception est terminée et validée ; elle est figée dans [`docs/design/`](docs/design/) et n'évolue plus que par décisions courtes ([`docs/adr/`](docs/adr/)).

| Document | Contenu |
|---|---|
| [FUNCTIONAL_ANALYSIS.md](docs/design/FUNCTIONAL_ANALYSIS.md) | Objectifs, utilisateurs, fonctions, lots |
| [ARCHITECTURE.md](docs/design/ARCHITECTURE.md) | Monolithe modulaire, modules, sûreté de l'automatisation, ADR-01 à ADR-11 |
| [TECH_CHOICES.md](docs/design/TECH_CHOICES.md) | Python, FastAPI, PostgreSQL, React, et pourquoi |
| [RISKS.md](docs/design/RISKS.md) | Registre des risques techniques, juridiques et opérationnels |
| [ROADMAP.md](docs/design/ROADMAP.md) | Jalons, estimations, critères d'arrêt |
| [Rapports de preuves](docs/spikes/) | Résultats des preuves de concept S1 à S7 |

## Contribuer

Les contributions sont signées selon le [Developer Certificate of Origin](DCO) (`git commit -s`). Voir [CONTRIBUTING.md](CONTRIBUTING.md). Failles de sécurité : [SECURITY.md](SECURITY.md).

## Licence

[GNU Affero General Public License v3.0 ou ultérieure](LICENSE) (`AGPL-3.0-or-later`).

---

## In English

**Pre-alpha, not for production.** A free, self-hostable web platform for **source-grounded news monitoring and AI-assisted writing**: collect from trusted sources, draft with the AI provider of your choice, keep every original source traceable, publish to your own site and CMS. Every automation is off by default and nothing is published without your explicit consent. Design documents are in French; the user interface will ship in French first, then English. Contributions are welcome under the DCO (`git commit -s`). Licence: AGPL-3.0-or-later.

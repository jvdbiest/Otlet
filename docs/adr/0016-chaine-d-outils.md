# ADR-0016 — Chaîne d'outils

| | |
|---|---|
| Statut | Proposé ; accepté à la fin de la tâche B02 |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §4, §6, §21 |
| Origine | Plan d'exécution d'É0, B02 |

## Contexte

TECH_CHOICES fixe les familles d'outils mais laisse quelques choix ouverts (`mypy` ou `pyright`, version exacte de Python).

## Décision

| Domaine | Outil |
|---|---|
| Python | **3.13** (prise en charge jusqu'en 2029) ; CI aussi sur la version la plus récente, en information |
| Paquets et verrous | `uv`, `uv.lock` avec empreintes |
| Lint et format | `ruff` (règles de sécurité `S` activées) |
| Typage | `mypy --strict`, greffon Pydantic |
| Tests | `pytest`, `hypothesis` ; PostgreSQL réel en conteneur |
| Architecture | `import-linter` (ADR-0017) |
| Base | PostgreSQL 18 + `pgvector` |
| Interface | Node LTS (construction seulement), `npm`, Vite, TypeScript strict, ESLint |
| Dépendances | `pip-audit`, `npm audit`, robot de mises à jour avec quarantaine de 7 jours |

## Conséquences

- Un seul gestionnaire Python (`uv`) pour le développement, la CI et l'image.
- À réviser si B02 révèle une incompatibilité (par exemple une dépendance sans roue pour Python 3.13).

## Options écartées

- `pyright` : plus rapide, mais `mypy` a le greffon Pydantic et reste la référence de SQLAlchemy 2.
- `poetry`, `pip-tools` : plus lents, verrous moins complets que `uv`.
- `pnpm` : gain marginal pour une seule application ; `npm` évite un outil de plus.

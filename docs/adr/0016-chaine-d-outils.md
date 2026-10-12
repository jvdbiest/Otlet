# ADR-0016 — Chaîne d'outils

| | |
|---|---|
| Statut | Accepté (fin de la tâche B02) |
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

## Écarts constatés pendant B02

- Aucune incompatibilité avec Python 3.13. Versions verrouillées dans `backend/uv.lock` : `ruff` 0.17.0, `mypy` 2.4.0, `pytest` 9.1.1.
- Back-end de construction : `hatchling`, nécessaire pour que `uv` installe le paquet `otlet` (disposition `src/`) et que les tests puissent l'importer.
- `hypothesis` et le greffon Pydantic de `mypy` ne sont pas encore installés : ils arrivent avec leurs premiers usages (Pydantic avec FastAPI en S6.4).
- Crochets de pré-commit reportés en B04, avec l'intégration continue ; mis en place en B04 (`.pre-commit-config.yaml`, `pre-commit` verrouillé dans le groupe `dev`).

## Écarts constatés pendant B08

- Node 24 LTS (`frontend/.nvmrc`), utilisé seulement pour construire l'interface ; Node n'est pas installé sur le poste du mainteneur, les commandes `npm` tournent dans l'image officielle `node:24-slim`.
- TypeScript 6.0 et non 7.0 : `typescript-eslint` 8.71 ne prend en charge que TypeScript < 6.1. Passage à 7 quand `typescript-eslint` le permettra.
- ESLint en configuration `strictTypeChecked` de `typescript-eslint`, zéro avertissement toléré.

## Mise en œuvre en B06

- Verrous à empreintes : `backend/uv.lock` (empreintes SHA-256, installé par `uv sync --locked` en CI et dans l'image), `frontend/package-lock.json` (champ `integrity`, installé par `npm ci`).
- Robot de mises à jour : Dependabot (`.github/dependabot.yml`), hebdomadaire, groupé par écosystème (Python, interface, actions GitHub, images de base et de la pile), **quarantaine de 7 jours** (`cooldown`) après chaque publication.
- Audit bloquant en CI (job « Audit des dépendances ») : `pip-audit` 2.10.1 sur l'export du verrou, empreintes exigées, et `npm audit --audit-level=moderate`. Un avis de vulnérabilité connu fait échouer la CI.

## Mise en œuvre en B07

- `tools/check_licenses.py` (bibliothèque standard) applique le filtre de `TECH_CHOICES.md` §1.1 à ce qui est livré : l'environnement Python synchronisé sans le groupe `dev`, et les paquets npm qui ne sont pas réservés au développement. Une licence absente ou non identifiée fait échouer la vérification ; une exception exige un ADR.
- Job de CI bloquant « Licences des dépendances ». Un paquet sous SSPL fait échouer la vérification (test `test_shipped_sspl_package_fails`).

## Options écartées

- `pyright` : plus rapide, mais `mypy` a le greffon Pydantic et reste la référence de SQLAlchemy 2.
- `poetry`, `pip-tools` : plus lents, verrous moins complets que `uv`.
- `pnpm` : gain marginal pour une seule application ; `npm` évite un outil de plus.

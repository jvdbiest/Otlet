# ADR-0017 — Contrats d'imports

| | |
|---|---|
| Statut | Accepté (fin de la tâche B03) |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §7.3 (MD1 à MD6) ; `TECH_CHOICES.md` §5.4 ; `RISKS.md` §4.15 (R-T14) |
| Origine | Plan d'exécution d'É0, B03 |

## Contexte

R-T14 (érosion des frontières sous la pression des délais) est la menace principale d'un monolithe modulaire tenu par une seule personne. RISKS exige des contrats `import-linter` bloquants dès le premier code, sans exceptions accumulées.

## Décision

Contrats vérifiés en CI, bloquants, **zéro exception** :

1. **Indépendance du domaine** : `otlet.*.domain` n'importe ni `fastapi`, `starlette`, `sqlalchemy`, `alembic`, `psycopg`, `procrastinate`, `httpx`, `openai`, `anthropic`.
2. **Couches** dans chaque module : `adapters` → `application` → `domain`.
3. **Points d'entrée au sommet** : aucun module n'importe `otlet.entrypoints`.
4. **MD4** : seul `otlet.ai_gateway` importe `openai` et `anthropic`.
5. **MD3** : seul `otlet.publishing` importe les connecteurs de publication.
6. **MD1** : un module n'importe d'un autre module que son interface publique (`<module>.application.api`). Si `import-linter` ne sait pas l'exprimer, un test d'architecture `pytest` le vérifie.

Noms des modules : `identity`, `workspaces`, `audit`, `notifications`, `registry`, `admin`, `sources`, `monitoring`, `drafting`, `guardrails`, `media`, `traceability`, `review`, `publishing`, `site`, `ai_gateway`, `automation`, `jobs`.

## Conséquences

- Une exception demandée équivaut à une modification d'architecture : elle passe par un ADR.
- Les contrats sont posés en B03 alors que les modules n'existent pas encore ; ils s'appliquent dès leur création.

## Mise en œuvre en B03

Configuration : section `[tool.importlinter]` de `backend/pyproject.toml`. Vérification : `uv run lint-imports` ; chaque contrat est défendu par un test qui introduit une violation (`backend/tests/architecture/test_import_contracts.py`).

| Règle | Contrat (id) | Statut |
|---|---|---|
| 1. Indépendance du domaine | `domain-independence` (`otlet.**.domain`) | Actif |
| 2. Couches | `module-layers` | Actif ; couches facultatives tant que le module n'existe pas |
| 3. Points d'entrée au sommet | `entrypoints-on-top` | Actif ; crée le paquet vide `otlet.entrypoints` |
| 4. MD4 | `ai-sdks-gateway-only` | Actif sous forme d'interdiction totale de `openai` et `anthropic` ; devient « seul `otlet.ai_gateway` » (contrat `protected`) à la création de la passerelle en S4 |
| 5. MD3 | — | Reporté à la création de `publishing` : `import-linter` refuse un contrat sur un module absent |
| 6. MD1 | — | Reporté à la création du deuxième module, pour la même raison |

## Options écartées

- Revue humaine seule : sans second relecteur, elle n'existe pas.
- Paquets Python séparés par module : coût de construction et de version disproportionné au lot 1 (RISKS §4.15 l'autorise mais ne l'exige pas).

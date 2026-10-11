# ADR-0015 — Forge et intégration continue

| | |
|---|---|
| Statut | Accepté (choix de Joël au point P0) ; mis en œuvre en B04 |
| Date | 2026-10-11 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §21 (forge laissée à la roadmap) ; `ROADMAP.md` §8.4 |
| Origine | Plan d'exécution d'É0 §1, P0-b |

## Contexte

TECH_CHOICES laisse le choix de la forge à la gouvernance du projet. Il faut une CI gratuite capable de lancer PostgreSQL en conteneur, un signalement privé de vulnérabilités et un robot de mises à jour de dépendances.

## Décision

1. Forge : **GitHub** ; intégration continue : **GitHub Actions**.
2. Branche `main` protégée : fusion uniquement par demande de fusion avec CI verte, y compris pour le mainteneur.
3. Signalement privé de vulnérabilités activé.
4. Les fichiers propres à la forge restent confinés à `.github/` ; la CI appelle des commandes du dépôt (scripts, `uv run …`) plutôt que des actions tierces, pour garder la sortie peu coûteuse.

## Conséquences

- Plate-forme propriétaire : un miroir sur Codeberg est possible à tout moment ; le passage à Forgejo Actions coûte une réécriture des fichiers YAML.
- Les comptes passeront au nom d'une organisation avant la préversion fermée (`ROADMAP.md` §8.4).

## Mise en œuvre (B04)

- Workflow `.github/workflows/ci.yml`, lancé sur chaque demande de fusion et sur `main`. Toutes les vérifications sont bloquantes :
  - **Signature DCO** : `tools/check_dco.py` exige, pour chaque commit de la demande hors fusions, un `Signed-off-by` portant l'adresse de l'auteur (ADR-0013) ;
  - **Back-end** sous Linux et sous Windows (le mainteneur développe sous Windows ; un défaut d'encodage propre à Windows a déjà été corrigé en B03), Python 3.13 : `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports`, `pytest`.
- Un troisième job sur la version la plus récente de Python (3.15) est informatif (ADR-0016) : son échec ne bloque pas.
- Seules des actions de GitHub sont utilisées (`actions/checkout`, `actions/cache`) ; `uv` est installé à une version fixe par `pipx`, et son cache est indexé sur `backend/uv.lock`.
- Les mêmes outils tournent en local par les crochets de `.pre-commit-config.yaml` (report de B02), dont un crochet `commit-msg` qui refuse un message sans `Signed-off-by`.
- Le robot de mises à jour, l'épinglage des actions par empreinte et les audits de dépendances relèvent de B06.
- Vérifications à exiger dans la protection de `main` (B01) : « Signature DCO » et les deux jobs « Back-end … Python 3.13 ».

## Options écartées

- Codeberg + Forgejo Actions : forge libre, mais capacité de CI plus limitée et moins de contributeurs potentiels. Choix inverse possible si Joël le préfère ; seul le point 1 change.
- GitLab : CI gratuite plus restreinte pour un dépôt public.

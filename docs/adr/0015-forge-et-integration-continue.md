# ADR-0015 — Forge et intégration continue

| | |
|---|---|
| Statut | Accepté (choix de Joël au point P0) |
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

## Options écartées

- Codeberg + Forgejo Actions : forge libre, mais capacité de CI plus limitée et moins de contributeurs potentiels. Choix inverse possible si Joël le préfère ; seul le point 1 change.
- GitLab : CI gratuite plus restreinte pour un dépôt public.

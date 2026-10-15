# ADR-0025 — La qualité du produit prime sur le profil matériel

| | |
|---|---|
| Statut | Accepté (2026-10-15) |
| Date | 2026-10-15 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §3.2 (budget mémoire solo) ; `ROADMAP.md` §5.1 (seuils de mémoire des preuves) |
| Origine | Décision de Joël après S5 et S5b (ADR-0024) |

## Contexte

S5 et S5b ont montré que le meilleur modèle de similarité mesuré, potion, dépasse le budget estimé avant toute mesure pour un modèle (500 Mo), sans que la pile complète dépasse le profil solo. Ce budget par composant était une hypothèse de conception, pas une contrainte démontrée.

## Décision

1. **La qualité fonctionnelle du produit prime** sur les contraintes matérielles du profil solo : performances, précision et fonctionnalités.
2. Le profil solo à 4 Go reste une **cible**. Il ne justifie pas de dégrader significativement le produit.
3. Si un composant apporte une **valeur démontrée** et que son coût principal est la mémoire ou le CPU, la qualité est conservée. Une machine plus puissante pourra être utilisée si nécessaire.
4. Le **critère déterminant** est la capacité de la pile complète à fonctionner correctement sur une configuration réaliste. Le respect d'un budget mémoire estimatif fixé avant les mesures ne l'est plus.
5. Des **profils de déploiement** pourront être définis plus tard (léger, recommandé, performant), sans sacrifier la qualité du profil recommandé.

## Conséquences

- Les budgets par composant de `TECH_CHOICES.md` §3.2 deviennent indicatifs. Le total de la pile, mesuré, fait foi.
- Une preuve dont un seuil matériel échoue alors que la qualité tient est soumise à Joël avec cette règle. Le protocole de l'ADR-0018 est inchangé : les seuils sont fixés avant la mesure et le verdict reste celui qui est mesuré.
- Pour S5 et S5b : potion est retenu, chargé en int8 par défaut (ADR-0024).

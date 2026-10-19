# Banc de rédaction : qwen3:14b, redaction-11, charte oui

| Brief | Essais | words | length_ratio | unsupported_per_100 | copy_share | copied_passages | judgements_per_100 | items_kept | names_kept | seconds | Refus de forme |
|---|---|---|---|---|---|---|---|---|---|---|---|
| disney-top10 | 2 | 465.00 | 0.77 | 0.00 | 0.00 | 0.00 | 0.76 | 0.90 | 1.00 | 80.00 | 0 |
| f1-synthesis | 2 | 347.50 | 0.58 | 0.00 | 0.46 | 6.50 | 0.43 | - | 0.50 | 93.00 | 2 |
| f1-panorama | 2 | 404.50 | 0.68 | 0.00 | 0.10 | 2.50 | 0.25 | - | 1.00 | 79.00 | 0 |
| settlers-synthesis | 2 | 590.00 | 0.98 | 0.95 | 0.00 | 0.00 | 0.00 | - | - | 78.00 | 0 |
| nvidia-thin | 2 | 499.00 | 1.67 | 0.45 | 0.01 | 0.00 | 0.00 | - | - | 62.00 | 0 |
| lula-short | 2 | 279.00 | 0.93 | 0.20 | 0.15 | 3.00 | 0.00 | - | 1.00 | 43.50 | 0 |

Absents des sources (à relire) : 15, 2024, Affaires, Europe, OEA, Palestiniens, Premier, S1, S2, Santé, Union, État, États-Unis
## Lecture (2026-10-19, premier passage)

- **disney-top10** : aucune invention relevée (contre « Stephen King » dans 5 versions sur 19 avant), « Disney+ propose » a disparu et Les Numériques est nommé dans les deux essais. Un essai a perdu 2 films sur 10 : la longueur est ramenée à « Moyen » par la matière, et le modèle a comprimé la liste.
- **f1-synthesis** : sur trois sources sans sujet commun, le modèle n'a cité que la première et en a recopié 46 % (un passage de 44 mots). Le produit renverrait cette réponse pour les sources oubliées ; le banc mesure la première réponse. Le Panorama, sur les mêmes sources, recopie 10 % et cite tout.
- **settlers-synthesis** : les « absents des sources » sont des traductions (Palestiniens, État, Affaires étrangères) : sources anglaises, article français. Fuite des identifiants S1, S2 dans un essai.
- **nvidia-thin** : 40 mots de matière, 312 et 686 mots écrits malgré la consigne « court » : sur une matière trop mince, le modèle invente le reste (Europe, États-Unis, 2024).
- **lula-short** : 23 % de recopie dans un essai sur une source de 192 mots.

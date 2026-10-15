# ADR-0024 — Modèle d'embeddings statique et seuils du garde-fou après S5

| | |
|---|---|
| Statut | Accepté (2026-10-15) |
| Date | 2026-10-15 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §3.2 (budget mémoire solo), §13 (TC-10) ; `RISKS.md` DR4, R-T10 |
| Origine | Rapport S5 (conclu : échec, de peu) |

## Contexte

S5 a mesuré trois modèles multilingues sur 200 paires FR / EN (`docs/spikes/S5.md` §4). Aucun ne tient les quatre seuils. `potion-multilingual-128M`, un modèle statique sous licence MIT, tient C2 (36 s pour le volume quotidien, contre 30 min permises), C3 (90 %), C4 (0 %) et C5 (seuil inter-langues : 92 % des traductions, 0 % de faux positifs). Il échoue sur C1 : 1 344 Mio pour 500 Mo. Les deux modèles à attention, MiniLM-L12 et e5-small, échouent sur C1, C2 et C3. Le seuil lexical de 0,5 sur les 5-grammes ne détecte aucune reprise quasi littérale.

## Décision

1. **Modèle par défaut** : `minishlab/potion-multilingual-128M` par `fastembed`, dans le worker, **sous condition** du point 2. Les modèles à attention sont écartés du profil solo.
2. **Complément de preuve court sur C1** (4 h au plus) : charger potion en float16 ou avec un vocabulaire réduit au français et à l'anglais, puis remesurer C1 avec le même seuil de 500 Mo et C3 / C4 avec la même procédure de calibration. Le protocole est commité avant la mesure (ADR-0018).
3. **Si le complément échoue**, deux voies sont soumises à Joël :
   - garder potion à environ 1,3 Go et relever la ligne du worker dans le budget solo. Le profil mesuré en S1 (1,1 Go) plus potion resterait sous 3,4 Go ; c'est une déduction, pas une mesure de la pile entière ;
   - ou ne garder la similarité inter-langues qu'en alerte (colonne « Si échec » de la roadmap).
4. **DR4 confirmé sur la qualité** : pour les paires de langues différentes, le score sémantique décide seul, avec un seuil propre (0,549 avec potion).
5. **Volet lexical** : le recouvrement de 5-grammes à 0,5 est abandonné comme signal de reprise quasi littérale. La plus longue séquence commune normalisée sépare nettement reprises, paraphrases et indépendants (1,00 / 0,38 / 0,14). Elle le remplace, avec un seuil à fixer avant mesure, au plus tard à la tranche verticale d'É1.
6. **Seuils sémantiques remesurés sur un corpus réel** à la tranche verticale d'É1, avec le même protocole, avant toute mise en service du garde-fou. Les seuils de S5 (0,640 en même langue, 0,549 en langues différentes) servent de valeurs initiales.

## Validation de Joël (2026-10-15)

- ADR-0024 accepté.
- Le critère pertinent est désormais **la mémoire de la pile complète**, et non la mémoire isolée du modèle. Le seuil de 500 Mo était une hypothèse de conception, non une contrainte technique démontrée.
- Le complément de preuve sur la mémoire de potion est mené s'il reste dans les 4 h prévues.
- S'il échoue et que la pile complète reste sous la limite du profil solo (3,4 Go), **potion reste le modèle par défaut** : la qualité des résultats prime. Le point 3 se lit ainsi : la première voie est retenue, sous cette condition.

## Conséquences

- Le garde-fou reste local et indépendant de tout fournisseur (P9).
- Un modèle statique ne lit pas le contexte d'une phrase. Il voit les reprises et les traductions du corpus, mais pourrait manquer une paraphrase très libre. Ce risque est à suivre sur le corpus réel.
- Le seuil retenu par la règle « 90 % des positifs » ne laisse aucune marge de rappel, alors que l'écart avec les indépendants est large. Le corpus réel dira où le placer.

## Options écartées

- **MiniLM-L12 et e5-small** : trop lourds en mémoire, près de 3 h pour le volume quotidien sur le processeur du NAS, rappel sous 90 %.
- **Modèle d'un fournisseur par l'adaptateur générique** : possible en option, jamais par défaut, puisque le garde-fou ne doit pas dépendre d'un fournisseur.

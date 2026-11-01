# TEXTE1 — Le texte collecté correspond-il à l'article ?

Diagnostic du 2026-11-01, sans modèle et sans écriture dans la Veille. Ce n'est pas une preuve au sens d'ADR-0018 : aucun seuil n'était fixé d'avance, et aucune correction n'est mesurée ici.

Origine : l'essai de TRI1 (`docs/spikes/TRI1.md` §8). Les textes de « Hiver 2026-2027 » et du vortex polaire parlaient d'autre chose que leur titre.

## Résultat

**Le problème vient du parsing, pas de la collecte ni du stockage.** `readability` retient un mauvais bloc de la page, ou une partie seulement de l'article.

- **Collecte hors de cause.** 134 pages relues (120 tirées au hasard et 14 choisies), toutes répondues : les 14 pages choisies contiennent bien l'article, 1 à 5 Ko de paragraphes, et 13 contiennent le début du résumé.
- **Stockage hors de cause.** La relecture redonne le texte stocké à l'identique dans 107 cas sur 120 et 13 sur 14. Les écarts sont surtout faibles, ou viennent d'une page qui a changé (commentaires, direct).

**Combien d'articles.** Sur 120 textes tirés au hasard parmi les 30 derniers jours :

| Part de l'article conservée | Articles |
|---|---|
| Moins de 25 % | 4 |
| 25 à 50 % | 9 |
| 50 à 80 % | 31 |
| 80 % ou plus | 76 |

Soit **11 % sous la moitié de l'article** (de 6 à 18 % avec l'incertitude de l'échantillon), environ 530 des 4 872 textes de l'espace de Joël (de 290 à 880). La mesure compare des longueurs : elle ne dit pas si le texte conservé est sur le sujet. Le repère de l'article est lui-même approché (`articleBody`, sinon les longs paragraphes de `<article>`, sinon ceux de la page).

**Familles repérées.**

| Site | Ce qui est retenu | Compté |
|---|---|---|
| Les Numériques | « Publicité, votre contenu continue ci-dessous » seul | 56 sur 434 (exact) |
| RTBF Info | Le bloc d'inscription à la newsletter | 11 sur 220 (exact) |
| Audiofanzine | Les commentaires du forum | au moins 17 sur 136 |
| Futura Sciences | L'accroche d'un autre article, recommandé | au plus 33 sur 166 (textes de moins de 1 000 signes) ; 5 vérifiés |
| Auto-Moto, Motor Tribu | Un fragment ; `articleBody` est bien plus long | 3 sur 11 et 1 sur 5 dans l'échantillon |
| La DH, La Libre, L'Avenir | Une partie de l'article seulement | 5 sur 51 et 2 sur 10 sous la moitié dans l'échantillon ; L'Avenir : le « froid », 660 signes sur environ 3 100 |

Ces familles se recouvrent en partie et ne s'additionnent pas.

## Conséquences

- **Recherche** : le corps du texte alimente la recherche par mots. Un article mal extrait n'est pas trouvé par ses mots, ou l'est pour ceux d'un autre article. Le sens n'est pas touché : il encode le titre et le résumé.
- **Tri** : pas d'effet direct, il lit le titre et le résumé.
- **Rédaction** : c'est là que l'effet est le plus direct. Le modèle rédige à partir de ce texte. Sur le froid, il a parlé du mouron parce que seule cette partie de l'article de La DH était conservée.

## Limites

- 120 articles, soit 5 à 7 par site en général, sauf La DH : les proportions par site sont indicatives.
- Pages relues le 2026-11-01 : l'état d'une page au moment de la collecte n'est pas connu.

Rejeu : `spikes/texte1/` (`text_check.py`, `text_probe.py`, `text_sample.py`, à lancer dans le conteneur worker).

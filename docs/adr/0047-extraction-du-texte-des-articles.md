# ADR-0047 — Extraction du texte des articles : trafilatura, avec repli sur la page

| | |
|---|---|
| Statut | Accepté (2026-11-01) |
| Date | 2026-11-01 |
| Décideur | Joël |
| Documents touchés | `backend/src/otlet/collection/adapters/parsing.py` ; `docs/spikes/TEXTE1.md`, `TEXTE1b.md`, `TEXTE1c.md` |
| Origine | Essai de TRI1 : le texte stocké de plusieurs articles ne correspondait pas à leur titre |

## Contexte

Le texte d'un article venait de `readability-lxml`. Il retenait parfois un mauvais bloc de la page (la publicité de Les Numériques, la newsletter de RTBF, les commentaires d'Audiofanzine, l'accroche d'un autre article chez Futura) ou une partie seulement de l'article (La DH, La Libre). La collecte et le stockage sont hors de cause (TEXTE1).

Sur 100 pages de référence écrites à la main, 5 % des textes gardaient moins de la moitié de l'article, et 17 % moins de 70 %. La recherche par mots et surtout la rédaction lisent ce texte.

## Options

1. **Garder `readability-lxml`.** Aucun changement, mais le défaut reste.
2. **Replier sur l'article marqué par la page (E1).** Gain faible : 92,8 % de l'article en médiane contre 91,5 % (TEXTE1b).
3. **`trafilatura` seule (E2).** 98,8 % en médiane, mais des pertes nettes sur RTBF et Auto-Moto (TEXTE1b).
4. **`trafilatura`, avec repli sur l'article marqué par la page (E3).** Retenue.

## Décision

Décision de Joël du 2026-11-01. Le texte vient de `trafilatura` 2.x, sans commentaires ni tableaux. Quand il fait moins de la moitié de ce que la page marque comme article (`articleBody` d'au moins 200 signes, sinon les longs paragraphes du plus grand `<article>`), ce texte marqué le remplace. `readability-lxml` ne sert plus qu'au titre.

**Mesure, sur 480 pages nouvelles et 48 de référence (TEXTE1c)** : 99,0 % de l'article en médiane contre 93,7 %, aucune page sous la moitié contre 2,1 %, aucune page en recul, 7,0 % de texte en trop contre 5,8 %, 46 ms par page au p95 contre 93 ms.

**La conclusion formelle de TEXTE1c est « partiel »** : le critère des 4 sites surveillés est raté (15 % pour Les Numériques, seuil de 5 %). À la relecture, ce sont des pages où l'ancienne extraction est plus longue parce qu'elle garde les tableaux de prix. Cette explication vient après la mesure. Joël décide de changer d'extraction malgré ce critère.

## Conséquences

- Les nouveaux articles sont lus ainsi. **Les anciens gardent leur texte** : leur relecture fera l'objet d'une demande à part, aux mêmes règles (robots, réserve TDM), après des essais réels.
- `articleBody` se lit dans les données de la page, qu'un lecteur ne voit pas. Il passe par le même nettoyage que tout texte venu du Web, et le filtre d'éléments cachés ne s'y applique pas.
- Limite connue : sur les pages à mur payant de Next.ink, le texte peut garder des éléments hors article (jusqu'à 65 % sur une page).
- Nouvelles dépendances, vérifiées par `tools/check_licenses.py` : `trafilatura` (Apache-2.0) et les bibliothèques qu'elle tire. `dateparser`, demandée par `htmldate`, est écartée : elle amènerait `regex` (Apache-2.0 AND CNRI-Python), hors du filtre de `TECH_CHOICES.md` §1.1. `htmldate` ne l'importe que si elle est présente, et Otlet ne lit pas de date avec `trafilatura`.
- Le filtre des éléments invisibles reste appliqué avant `trafilatura` : le banc lisait la page brute, d'où une revérification du code du produit sur les pages figées.

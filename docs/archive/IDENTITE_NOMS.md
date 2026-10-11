# Identité du projet : 20 noms candidats

Version 1, 2026-10-11. Statut : proposition, à valider par Joël.

## Méthode et limites

- Environ 85 noms testés ; 20 retenus ci-dessous, classés du plus solide au plus faible.
- **PyPI** : vérifié automatiquement le 2026-10-11 (`https://pypi.org/pypi/<nom>/json`, 404 = libre).
- **GitHub** : non vérifiable depuis cette session (accès API limité aux dépôts attachés). Le dépôt sera de toute façon sous le compte de Joël (`<compte>/<nom>`), donc pas de collision de chemin ; seule la disponibilité d'une organisation `github.com/<nom>` reste à contrôler à la main.
- **Conflits** : recherche Web (produits logiciels, médias, applis). **Aucune recherche de marque déposée** (EUIPO, BOIP Benelux, INPI) n'a été faite : à faire gratuitement sur [TMview](https://www.tmdn.org/tmview/) pour le nom retenu avant le premier commit public (cohérent avec Q-RM1, sans budget juridique).
- Critères appliqués : mémorisable, international, prononçable en français et en anglais, en lien avec veille, rédaction et publication, aucune référence à un fournisseur d'IA.

## Les 20 noms

| # | Nom | Signification | Conflits ou ambiguïtés constatés | Dépôt Git | Package Python | Verdict |
|---|-----|---------------|----------------------------------|-----------|----------------|---------|
| 1 | **Tamis** | Le tamis filtre : trier les sources fiables, ne garder que l'utile. Mot existant en français et en anglais (*tamis*, tamis fin). | Aucun logiciel homonyme trouvé. Prononciation divergente (FR « ta-mi », EN « tam-iss »), acceptable. Évoque la collecte et le tri plus que la publication. | `tamis` | `tamis` (libre) | **Retenu** |
| 2 | **Sourcelle** | Néologisme : *source* + suffixe ; la source qui reste visible, la traçabilité. | Aucun homonyme trouvé. Inventé, donc à expliquer. En anglais, risque de lecture « sour- » (aigre). | `sourcelle` | `sourcelle` (libre) | **Retenu** |
| 3 | **Fanal** | Feu de navire ou de phare : ce qui guide et se voit de loin (diffusion). Mot existant en FR, EN (rare) et ES. | Ancien client DNS dynamique « fanal » (linuxfr, inactif). En anglais, la sous-chaîne « anal » expose aux plaisanteries : réserve réelle pour un nom international. | `fanal` | `fanal` (libre) | Retenu sous réserve |
| 4 | Filon | Le bon filon : la veine d'information qui vaut la peine. | Aucun homonyme logiciel trouvé. Sans sens en anglais ; « filon » est plutôt familier en français. | `filon` | `filon` (libre) | Possible |
| 5 | Echora | Néologisme : écho + aura ; la rediffusion d'une information. | Une fiche SaaS « Echora » non identifiée existe. L'écho répète à l'identique, **contraire** à la règle « ne pas reproduire les sources ». Famille « Echo » saturée. | `echora` | `echora` (libre) | Faible |
| 6 | Vigie | Le guetteur en haut du mât : la veille. | Terme saturé dans la veille francophone (NetVigie, Vigiale…). Prononciation anglaise incertaine. Ne couvre pas la rédaction. | `vigie` | `vigie` (libre) | Faible |
| 7 | Plumeo | Plume + o : l'écriture. | Univers « Plume » très encombré (Plume Design, Plume Finance, Plume social). Prononciation divergente (« plu-mé-o » / « ploo-mee-o »). | `plumeo` | `plumeo` (libre) | Faible |
| 8 | Tracea | De *trace* : traçabilité des sources. | Préfixe « Trace » saturé (Traceo, TracePro…). Sonne comme un outil logistique. | `tracea` | `tracea` (libre) | Faible |
| 9 | Veillo | Veille + o. | Opaque hors francophonie ; en anglais évoque *veil* (voile, cacher), à l'opposé de la transparence des sources. | `veillo` | `veillo` (libre) | Écarté |
| 10 | Sourcier | Le sourcier trouve les sources. | Imprononçable en anglais ; « sour » ; proche de *Sourcery* (outil IA de revue de code). | `sourcier` | `sourcier` (libre) | Écarté |
| 11 | Orpailleur | Extraire les pépites du flux. | Imprononçable en anglais ; nom d'une équipe de recherche LORIA/Inria. | `orpailleur` | `orpailleur` (libre) | Écarté |
| 12 | Gazetta | La gazette. | Proche de *La Gazzetta dello Sport* et de nombreux médias « Gazeta » ; ferait passer l'outil pour un média. | `gazetta` | `gazetta` (libre) | Écarté |
| 13 | Nuntia | Latin : nouvelles, messages. | **Nunti** est déjà un lecteur RSS open source (Android/iOS) ; GNOME Nuntius. Prononciation instable. | `nuntia` | `nuntia` (libre) | Écarté |
| 14 | Calame | Le roseau taillé des scribes. | **Calame** est une application d'écriture pour Mac avec IA locale (2025) : conflit direct. | `calame` | `calame` (libre) | Écarté |
| 15 | Missive | Même mot en FR et EN. | **Missive** (missiveapp.com), messagerie d'équipe établie. PyPI pris. | `missive` | pris | Écarté |
| 16 | Ricochet | Même mot en FR et EN ; l'info rebondit vers les canaux. | Ricochet Refresh (messagerie sécurisée). PyPI pris. | `ricochet` | pris | Écarté |
| 17 | Relais | Le relais de l'information. | Marque hôtelière *Relais & Châteaux* ; « s » muet piégeux en anglais. PyPI pris. | `relais` | pris | Écarté |
| 18 | Glose | Le commentaire en marge d'un texte. | **Glose**, plateforme sociale de livres numériques (rachetée par Medium). | `glose` | `glose` (libre) | Écarté |
| 19 | Brevio | Bref + o : le résumé. | **Brevio News**, appli de résumés d'actualité par IA (Product Hunt) : même marché. | `brevio` | `brevio` (libre) | Écarté |
| 20 | Heraldo | Le héraut (espagnol). | Titres de presse *El Heraldo* (Mexique, Colombie, Aragon). | `heraldo` | `heraldo` (libre) | Écarté |

Écartés avant la liste, pour mémoire : Mercure (protocole Mercure, PyPI pris), Hermès, Iris, Echo, Atlas, Agora (saturés ou marques), Codex (produit d'un fournisseur d'IA), Lanterne (Lantern, logiciel anti-censure), Martinet (fouet, connotation négative), Scribeo (« Scribe » saturé), Kiosko (kiosko.net, presse), Pollen, Tessera, Semaphore, Provenance (PyPI pris).

## Revue critique

- Les mots réels courts et internationaux sont presque tous pris par un logiciel ou un média ; les survivants sont des mots rares (Tamis, Fanal, Filon) ou des néologismes (Sourcelle).
- Aucun nom ne couvre à lui seul collecte, rédaction **et** publication. Un nom métaphorique, porté par un sous-titre descriptif, est plus durable qu'un nom qui tente de tout dire. Sous-titre suggéré : « veille, rédaction et publication assistées, open source ».
- Les noms évoquant la répétition (Echo, Relais, Ricochet) ou un média (Gazetta, Heraldo) contredisent deux principes du projet : ne pas reproduire les sources et ne pas se faire passer pour un éditeur de presse.

## Recommandation (top 3)

1. **Tamis** : dépôt `tamis`, package `tamis`. Court, existe dans les deux langues, dit la valeur centrale (trier les sources fiables sous contrôle éditorial), aucun conflit trouvé.
2. **Sourcelle** : dépôt `sourcelle`, package `sourcelle`. Le plus « possédable » (néologisme), centré sur la traçabilité ; demande une explication.
3. **Fanal** : dépôt `fanal`, package `fanal`. Belle image de diffusion, mais la plaisanterie anglaise est un vrai risque.

Avant validation définitive : contrôle TMview (EUIPO, BOIP, INPI) du nom choisi, vérification manuelle de `github.com/<nom>`, et réservation immédiate du nom sur PyPI au premier paquet publié.

Sources consultées : [PyPI JSON API](https://pypi.org/), [Calame (mac4ever)](https://www.mac4ever.com/mac/191926-calame-une-nouvelle-app-d-ecriture-pour-mac-avec-une-ia-locale-e-10-licences-pour-vous), [Nunti (AlternativeTo)](https://alternativeto.net/software/nunti/about), [Missive (Capterra)](https://www.capterra.com/p/152884/Missive/reviews?page=2), [Brevio News (Product Hunt)](https://www.producthunt.com/products/brevio-news), [Glose (wwwhatsnew)](https://wwwhatsnew.com/?p=225712), [fanal (linuxfr)](https://linuxfr.org/news/fanal-un-client-pour-dns-dynamique), [NetVigie](https://www.lafabriquedunet.fr/logiciel/netvigie), [Lantern (Wikipedia)](https://en.wikipedia.org/wiki/Lantern_(software)), [Echora (saascity)](https://saascity.io/de/live/echora), [Traceo (App Store)](https://apps.apple.com/pl/app/traceo/id6742399173).

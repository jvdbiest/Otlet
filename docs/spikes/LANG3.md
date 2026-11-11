# LANG3 — Rédiger en FR, NL et EN à partir de sources dans les trois langues

| | |
|---|---|
| Statut | Conclue : partiel (langue et sources tenues ; faits au-dessus du seuil) |
| Durée maximale | 1 h de génération sur la VM .252, appels un par un ; 3 h de relecture |
| Ouverte le / conclue le | 2026-11-11 / 2026-11-11 |
| Choix concernés | `docs/design/MODELE_PAR_LANGUE.md` (réglage construit le 2026-11-11), LANG1, LANG2, aide à la phrase (REL2) |
| Commande de rejeu | `python /data/lang3.py` dans le conteneur `api` de la VM, puis `python3 spikes/lang3/analyse.py <dossier> prepare|aide|score` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Avec le réglage « Modèle par langue de rédaction » tel qu'il est construit, et gemma4 réglé pour le français, le néerlandais et l'anglais, Otlet rédige-t-il un brouillon juste et lisible dans chacune des trois langues, à partir de sources mêlant le français, le néerlandais et l'anglais ?

Origine : Joël, 2026-11-11, après la construction du réglage. LANG1 et LANG2 utilisaient des sources presque toutes françaises. Ici, chaque brief mêle les trois langues : il faut lire et croiser des sources dans une langue pour écrire dans une autre.

## 2. Critères de réussite

| Critère | Seuil, sur les 15 brouillons |
|---|---|
| M1. Le brouillon aboutit, dans la langue demandée, écrit par le modèle de la langue (`model_reason` = `language`) | 15 sur 15 |
| M2. Le brouillon cite au moins une source de chaque langue (FR, NL et EN) | ≥ 12 sur 15 |
| M3. Erreurs de faits (définition de LANG1) | 15 au plus en tout, et aucun brouillon avec plus de 3 |
| M4. Fautes de langue (définition de LANG1) | 20 au plus par langue de rédaction (5 brouillons) |
| M5. Passages non traduits : une phrase ou plus dans une autre langue que celle du brouillon, hors citation entre guillemets attribuée à son auteur | 2 au plus en tout |
| M6. Longueur d'au moins 70 % de celle demandée (ou de celle que la matière permet), et durée médiane d'une génération de 10 minutes au plus | 15 sur 15, et 10 min au plus |

**Succès** : les 6 critères. Le réglage tient ses promesses avec des sources multilingues. **Partiel** : M1, M2 et M5 sont tenus, mais pas M3, M4 ou M6. La rédaction multilingue fonctionne, mais la qualité reste à surveiller (relecture, aide à la phrase). **Échec** : M1, M2 ou M5 n'est pas tenu. Le réglage ne suffit pas à rédiger à partir de sources mêlées.

**Relevés sans seuil** : les erreurs de faits qui viennent d'une source dans une autre langue que le brouillon (mauvaise lecture ou mauvaise traduction) ; les citations coupées vues dans LANG1 ; les noms et chiffres repris d'une source NL ou EN.

## 3. Protocole

**Sujets et sources**, figés avant la mesure dans `spikes/lang3/subjects.json`. Ce sont 5 sujets de la semaine du 5 au 11 novembre 2026, couverts par des sources des trois langues dans la veille de Joël : la fusillade de Cracovie, l'affaire Jensen Huang chez Nvidia, la procédure de destitution visant Pete Hegseth, les pourparlers sur l'Ukraine à Abou Dhabi et la visite du pape Léon XIV en Argentine. Pour chaque sujet et chaque langue, ce sont les 3 articles les plus récents de la veille de Joël dont le titre porte sur le sujet, sans doublon de titre, ou tous s'il y en a moins. Les articles FR et EN ont leur texte complet. Les articles NL n'ont que leur résumé (De Morgen, De Tijd et De Standaard sont payants). Cela fait 36 articles : 15 FR, 13 NL, 8 EN (un seul article EN pour Cracovie et pour l'Ukraine).

> **Révision avant toute mesure (2026-11-11, accord de Joël).** La première version prenait ses articles anglais (BBC News, The Guardian) dans l'espace de test « Vérification X01 », pas dans la veille de Joël : Otlet a refusé de créer les briefs, et rien n'a été généré. Avec l'accord de Joël, BBC News et The Guardian ont été ajoutés à sa veille. Leurs flux ne gardent que les derniers jours : le Paraguay et la COP31 n'y étaient plus. Ces deux sujets sont remplacés par Hegseth et la visite du pape, couverts dans les trois langues. Les critères (§2) ne changent pas.

**Briefs.** Pour chaque sujet et chaque langue, un brief « [TEST_LANG3] » (titre demandé par Joël, gardé après la mesure) avec tous les articles du sujet, en matière, et la question du sujet écrite dans la langue du brief (`subjects.json`). La longueur est moyenne (600 mots), en mode synthèse, sans modèle fixé dans le brief : c'est le réglage par langue qui choisit. Cela fait 5 × 3 = **15 générations**, une à la fois, avec 30 secondes entre deux.

**Le réglage pendant la mesure.** Le script règle gemma4 pour le français, le néerlandais et l'anglais, sur le fournisseur « Modèles Locaux 2 ». Il remet ensuite exactement le réglage de Joël tel qu'il était (vide le 2026-11-11), y compris en cas d'erreur. Joël ne génère pas de brouillon sur .252 pendant la mesure.

**Relecture à l'aveugle**, comme dans LANG1 : les 15 brouillons sont mélangés et numérotés, avec l'aide à la phrase sous chaque phrase. Je relève les erreurs de faits, les fautes de langue et les passages non traduits. La langue de la source d'une erreur est notée. M2 est compté par le script, d'après les sources citées par chaque brouillon. L'aide à la phrase retrouve mal une phrase de source dans une autre langue quand elle n'a ni nom ni chiffre : je relis alors la source citée en entier.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Les défauts éventuels sont rapportés, puis traités avec Joël.

## 4. Mesures

Le 2026-11-11, de 11 h 27 à 12 h 05, sur la VM .252 : 15 générations, une à la fois, puis la relecture à l'aveugle avec l'aide à la phrase. Le réglage par langue de Joël a été remis à vide à la fin. Les briefs « [TEST_LANG3] » restent dans son espace, comme il l'a demandé. Fichiers : `spikes/lang3/results/` (grille, notes par brouillon, `rapport.txt`). Les brouillons complets sont sur la VM, dans `~/s-lang3/`.

| Critère | Seuil | Mesuré | |
|---|---|---|---|
| M1. Aboutis, dans la langue demandée, par le modèle de la langue | 15 sur 15 | **15 sur 15** (gemma4, `model_reason` = `language`) | ✅ |
| M2. Sources des trois langues citées | ≥ 12 sur 15 | **15 sur 15** | ✅ |
| M3. Erreurs de faits | ≤ 15, aucun brouillon > 3 | **24**, au plus 3 par brouillon | ❌ |
| M4. Fautes de langue | ≤ 20 par langue | FR 6, **NL 16**, EN 2 | ✅ |
| M5. Passages non traduits | ≤ 2 | **0** | ✅ |
| M6. Longueur et durée | 15 sur 15, ≤ 10 min | 14 sur 15 (Ukraine EN : 405 mots pour 420 au moins), **1,7 min** | ❌ |

**Par langue de rédaction**, les erreurs de faits : FR 6, NL 10, EN 8. Le néerlandais cumule le plus d'erreurs de faits et de fautes de langue, comme dans LANG1.

**Erreurs qui viennent d'une source dans une autre langue** que le brouillon : 14 sur 24. Deux motifs reviennent, chacun dans les trois brouillons du sujet :
- **Un titre néerlandais mal compris.** « Poetin stuurt met Vladimir Medinsky zijn favoriete geschiedenisherschrijver » (Poutine envoie celui qui réécrit l'histoire pour lui) devient « son historien favori » (FR), « his favorite historian » (EN) et « een geschiedschrijver die bekend staat om zijn favoriete geschiedschrijving » (NL). Le sens critique du titre est perdu.
- **Un fait d'Uruguay rangé dans l'Argentine.** Le résumé néerlandais « Paus Leo maant in Uruguay… roept jongeren op te trouwen en kinderen te krijgen » finit dans le récit de la visite en Argentine (FR, NL, EN).

Les autres erreurs sont celles de LANG1 : qui a dit quoi (les Ukrainiens et Kushner, la loyauté de Trump envers Hegseth), une date de publication prise pour la date du vote (Hegseth), et quelques ajouts sans source (« la pauvreté a fortement augmenté », « 320 km »). Deux sources se contredisent sur le nombre d'armes du tireur de Cracovie (sept pour la source FR, quatre pour la source EN) : les brouillons en prennent une sans signaler l'écart. Ce n'est pas compté comme une erreur.

**Ce qui marche bien.** Aucun brouillon ne recopie une phrase dans une autre langue. Les citations anglaises sont traduites (« EXONERATION of a Great American Patriot » devient « mise hors de cause d'un grand patriote américain ») ou gardées entre guillemets et attribuées. Les noms et les chiffres repris des sources anglaises sont justes : 211 contre 204, Swit Starachowice, Oksinski, 400 milliards de dollars.

**Toujours là.** Le défaut des citations coupées : 2 phrases de l'Ukraine EN s'arrêtent juste avant la citation (« were », « praised the talks as »).

## 5. Conclusion

**Partiel**, au sens fixé d'avance : M1, M2 et M5 sont tenus, M3 et M6 non.

- **Le réglage par langue fonctionne avec des sources mêlées.** Les 15 brouillons sont dans la bonne langue, écrits par gemma4 grâce au réglage, en 1 min 40 environ. Chacun s'appuie sur des sources des trois langues, sans passage non traduit.
- **La justesse reste la limite, comme dans LANG1.** Il y a 24 erreurs de faits au lieu de 15 au plus, soit 1,6 par brouillon. Plus de la moitié vient d'une source lue dans une autre langue, surtout des **titres et résumés néerlandais**, courts et allusifs, que gemma4 interprète mal.
- **Le néerlandais reste la langue la plus fragile**, en faits (10) comme en langue (16 fautes, juste sous le seuil).
- **L'aide à la phrase reste indispensable**, mais elle retrouve mal une source dans une autre langue que le brouillon quand la phrase n'a ni nom ni chiffre (Medinsky, Uruguay). C'est une piste d'amélioration.

Pistes à discuter avec Joël, hors de ce banc :
1. Les résumés NL des sites payants sont la matière la plus risquée. Faut-il les marquer « résumé seulement » dans le brief, ou les mettre en contexte plutôt qu'en matière ?
2. L'aide à la phrase pourrait chercher aussi par les noms propres d'une phrase voisine, pour mieux relier une phrase à une source dans une autre langue.
3. Le défaut des citations coupées, toujours présent (vu dans LANG1).

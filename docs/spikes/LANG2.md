# LANG2 — Une ligne de langue neutre dans la charte suffit-elle à tenir la langue du brief ?

| | |
|---|---|
| Statut | Protocole, en attente de fusion |
| Durée maximale | 3 h de génération sur la VM .252, appels un par un ; pas de relecture des faits |
| Ouverte le | 2026-11-11 |
| Choix concernés | LANG1, `docs/design/MODELE_PAR_LANGUE.md`, charte d'écriture (`writing/domain/charter.py`), contrôle de langue du brouillon |
| Commande de rejeu | `python /data/lang2.py` dans le conteneur `api` de la VM, puis `python3 spikes/lang2/analyse.py <dossier>` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

La charte d'écriture se termine par « 20. Écris dans un français correct, clair, fluide et professionnel. ». Si on remplace cette seule ligne par une consigne neutre, les brouillons demandés en néerlandais ou en anglais restent-ils dans la langue du brief ?

Origine : Joël, 2026-11-11, après LANG1. Dans LANG1, 7 brouillons sur 30 demandés en NL ou en EN sont sortis en français, dont 5 de qwen3:14b. Or la charte est envoyée avec chaque brief, quelle que soit sa langue. Le prompt précise même « The charter prevails over the brief » (`writing/domain/draft.py`). La charte par défaut du produit contient la même ligne. Joël veut d'abord mesurer ce changement simple, avant d'envisager des chartes complètes par langue.

## 2. Critères de réussite

Deux chartes sont comparées dans la même nuit, sur les mêmes briefs :
- **A** est la charte actuelle de Joël, inchangée ;
- **B** est la même charte, dont la ligne 20 devient : « 20. Écris dans la langue de rédaction demandée par le brief, dans un style correct, clair, fluide et professionnel. ».

Un brouillon **tient la langue** si la langue reconnue dans son texte final (`language_written`, la même mesure que le contrôle de langue) est celle du brief.

| Critère | Seuil |
|---|---|
| L1. qwen3:14b avec B : brouillons qui tiennent la langue | ≥ 8 sur 10 |
| L2. qwen3:14b : gain de B sur A, dans cette même mesure | ≥ 3 brouillons |
| L3. gemma4 avec B : brouillons qui tiennent la langue | 10 sur 10 (aucun recul) |
| L4. Brouillons de B qui aboutissent (qwen3 et gemma4) | 20 sur 20 |

**Succès** : les 4 critères. La ligne neutre suffit : on la propose pour la charte de Joël et pour la charte par défaut du produit, sans chartes par langue. **Partiel** : L2 tenu (B gagne au moins 3 brouillons), mais pas L1. La ligne aide sans suffire, et des chartes par langue restent à mesurer (LANG3). **Échec** : gain de moins de 3 brouillons. La ligne de la charte n'est pas la cause principale : on cherche ailleurs (la langue des sources, le prompt), avant toute charte par langue.

**Mesure secondaire, sans seuil** : la langue de la **première** réponse du modèle, avant toute réparation. Le contrôle de langue la note dans les refus (« language: the article is written in … »). Elle montre l'effet de la charte seule, sans la réparation.

## 3. Protocole

**Briefs.** Les 10 combinaisons néerlandais et anglais de LANG1 : 5 sujets (MotoGP, Route du Rhum, Nvidia, CPAS, Cracovie) × 2 langues. Ce sont les mêmes articles, la même matière, le même contexte, la longueur moyenne et le titre « [LANG2] ». Le français n'est pas mesuré, car la ligne actuelle le sert déjà.

**Modèles et passages.**
- **qwen3:14b** : 10 briefs avec A, puis 10 avec B, en alternant A et B brief par brief. Il a fait 5 des 7 brouillons sortis en français dans LANG1. A est rejoué pour avoir un témoin de la même nuit, car un seul passage de LANG1 ne suffit pas comme référence.
- **gemma4** : les 10 briefs avec B seulement. Il a tenu la langue 15 fois sur 15 avec A dans LANG1 ; on vérifie que B ne le fait pas reculer.
- **mistral-small** n'est pas mesuré : ses dépassements du délai de 10 minutes de la passerelle (LANG1) rendraient la mesure longue et peu lisible.

Cela fait **30 générations**, une à la fois, avec 30 secondes entre deux. Elles prennent environ 1 h 30. Le produit tourne tel quel, avec son contrôle de langue et sa réparation.

**La charte pendant la mesure.** La charte est un réglage de l'utilisateur, lu au moment de rédiger. Le script enregistre d'abord la charte de Joël telle qu'elle est (ou l'absence de charte propre), puis pose A ou B avant chaque génération. À la fin, ou en cas d'erreur, il remet exactement la charte d'origine et vérifie qu'elle est identique. Pendant la mesure, Joël ne génère pas de brouillon sur .252, sinon le sien utiliserait la charte du moment.

**Ce qui est relevé**, sans relecture : la langue du texte final, la langue de la première réponse, si la génération aboutit, la longueur, la durée et les refus.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. La justesse des faits n'est pas relue : la ligne 20 ne porte que sur la langue. Si B réussit, la modification de la charte de Joël et de la charte par défaut sera proposée à part.

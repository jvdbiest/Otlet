# ADR-0043 — Assistant de veille : le glossaire trouve, le modèle ordonne

| | |
|---|---|
| Statut | Accepté (2026-10-25) ; mise en œuvre par lots (A1b-1 d'abord) |
| Date | 2026-10-25 |
| Décideur | Joël |
| Documents touchés | ADR-0041 (A1b recadré ; évaluateur réutilisé) ; ADR-0035 (recherche plein texte) ; ADR-0027 (choix du modèle par l'utilisateur) ; backlog d'É1 (A1b-1, A1b-2) |
| Origine | Fil de Joël du 2026-10-24 ; document partagé « Otlet · A1b : Assistant de veille » ; banc `spikes/a1b-veille` |

## Contexte

Les essais de rédaction d'octobre ont déplacé la difficulté : la génération tient, mais la matière se trouve mal. Pour écrire sur un sujet, Joël cherche lui-même dans la Veille, et n'est jamais sûr d'avoir trouvé les bonnes sources. Sur sa Veille réelle, la recherche actuelle échoue de six façons : bruit (« Bruxelles » est partout), matière absente, classement qui ignore l'angle, rappel faible, sujets mêlés, et langue (environ 260 éléments néerlandais qu'une recherche en français ne trouve jamais).

L'ADR-0041 prévoyait A1b, « Partir d'une idée », qui passait directement de l'idée au brief. Joël l'a recadré en **Assistant de veille** : une étape visible, avant le brief, qui découvre et regroupe la matière.

Le banc (6 sujets réels, 251 candidats dont 21 en néerlandais, qwen3:14b local, référence relue par Joël) a mesuré :

| | Recherche actuelle | Termes élargis + glossaire | + tri par le modèle (2e passage) |
|---|---|---|---|
| Matière pertinente retrouvée | 76 % | 100 % | 96 % (retenus + à vérifier) |
| Néerlandais retrouvés | 1 sur 9 | 9 sur 9 | 8 sur 9 |
| Éléments à lire | 108 | 251 | 104, dont 70 % pertinents |

Les termes élargis par le modèle seul échouent sur les sujets belges (zéro résultat pour le budget de Bruxelles, néerlandais inventé). Au premier passage, le tri écartait 9 % de la matière et inventait des liens dans ses raisons ; trois corrections les ont ramenés à 4 % et à zéro lien inventé parmi les raisons relues.

## Décision

1. **Le glossaire trouve, le modèle ordonne.** La découverte de la matière repose sur une recherche sans modèle, par termes élargis et glossaire. Le modèle ne sert qu'à juger la pertinence, pour ordonner et regrouper ; il n'exclut jamais seul un élément.
2. **Des termes élargis visibles.** Le sujet est découpé en concepts (deux au plus), chacun avec ses termes en français, néerlandais et anglais, affichés comme des étiquettes que l'auteur retire ou complète avant la recherche. Le modèle peut proposer des termes ; le glossaire les complète ; l'auteur décide. La recherche cherche chaque terme dans chaque langue de l'index (ADR-0035) : un élément doit contenir un terme de chaque concept.
3. **Un glossaire, brique commune d'Otlet.** Des équivalences entre termes (« Bruxelles-Capitale = Brussels Hoofdstedelijk Gewest = Brussels-Capital Region »), propres à l'espace, gérées dans ses Réglages et enrichies depuis l'assistant. Il sert aussi aux sujets de veille, à A1a et au futur pilote automatique, toujours sans appel au modèle.
4. **Un dossier en trois groupes.** Retenus (le modèle dit « traite »), à vérifier (« proche », ou tout élément que le modèle n'a pas pu juger), écartés (« hors sujet », repliés, jamais cachés, un clic les remet). Chaque élément porte sa raison et s'ouvre sur sa source.
5. **Règles du tri**, issues du banc :
   - le modèle ne voit que le titre, le début du résumé, la langue, l'éditeur et le **pays de l'éditeur**, tiré de l'adresse de l'élément sans modèle ;
   - **l'angle départage « traite » et « proche », il n'écarte jamais** ;
   - **aucun lien que l'élément n'écrit pas** : sans lien écrit, l'élément est au plus « proche » ;
   - un élément **sans résumé** va dans « à vérifier » sans être soumis au modèle ;
   - un numéro inconnu dans la réponse est ignoré ; un élément sans verdict va dans « à vérifier ».
6. **Le dossier est enregistré** : sujet, angle, concepts et termes, candidats, verdicts, raisons, modèle et version du prompt, rattachés à l'espace et à leur auteur, sous RLS. Il sert à reprendre, à retrouver pourquoi un élément a été écarté, et plus tard au pilote automatique.
7. **Vers le brief.** La sélection ouvre le formulaire de brief existant, pré-rempli (éléments, titre de travail, angle, nature) ; le niveau de matière d'A1a est calculé sur la sélection dès le dossier. Rien n'est enregistré ni généré sans action de l'auteur.
8. **Le modèle de l'utilisateur** (ADR-0027) : celui de son profil, local ou hébergé. Les appels sont courts (lots d'environ 25 éléments, titres et résumés), pour rester utilisables avec un modèle local.
9. **Découpage** :
   - **A1b-1** : sujet, concepts et termes, glossaire, recherche, dossier, tri, vers le brief ;
   - **A1b-2** (après usage) : thèmes et angles proposés, brouillon de brief complet, entrées depuis Veille › Éléments et Sujets ;
   - le banc est rejoué à chaque changement du prompt de tri, avec les mêmes seuils : au moins 20 points de rappel sur la recherche actuelle, moins de 10 % de pertinents écartés, trois néerlandais sur quatre retrouvés, aucune raison inventée.

## Conséquences

- La recherche plein texte gagne une forme « par concepts », réutilisable ailleurs (sujets de veille).
- Le pays de l'éditeur, tiré de l'adresse, pourra devenir un champ de la source, corrigeable.
- L'évaluateur d'A1a reste la seule règle de la matière ; l'assistant l'appelle, il ne la recopie pas.
- A1a-2 (« Voir d'autres éditeurs », « Chercher dans la Veille ») trouve naturellement sa place dans le dossier ; il pourra y être absorbé si l'usage le confirme.
- Le pilote automatique (ADR-0041, perspective) pourra produire des dossiers réguliers à partir d'un sujet suivi ; leur qualification reste une aide, jamais une interdiction.

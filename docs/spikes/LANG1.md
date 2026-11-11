# LANG1 — Quel modèle local écrit le mieux dans chaque langue ?

| | |
|---|---|
| Statut | Conclue : échec (aucun modèle retenu, dans aucune langue) |
| Durée maximale | 8 h de génération sur la VM .252, appels un par un ; 4 h de relecture |
| Ouverte le / conclue le | 2026-11-10 / 2026-11-11 |
| Choix concernés | `docs/design/MODELE_PAR_LANGUE.md`, ADR-0027, contrôle de langue du brouillon |
| Commande de rejeu | `python /data/lang1.py` dans le conteneur `api` de la VM, puis `python3 spikes/lang1/analyse.py <dossier>` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Pour chaque langue de rédaction, un des modèles locaux installés écrit-il mieux que les autres, de façon stable sur plusieurs sujets ? Si oui, un mode « Automatique » du réglage « Modèle par langue de rédaction » peut-il s'appuyer sur ce résultat ?

Origine : Joël, 2026-11-10. Sur le seul brief MotoGP en néerlandais, gemma4 écrivait le mieux, mistral-small faisait le moins d'erreurs de faits mais prenait 33 minutes, et qwen3:14b était le plus faible. Un seul brief ne suffit pas pour conclure.

## 2. Critères de réussite

Un modèle est **retenu pour une langue** s'il tient les six critères suivants sur les 5 sujets de cette langue :

| Critère | Seuil, sur les 5 brouillons d'un modèle dans une langue |
|---|---|
| C1. Le brouillon aboutit, dans la langue demandée | 5 sur 5 |
| C2. Erreurs de faits (§3) | 5 au plus en tout |
| C3. Fautes de langue (§3) | 20 au plus en tout |
| C4. Brouillons avec plus de 2 phrases répétées (§3) | aucun |
| C5. Longueur d'au moins 70 % de celle demandée (ou de celle que la matière permet) | 5 sur 5 |
| C6. Durée médiane d'une génération | 10 minutes au plus |

**Le meilleur modèle d'une langue** est, parmi ceux retenus, celui qui a le moins d'erreurs de faits, puis le moins de fautes de langue. Il est **stable** s'il est premier ou premier ex aequo sur au moins 3 des 5 sujets, au score par sujet de 3 × erreurs de faits + fautes de langue.

**Succès** : dans chacune des trois langues, un modèle est retenu et son avance est stable. Le mode « Automatique » peut alors être proposé pour les trois langues. **Partiel** : c'est le cas pour une ou deux langues seulement. Le mode « Automatique » ne serait proposé que pour elles. **Échec** : aucune langue. On garderait le réglage manuel, sans mode « Automatique ».

## 3. Protocole

**Langues.** Français, néerlandais, anglais : les langues dans lesquelles Joël publie.

**Modèles.** Les trois déjà essayés sur le brief MotoGP, sur le fournisseur « Modèles Locaux 2 » (Ollama du PC de Joël) : `qwen3:14b`, `mistral-small:latest`, `gemma4:latest`. Les autres modèles installés (llama3.1, mistral-nemo, deepseek-r1, gemma4-balanced) restent hors du banc. On pourra les ajouter dans un banc suivant si l'un des trois échoue partout.

**Sujets.** Cinq briefs existants de l'instance de Joël, choisis avant la mesure pour couvrir des domaines et des difficultés différents. Ils viennent des cas de référence, de RB1 ou des essais « [TEST] » :

| Sujet | Brief d'origine | Articles | Pourquoi |
|---|---|---|---|
| Grand Prix du Qatar de MotoGP | `3cc4fad5` | 18 | rangs et noms, cas de référence de la fidélité |
| Route du Rhum | `9618fc38` | 4 | noms propres, matière courte (cas Beaudart) |
| Le patron de Nvidia | `c22f90fc` | 6 | économie et technologie, termes anglais |
| Les CPAS et la circulaire Van Bossuyt | `2e70f69f` | 6 | politique belge, noms néerlandais |
| Cracovie | `e850ae32` | 10 | fait divers international, chronologie |

**Génération.** Pour chaque sujet, langue et modèle, une copie du brief avec les mêmes articles, la même matière et le même contexte, l'angle et les consignes d'origine, la longueur « moyenne » (600 mots) et la langue et le modèle du banc. Le titre commence par « [LANG1] ». Cela fait 5 × 3 × 3 = **45 générations**, une à la fois, avec 30 secondes entre deux. Le produit tourne tel quel, avec son contrôle de langue et sa réparation. Une génération qui dure plus de 40 minutes est arrêtée et comptée comme non aboutie (C1). Rien d'autre ne tourne sur la VM pendant la mesure.

**Relecture à l'aveugle.** Les 45 brouillons sont mélangés et numérotés de L01 à L45 dans un fichier de lecture qui ne nomme pas le modèle. La correspondance est gardée dans un fichier à part. Elle n'est ouverte qu'une fois la grille remplie. Pour chaque brouillon, je relève :
- **les erreurs de faits** : un fait contraire aux sources (un rang, un chiffre, une date, qui fait quoi), ou un fait absent des sources présenté comme sûr. Chaque phrase est vérifiée avec l'aide à la phrase (REL2), qui montre ses phrases de source. Un même fait faux répété compte une fois ;
- **les fautes de langue** : un mot qui n'existe pas, un mot d'une autre langue laissé tel quel (hors noms propres et termes d'usage), un accord ou une construction fautive, un calque qui gêne la lecture. Une même faute répétée compte une fois.

**Répétitions, sans relecture** (`analyse.py`). Une phrase est répétée si elle partage au moins 70 % de ses mots (de 6 lettres ou plus) avec une phrase précédente du même brouillon.

**Longueur et durée.** Elles sont relevées par le script : le nombre de mots du chapô et des paragraphes, et la durée entre la demande et la fin de la génération.

**Limites connues, écrites avant la mesure.**
- Il y a un seul essai par combinaison. La stabilité sur 5 sujets en tient lieu.
- Je relis le néerlandais sans en être locuteur natif. Joël relira, s'il le veut, 5 brouillons néerlandais tirés au hasard. Un écart de plus de 3 fautes de langue sur un brouillon serait signalé dans les mesures.
- Les durées dépendent de la charge du PC de Joël. Elles seront données telles quelles.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Les règles du mode « Automatique » seront décidées avec Joël après la mesure (`docs/design/MODELE_PAR_LANGUE.md`, §4).

## 4. Mesures

Du 2026-11-10 à 21 h 06 au 2026-11-11 à 2 h 09, sur la VM .252 avec l'Ollama du PC de Joël : 45 générations, une à la fois. La relecture à l'aveugle a suivi, avec l'aide à la phrase sur chaque phrase (`aide.py`). La correspondance n'a été ouverte qu'une fois la grille remplie. Fichiers : `spikes/lang1/results/` (grille et notes par brouillon, `rapport.txt`, correspondance). Les brouillons complets et l'aide sont sur la VM, dans `~/s-lang1/`.

| Langue | Modèle | C1 aboutis, bonne langue | C2 faits | C3 langue | C4 | C5 longueur | C6 médiane | Retenu |
|---|---|---|---|---|---|---|---|---|
| fr | gemma4 | 5/5 | 6 ❌ | 7 | 1 ❌ | 5/5 | 1,7 min | non |
| fr | mistral-small | 4/5 ❌ | 4 | 2 | 0 | 2/5 ❌ | 11,7 min ❌ | non |
| fr | qwen3:14b | 5/5 | 11 ❌ | 4 | 0 | 4/5 ❌ | 2,7 min | non |
| nl | gemma4 | 5/5 | 6 ❌ | 24 ❌ | 0 | 5/5 | 2,0 min | non |
| nl | mistral-small | 3/5 ❌ | 5 | 11 | 2 ❌ | 3/5 ❌ | 18,7 min ❌ | non |
| nl | qwen3:14b | 2/5 ❌ | 7 ❌ | 16 | 0 | 4/5 ❌ | 3,3 min | non |
| en | gemma4 | 5/5 | 6 ❌ | 3 | 0 | 5/5 | 1,7 min | non |
| en | mistral-small | 2/5 ❌ | 2 | 1 | 1 ❌ | 2/5 ❌ | 13,3 min ❌ | non |
| en | qwen3:14b | 3/5 ❌ | 7 ❌ | 1 | 0 | 3/5 ❌ | 2,3 min | non |

**Aucun modèle n'est retenu, dans aucune langue.** La stabilité sur les sujets n'a donc pas lieu d'être calculée.

**Ce qui a fait échouer chaque modèle.**
- **gemma4** écrit toujours dans la langue demandée (15 sur 15) et il est le plus rapide (2 min environ). Il échoue de peu sur les faits, avec 6 erreurs au lieu de 5 au plus dans chaque langue. La moitié vient de la Route du Rhum : propos de Francis Le Goff et de Franck Cammas attribués à Laperche, Beaudart qui saluerait Horeau (le cas de référence), Le Cléac'h présenté comme le mentor de Laperche. En néerlandais, il fait aussi 24 fautes de langue sur 5 brouillons (« een intense duel », « achterwiel », « rechterradius », « werd neutraliseerd », « CPAS » au lieu de « OCMW »). En français, un brouillon contient quatre fois la ligne parasite « Otlet ajoute les références des sources: les sources. ».
- **mistral-small** fait le moins d'erreurs de faits, mais 4 générations sur 15 dépassent le délai de 10 minutes de la passerelle, deux fois de suite, et échouent. Deux autres sortent en français alors que le néerlandais ou l'anglais était demandé. Sa durée médiane dépasse 10 minutes dans les trois langues, et il répète des phrases (jusqu'à 5 dans un brouillon).
- **qwen3:14b** a écrit 5 brouillons en français sur 10 demandés en néerlandais ou en anglais. C'est aussi lui qui fait le plus d'erreurs de faits en français (11), dont l'erreur de référence du MotoGP : « Martín, malgré sa deuxième place dans la course Sprint », et même Martín « leader du championnat ».

**Brouillons écrits en français au lieu de la langue demandée : 7 sur 30.** Ce sont 5 brouillons de qwen3 et 2 de mistral-small. Chaque fois, le contrôle de langue a renvoyé la première réponse (« language: the article is written in français »), et la réparation est restée en français. Le brouillon garde alors l'avertissement « écrit en français ». Une piste, à vérifier hors de ce banc : la charte d'écriture de Joël, envoyée avec chaque brief quelle qu'en soit la langue, se termine par « Écris dans un français correct, clair, fluide et professionnel ».

**Deux défauts du produit vus en passant, sans lien avec la langue.**
- Dans 3 brouillons de gemma4 (L14, L15, L17), des phrases s'arrêtent juste avant une citation (« Het bedrijf stelt dat de interacties tussen Jensen Huang en Alice Huang » sans la suite), 9 fois en tout. La citation a disparu entre la réponse du modèle et le brouillon.
- La ligne « Otlet ajoute les références des sources: les sources. » est une consigne du prompt recopiée telle quelle dans le texte.

**Limites.** Il y a un seul essai par combinaison. Je relis le néerlandais sans en être locuteur natif, et Joël n'a pas encore relu les 5 brouillons néerlandais tirés au hasard. Les erreurs de faits ont été relevées avec l'aide à la phrase, qui retrouve mal une phrase française pour une phrase néerlandaise ou anglaise quand elle n'a ni nom ni chiffre. Une invention discrète a donc pu m'échapper, plus en NL et en EN qu'en FR.

## 5. Conclusion

**Échec**, au sens fixé d'avance : aucun modèle n'est retenu, dans aucune langue. Il n'y a donc pas de base pour un mode « Automatique ». Le réglage « Modèle par langue de rédaction » peut être fait sans lui (`docs/design/MODELE_PAR_LANGUE.md`, §4).

Ce que le banc montre malgré tout, pour éclairer le choix manuel :
- **gemma4 est le seul modèle utilisable dans les trois langues.** Il aboutit toujours, dans la bonne langue, en 2 minutes, et il échoue de peu sur les faits. Son néerlandais reste fautif.
- **Choisir un modèle par langue ne corrige pas les erreurs de faits.** Les trois modèles se trompent sur les mêmes points : qui dit quoi, et les rangs. L'aide à la phrase reste nécessaire, quelle que soit la langue.
- **mistral-small n'est pas utilisable sur ce matériel** : il dépasse trop souvent le délai de la passerelle.
- **qwen3:14b ne tient pas la langue demandée** en néerlandais ni en anglais.

Trois sujets à trancher avec Joël, hors de ce banc :
1. La charte d'écriture : faut-il la rendre neutre en langue, ou ajouter dans le prompt que la langue du brief l'emporte sur celle de la charte ?
2. Les citations coupées et la ligne parasite : deux défauts du produit à corriger, à mesurer sur les brouillons de ce banc.
3. Le réglage manuel « Modèle par langue de rédaction », sans mode « Automatique », avec gemma4 seulement comme conseil affiché.

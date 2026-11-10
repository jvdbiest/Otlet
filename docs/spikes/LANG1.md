# LANG1 — Quel modèle local écrit le mieux dans chaque langue ?

| | |
|---|---|
| Statut | Protocole, en attente de fusion |
| Durée maximale | 8 h de génération sur la VM .252, appels un par un ; 4 h de relecture |
| Ouverte le | 2026-11-10 |
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

À venir.

## 5. Conclusion

À venir.

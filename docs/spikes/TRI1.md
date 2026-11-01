# TRI1 — Le tri du Reporter retient-il ce qui répond à la question ?

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 3 h de mesure (une heure de modèle attendue) |
| Temps passé | à remplir |
| Ouverte le / conclue le | 2026-11-01 / à remplir |
| Choix concernés | ADR-0043 §5 (tri sans exclusion), ADR-0044 (Reporter) |
| Commande de rejeu | `spikes/tri1/run-tri1.sh` puis `python3 spikes/tri1/tri1.py <dossier> --summary` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Quand l'auteur trie un ensemble du Reporter, le verdict « traite » retient-il les articles qui répondent à la question, sans y mêler ceux qui ne font que partager un mot ou un thème ? Et une variante fait-elle nettement mieux que le tri actuel ?

Origine : Joël, 2026-11-01. Sur la question du froid, 7 articles du brief étaient jugés « traite » pour une simple mention. Sur l'Ukraine, une source portait sur la présidentielle bulgare, et le brouillon lui a consacré une section. La recherche ramène désormais plus d'articles (`spikes/a2-sens/RAPPORT.md`), donc le tri compte davantage.

Constat à la lecture du code : le tri ne reçoit pas la question. Il reçoit les noms des concepts (`reporter.py`, `subject`), par exemple « Ukraine » seul.

FOND1 a montré que qwen3:14b juge mal les nuances : TRI1 ne présume pas que ce jugement soit fiable.

## 2. Critères de réussite

Mesurés sur l'ensemble des 7 questions, sans les articles sans résumé (la règle du produit les met en « à vérifier »). R, T et H sont définis au §3. L'Ukraine pèse 60 articles R sur 100 : les quatre premiers critères doivent tenir sur les 7 questions **et** sur les 6 autres.

| Critère | Seuil |
|---|---|
| Part des articles R jugés « traite » | ≥ 85 % |
| Part des articles R jugés « hors_sujet » (faux rejets) | ≤ 3 % |
| Part de R parmi les « traite » (précision) | ≥ 75 % |
| Part des articles H jugés « traite » | ≤ 5 % |
| Froid : articles R jugés « traite » | au moins 5 sur 6 |
| Ukraine : articles de la présidentielle bulgare jugés « traite » | 0 sur 4 |

**Succès** : une variante tient les 6 critères. **Partiel** : une variante améliore nettement la précision sans perdre de rappel, sans tenir les 6. **Échec** : aucune ne fait mieux que le tri actuel ; le tri reste une aide à la lecture, et le brief ne doit pas s'y fier seul.

## 3. Protocole

**Environnement.** VM .252, code de `main` déployé, passerelle du produit, profil de Joël (qwen3:14b sur Ollama de son PC). Aucun build, test ni autre appel au modèle pendant la mesure. Appels un par un, 5 s de pause. Rien n'est écrit dans son instance, sauf le journal des appels de la passerelle, comme pour tout appel.

**Jeu.** Les 7 ensembles de l'essai réel du 2026-11-01, figés : 363 articles (froid 39, Ukraine 123, hôpitaux en Flandre 18, pertes d'emploi 54, essais de motos 65, Ahold Delhaize 31, prix de l'énergie 33), dont 10 sans résumé. Les titres et les résumés restent sur la VM (`items.jsonl`) ; le dépôt ne garde que les titres et les étiquettes (`spikes/tri1/labels.csv`).

**Référence.** Étiquettes écrites par Claude d'après le titre et le début du résumé, avant toute mesure et sans verdict de modèle sous les yeux. Joël peut les corriger avant la fusion.
- **R** : répond à la question, ou la question porte sur son sujet principal.
- **T** : même thème sans y répondre, ou le sujet n'y est qu'un contexte.
- **H** : hors sujet.

**Variantes, par lots de 25 comme le produit.**
- **A, le tri actuel** : le prompt `veille-2` et le sujet fait des noms des concepts de l'essai.
- **B** : le même prompt, avec la question de l'auteur comme sujet.
- **C** : la question de l'auteur et un prompt qui distingue « répond » de « même thème » (`ANSWERS_SYSTEM`, `spikes/tri1/tri1.py`). Il donne un exemple pris hors du jeu.

**Volume.** 54 appels (18 par variante), un passage chacun. Estimation d'après le tri de 65 articles en 214 s : environ une heure de modèle. Un appel pilote d'abord, pour vérifier le montage ; il compte dans les 54.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si une variante réussit, le changement du tri sera proposé à Joël à part.

## 4. Mesures

À remplir après la mesure.

## 5. Conclusion

À remplir.

## 6. Conséquences

À remplir.

## 7. Ce que la preuve n'a pas couvert

- Un seul auteur d'étiquettes, qui a aussi écrit la variante C : le risque de biais est réel. Joël peut relire `labels.csv`.
- Les titres et 300 caractères de résumé seulement, comme le tri du produit : un article peut répondre plus loin dans son texte.
- 7 questions, un passage par variante : ni la stabilité du modèle, ni d'autres modèles ne sont mesurés.
- La rédaction du brief à partir des articles retenus n'est pas mesurée.

# TRI2 — Le tri sait-il séparer « répond à la question » de « même thème » ?

| | |
|---|---|
| Statut | Conclue : échec |
| Durée maximale | 4 h de mesure (environ 1 h 30 de modèle attendue) |
| Temps passé | 2 h de préparation et d'analyse (journal de temps, TRI2) ; 93 min de modèle |
| Ouverte le / conclue le | 2026-11-07 / 2026-11-07 |
| Choix concernés | ADR-0043 §5 (tri sans exclusion), ADR-0044 (Reporter), TRI1 |
| Commande de rejeu | `spikes/tri2/run-tri2.sh` puis `python3 spikes/tri2/tri2.py <dossier> --summary` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Une façon de trier fait-elle nettement mieux que le tri actuel (B, la question envoyée au tri, #127) pour ne retenir en « traite » que les articles qui répondent à la question, et non ceux qui partagent seulement son thème ? Garde-t-elle les bons articles, et donne-t-elle le même verdict d'un passage à l'autre ?

Origine : Joël, 2026-11-07. Il a choisi le froid, l'Ukraine et les motos comme cas de référence.

Ce que TRI1 a laissé ouvert (§4, §8) :
- B retient trop : 18 articles sur 84 ne répondent pas sur ces trois questions (précision 78,6 %), et 67 % seulement sur les motos.
- Un effet de lot : dans un lot de l'Ukraine pauvre en articles sur le sujet, 9 articles sont retenus avec la même formule.
- Des liens inventés : Novaïa Gazeta devient « opposé à la Russie en Ukraine ».
- L'instabilité : l'article bulgare retenu est au rang 93 au banc et au rang 28 à l'essai réel ; le brief du froid a retenu la raclette et le mouron du jardin, que le banc n'avait pas retenus.

TRI2 essaie deux réponses à ces défauts, sans toucher au produit.

## 2. Critères de réussite

Mesurés sur les 3 questions de référence ensemble, sans les articles sans résumé (la règle du produit les met en « à vérifier »). R, T et H sont ceux de TRI1 (§3). Chaque critère marqué « par passage » doit tenir sur **les deux** passages.

| Critère | Seuil | B au banc TRI1 |
|---|---|---|
| Part des articles R jugés « traite », par passage | ≥ 85 % | 90,4 % |
| Part des articles R jugés « hors_sujet » (faux rejets), par passage | ≤ 3 % | 0 % |
| Part de R parmi les « traite » (précision), par passage | ≥ 85 % | 78,6 % |
| Précision sur chacune des 3 questions, par passage | ≥ 75 % | froid 83 %, Ukraine 81 %, motos 67 % |
| Froid : articles R jugés « traite », par passage | au moins 5 sur 6 | 5 |
| Ukraine : articles de la présidentielle bulgare jugés « traite », par passage | 0 sur 4 | 1 |
| Stabilité : parmi les articles retenus à l'un des deux passages, part retenue aux deux | ≥ 80 % | non mesurée |
| Questions de contrôle (les 4 autres de TRI1, un passage) : perte de rappel par rapport à B mesuré dans TRI2 | ≤ 5 points | |
| Questions de contrôle : précision | au moins celle de B mesuré dans TRI2 | |
| Temps de modèle sur les 3 questions de référence | ≤ 2,5 × celui de B | |

B est mesuré de nouveau dans TRI2, deux passages, pour avoir sa propre stabilité et un temps de référence pris le même jour. La colonne « B au banc TRI1 » ne sert qu'à situer les seuils.

**Succès** : une variante tient tous les critères. **Partiel** : une variante gagne au moins 6 points de précision sur B aux deux passages, avec un rappel ≥ 85 % et aucun faux rejet en plus, sans tenir tous les critères. **Échec** : aucune variante ne fait nettement mieux que B ; le tri reste une aide à la lecture, et l'auteur garde la relecture des retenus (ADR-0043 §5).

## 3. Protocole

**Environnement.** Comme TRI1. VM .252, code de `main` déployé, passerelle du produit, profil de Joël (qwen3:14b sur Ollama de son PC). Aucun build, test ni autre appel au modèle pendant la mesure. Appels un par un, 5 s de pause. Rien n'est écrit dans son instance, sauf le journal des appels de la passerelle, comme pour tout appel.

**Jeu.** Les ensembles figés de TRI1, sans changement : mêmes titres, mêmes résumés, mêmes étiquettes (`spikes/tri1/labels.csv`), recopiés dans `~/s-tri2` sur la VM.
- Référence : froid (38 articles avec résumé, dont 6 R), Ukraine (119, dont 57 R), essais de motos (64, dont 10 R).
- Contrôle : hôpitaux en Flandre (18), pertes d'emploi (52), Ahold Delhaize (30), prix de l'énergie (32).

La relecture des textes du 7 novembre ne touche pas ce jeu : le tri ne lit que le titre et les 300 premiers caractères du résumé.

**Variantes.**
- **B, le tri actuel** : le prompt `veille-2` et la question de l'auteur, par lots de 25 comme le produit.
- **D, une preuve citée** : B d'abord, puis un second jugement des seuls articles que B a mis en « traite », par lots de 10, avec un prompt qui demande si l'élément répond à la question et, si oui, de recopier mot pour mot le passage qui répond (`EVIDENCE_SYSTEM`, `spikes/tri2/tri2.py`). Le programme, pas le modèle, vérifie la citation : au moins 5 mots, présents tels quels dans le titre ou les 300 caractères de résumé envoyés, à la casse, aux accents et à la ponctuation près. Sans réponse positive ou sans citation retrouvée, l'article passe en « proche ». D ne fait donc que retirer des « traite » ; il ne met jamais rien en « hors_sujet ». L'idée : une réponse se cite, un même thème ne se cite pas, et un lien inventé ne se retrouve pas dans le texte.
- **E, des lots de 8** : B tel quel, par lots de 8 au lieu de 25, pour voir si l'effet de lot pèse sur la précision et la stabilité.

**Passages.** Chaque variante passe deux fois sur la référence, avec les mêmes lots dans le même ordre ; le second passage de D part du second passage de B. Les questions de contrôle passent une fois par variante.

**Volume.** B : 28 appels. E : 74 appels. D : un appel par tranche de 10 articles retenus par B, soit environ 26 appels si B retient comme dans TRI1. Environ 128 appels en tout. Estimation d'après TRI1 (18 appels de 25 articles en 19 min) : environ 1 h 30 de modèle, 2 h avec les pauses. Durée maximale : 4 h ; au-delà, la mesure s'arrête et ce qui manque est rapporté. Un appel pilote d'abord, pour vérifier le montage ; il compte dans le total. Un appel en erreur n'est pas refait : ses articles restent sans verdict et comptent comme non retenus.

**Suivi.** Un premier chiffre dans le fil quand la mesure a vraiment démarré, puis un état court toutes les heures environ, et tout échec signalé aussitôt.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si une variante réussit, son passage dans le tri sera proposé à Joël à part, avec son coût en temps.

## 4. Mesures

Le 2026-11-07, de 14 h 31 à 16 h 19 : 127 appels, aucun en erreur, aucun article sans verdict, 93 min de modèle. Le pilote a pris 127 s par lot de 25, contre environ 65 s dans TRI1 ; la suite a été plus rapide. D a fait 26 appels, comme prévu. Aucun écart au montage.

| Critère | Seuil | B, tri actuel (passage 1 / 2) | D, preuve citée | E, lots de 8 |
|---|---|---|---|---|
| R jugés « traite » | ≥ 85 % | ✅ 90,4 / 91,8 % | ❌ 82,2 / 76,7 % | ❌ 86,3 / 84,9 % |
| R jugés « hors_sujet » | ≤ 3 % | ✅ 2,7 / 2,7 % | ✅ 2,7 / 2,7 % | ✅ 1,4 / 0 % |
| R parmi les « traite » (précision) | ≥ 85 % | ❌ 78,6 / 82,7 % | ❌ 83,3 / 88,9 % | ❌ 75,9 / 73,8 % |
| Précision du froid | ≥ 75 % | ✅ 80 / ❌ 71 % | ✅ 100 / 100 % | ✅ 100 / ❌ 57 % |
| Précision de l'Ukraine | ≥ 75 % | ✅ 85 / 88 % | ✅ 87 / 94 % | ✅ 76 / 83 % |
| Précision des motos | ≥ 75 % | ❌ 56 / 67 % | ❌ 67 / 71 % | ❌ 67 / 53 % |
| Froid : R jugés « traite » | ≥ 5 sur 6 | ❌ 4 / ✅ 5 | ❌ 3 / 2 | ✅ 5 / ❌ 4 |
| Présidentielle bulgare jugée « traite » | 0 sur 4 | ❌ 1 / ✅ 0 | ❌ 1 / ✅ 0 | ❌ 1 / ✅ 0 |
| Stabilité des retenus | ≥ 80 % | ✅ 85,4 % | ❌ 75,3 % | ❌ 74,0 % |
| Contrôle : perte de rappel | ≤ 5 points | ✅ 0 (91,3 %) | ❌ 13 (78,3 %) | ✅ 0 (91,3 %) |
| Contrôle : précision | ≥ B (60,0 %) | ✅ 60,0 % | ✅ 75,0 % | ✅ 63,6 % |
| Temps de modèle sur la référence | ≤ 2,5 × B | ✅ 24 min | ✅ 39 min (1,6 ×) | ✅ 33 min (1,4 ×) |

Fichiers : `spikes/tri2/results/summary.txt` et `spikes/tri2/results/analyse.txt` (`spikes/tri2/analyse.py`). Les raisons du modèle restent sur la VM (`~/s-tri2/calls.jsonl`).

Relecture des erreurs :
- **Le tri actuel n'est pas stable.** Un article sur sept retenu à un passage ne l'est pas à l'autre, avec les mêmes lots, dans le même ordre. Le froid passe de 4 à 5 articles, l'article bulgare (rang 93) de 1 à 0, la raclette est retenue une fois sur deux. Le chiffre d'un seul passage, comme dans TRI1, ne suffit donc pas à juger un tri.
- **Les erreurs de « même thème » qui reviennent sont toujours les mêmes.** Retenus aux deux passages par B sans répondre : les 4 « Top 5 » de motos et le sommaire d'Enduro Magazine ; deux articles sur la fermeture de Novaïa Gazeta, un satellite russe, le récit de deux réfugiés de Marioupol ; TotalEnergies, pourtant hors sujet ; une publicité pour un chauffage connecté sur le froid. Ce ne sont pas des erreurs de hasard : le modèle prend le thème pour la réponse sur ces articles, à chaque fois.
- **Ce n'est pas un effet de taille de lot.** Les retenus à tort de l'Ukraine se concentrent sur les rangs 64 à 99, les moins proches de la question, en lots de 25 comme en lots de 8. E garde les mêmes erreurs et en ajoute d'autres (motos 19 retenus, froid 7 retenus au second passage).
- **D, la preuve citée, a un vrai effet mais il coûte de bons articles.** Quand le second jugement dit « ne répond pas », il retire surtout des articles de même thème : 11 sur 25 au premier passage, 6 sur 13 au second. Mais il cite mal : il recolle des passages avec « […] » ou réécrit un mot (Olechky, Starlink en néerlandais), et la vérification mot pour mot, fixée d'avance, rejette alors la preuve. Au second passage, 10 bons articles de l'Ukraine sont perdus ainsi. Sur le froid, il écarte « Le froid est attendu… et cela n'a rien d'exceptionnel » et le vortex polaire, dont la réponse n'est pas dans les 300 caractères envoyés. D ne retire aucun « Top 5 ».
- **Les « Top 5 » de motos pèsent sur un seul critère.** S'ils étaient comptés comme R, la précision des motos de B passerait de 56 et 67 % à 78 et 93 %. Les étiquettes ne changent pas pour autant ; TRI1 les avait déjà signalés comme discutables.

## 5. Conclusion

**Échec.** Aucune variante ne fait nettement mieux que le tri actuel. D gagne 5 et 6 points de précision mais perd le rappel (82 et 77 %) et devient instable ; E ne gagne rien. Le tri actuel lui-même ne tient pas la précision voulue, et un article retenu sur sept change d'un passage à l'autre.

Avec qwen3:14b, le titre et 300 caractères de résumé, le verdict « traite » ne sépare pas de façon fiable « répond à la question » de « même thème ». Le brief ne peut pas se fier à ce verdict seul pour choisir sa matière.

## 6. Conséquences

| Document ou choix | Conséquence | ADR |
|---|---|---|
| Tri du Reporter | Inchangé : D et E ne sont pas reprises | ADR-0044 inchangé |
| Brief depuis les « retenus » (les 20 premiers) | À soumettre à Joël : l'auteur confirme la liste avant la rédaction, au lieu de la prendre telle quelle | ADR-0043 §5 confirmé (rien n'est exclu sans l'auteur) |
| Second jugement avec preuve citée | Piste à garder : la question « répond-il ? » retire la moitié des articles de même thème. À rejouer seulement avec une vérification qui accepte les morceaux séparés par « […] », et peut-être plus de texte que 300 caractères | |
| Choix du modèle | Non mesuré : un autre modèle sur le même banc dirait si la limite vient de qwen3:14b | ADR-0027 |

Le code de `spikes/tri2/` reste un banc ; rien n'est repris dans `backend/`.

## 7. Ce que la preuve n'a pas couvert

- Les étiquettes sont celles de TRI1, écrites par un seul auteur (Claude) ; Joël peut relire `spikes/tri1/labels.csv`.
- Deux passages seulement : la stabilité est estimée sur 3 questions et environ 100 articles retenus.
- Un seul modèle, qwen3:14b. Ni un modèle plus grand ni un autre fournisseur n'ont été essayés.
- Le tri ne lit que le titre et 300 caractères de résumé ; la relecture du 7 novembre a amélioré les textes, mais le tri ne les lit pas.
- La vérification de D a été fixée avant la mesure et n'a pas été assouplie : l'effet d'une vérification par morceaux n'est pas mesuré.
- Le brief n'a pas été rédigé à partir des résultats du banc.

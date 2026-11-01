# TRI1 — Le tri du Reporter retient-il ce qui répond à la question ?

| | |
|---|---|
| Statut | Conclue : partiel |
| Durée maximale | 3 h de mesure (une heure de modèle attendue) |
| Temps passé | 2 h 30 de préparation et d'analyse (journal de temps, TRI1) ; 60 min de modèle |
| Ouverte le / conclue le | 2026-11-01 / 2026-11-01 |
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

54 appels, aucun en erreur, aucun article sans verdict ; 25 min pour A, 19 pour B, 17 pour C ; un appel a pris 359 s. Seul écart au montage prévu : `run-tri1.sh` corrigé après la fusion, sans toucher au protocole, car `/tmp` du worker est un tmpfs que `docker cp` ne voit pas (un appel par exécution de `tri1.py`, résultat sorti du conteneur à chaque fois).

| Critère | Seuil | A, tri actuel | B, la question | C, prompt strict |
|---|---|---|---|---|
| R jugés « traite » | ≥ 85 % | ✅ 86,5 % | ✅ 89,6 % | ❌ 83,3 % |
| Idem, sans l'Ukraine | ≥ 85 % | ✅ 89,7 % | ✅ 89,7 % | ✅ 87,2 % |
| R jugés « hors_sujet » | ≤ 3 % | ✅ 1,0 % | ✅ 0 % | ❌ 5,2 % |
| Idem, sans l'Ukraine | ≤ 3 % | ✅ 0 % | ✅ 0 % | ❌ 7,7 % |
| R parmi les « traite » | ≥ 75 % | ❌ 65,9 % | ❌ 73,5 % | ❌ 71,4 % |
| Idem, sans l'Ukraine | ≥ 75 % | ❌ 54,7 % | ❌ 64,8 % | ❌ 61,8 % |
| H jugés « traite » | ≤ 5 % | ✅ 4,7 % | ✅ 4,1 % | ✅ 3,6 % |
| Idem, sans l'Ukraine | ≤ 5 % | ✅ 3,8 % | ✅ 3,0 % | ✅ 3,0 % |
| Froid : R jugés « traite » | ≥ 5 sur 6 | ❌ 3 | ✅ 5 | ✅ 5 |
| Présidentielle bulgare jugée « traite » | 0 sur 4 | ❌ 2 | ❌ 1 | ❌ 2 |

Fichiers : `spikes/tri1/results/summary.txt`, `spikes/tri1/results/erreurs-B.txt`. Les raisons du modèle restent sur la VM (`~/s-tri1/calls.jsonl`).

Relecture des erreurs de B :
- **Sur 31 retenus qui ne sont pas R, 7 sont H et 24 sont T.** Plusieurs T se discutent : les 4 « Top 5 » de motos, tirés d'essais, ou « Poutine compte intensifier… ». Compter ces 5 articles comme R donnerait 77,8 % sur les 7 questions, et le critère sans l'Ukraine resterait sous 75 % (72 % avec les 4 « Top 5 »). Les seuils et les étiquettes ne changent pas pour autant.
- **Un effet de lot.** Entre les rangs 87 et 98 de l'Ukraine, dans le même lot, 9 articles sont retenus avec la même formule, « Le sujet mentionne directement… », dont TotalEnergies, un empire immobilier et les midterms. Ce lot contient peu d'articles sur le sujet.
- **Un lien inventé** : Novaïa Gazeta, « journal opposé à la Russie en Ukraine ».
- **B lit la question au mot près.** Sur l'énergie, trois articles sur des hausses sont en « proche » avec pour raison « non cet hiver ». Sur l'Ukraine, 6 articles R sont en « proche », dont 3 sur Starlink.
- **Rien de perdu en « hors_sujet »** : avec B, tous les articles R restent « traite » ou « proche ».

## 5. Conclusion

**Partiel.** Aucune variante ne tient les 6 critères. B améliore nettement la précision (65,9 % → 73,5 %) sans perdre de rappel (86,5 % → 89,6 %), et passe le froid de 3 à 5 articles sur 6. C ne fait pas mieux que B et écarte plus de bons articles : préciser le prompt ne remplace pas la question. Le verdict « traite » reste trop généreux pour décider seul de la matière d'un brief.

## 6. Conséquences

| Document ou choix | Conséquence | ADR |
|---|---|---|
| Tri du Reporter (`reporter.py`, `subject`) | À soumettre à Joël : envoyer la question de l'auteur et non les noms des concepts | ADR-0044, à compléter si accepté |
| Prompt `veille-2`, variante C | Inchangé ; C n'est pas reprise | |
| Brief depuis les « retenus » | Le brief ne doit pas se fier au seul verdict : l'auteur garde la relecture | ADR-0043 §5 confirmé (rien n'est exclu) |

Le code de `spikes/tri1/` reste un banc ; rien n'est repris dans `backend/` à cette étape.

## 7. Ce que la preuve n'a pas couvert

- Un seul auteur d'étiquettes, qui a aussi écrit la variante C : le risque de biais est réel. Joël peut relire `labels.csv`.
- Les titres et 300 caractères de résumé seulement, comme le tri du produit : un article peut répondre plus loin dans son texte.
- 7 questions, un passage par variante : ni la stabilité du modèle, ni d'autres modèles ne sont mesurés.
- La rédaction du brief à partir des articles retenus n'est pas mesurée.
- L'effet de lot n'a pas été isolé : des lots plus petits ou un autre ordre n'ont pas été essayés.
- Le prompt C donne un seul exemple, et il n'est qu'une rédaction possible parmi d'autres.

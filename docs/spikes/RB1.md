# RB1 — Banc complet du Reporter et du brief sur deux jours de veille

| | |
|---|---|
| Statut | Conclue : seuils tenus pour le tri et la validation P3, manqués pour la recherche, la rédaction et la fidélité |
| Durée maximale | 4 h de mesure (environ 2 h 30 de modèle attendues) |
| Temps passé | 3 h de préparation et d'analyse ; 45 min de modèle pour la phase 1, 30 min pour la phase 2 |
| Ouverte le / conclue le | 2026-11-08 / 2026-11-08 |
| Choix concernés | ADR-0044 (Reporter), ADR-0045, ADR-0047, TRI1, TRI2, `docs/design/MATIERE_DU_BRIEF.md` (P2, P3) |
| Commande de rejeu | `spikes/rb1/rb1_ask.py` puis `spikes/rb1/rb1_brief.py` (§3) |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Sur des articles frais, que le banc n'a jamais vus, où le parcours complet casse-t-il ? Le parcours va de la question au Reporter jusqu'au brouillon, en passant par le tri, la liste à vérifier et le brief. Et quelles corrections apportent le plus ?

Origine : Joël, 2026-11-08. Il veut un banc complet, sur les articles arrivés le 7 et le 8 novembre, pour optimiser le Reporter et la création du brief si nécessaire. Chaque problème du rapport est classé selon son origine principale : **Recherche, Tri, Validation P3, Brief, Rédaction, Fidélité des faits**, même si plusieurs composants y prennent part.

C'est un banc de diagnostic. Il ne compare pas de variantes : il mesure le produit tel qu'il est sur `main`, P2 et P3 compris (#140), déployé sur .252. Ses seuils servent à dire où le produit ne tient pas.

## 2. Critères

| Étape (origine) | Mesure | Seuil |
|---|---|---|
| Recherche | Articles R du corpus trouvés par le Reporter, sur toutes les questions | ≥ 90 % |
| Recherche | Questions où le Reporter trouve moins de la moitié des articles R | 0 |
| Recherche | Question 14 (sans réponse dans le corpus) | le Reporter ne présente aucun article comme réponse |
| Tri | Part de R parmi les « traite » (précision), premier passage | ≥ 80 % |
| Tri | Part des R trouvés jugés « traite » (rappel), premier passage | ≥ 85 % |
| Tri | Part des R trouvés jugés « hors_sujet » | ≤ 3 % |
| Tri | Stabilité : parmi les articles retenus à l'un des deux passages, part retenue aux deux | ≥ 85 % |
| Validation P3 | La liste à vérifier s'ouvre quand les « traite » contiennent un article T ou H | dans tous ces cas |
| Brief | Briefs où l'auteur doit écarter plus de 20 R faute de place | 0 |
| Rédaction | Champ « answer » juste : « yes » quand des R répondent, « partly » pour les questions 7 et 13 | ≥ 80 % des brouillons |
| Rédaction | Brouillons qui gardent, après correction, une section sur le seul contexte | 0 |
| Rédaction | Brouillons avec du texte dans une autre langue que le français, ou des caractères parasites | 0 |
| Fidélité des faits | Sur les 7 brouillons marqués `fidelity`, paragraphes contenant une erreur : fait inversé, mauvais acteur, chiffre ou lieu faux, ou fait absent des sources citées | ≤ 10 %, et aucune inversion de fait |

Chaque problème rencontré est noté avec sa question, ce qu'on voit, son origine principale (les six ci-dessus) et la correction possible.

## 3. Protocole

**Environnement.** VM .252 avec `main` déployé (`redaction-20`), passerelle du produit, profil de Joël (qwen3:14b sur l'Ollama de son PC). Aucun build, test ni autre appel au modèle pendant la mesure. Appels un par un. Tout ce que le banc crée est visible et titré « [RB1] » pour les conversations, et par la question pour les briefs. Joël peut le supprimer.

**Corpus.** Les articles collectés le 7 et le 8 novembre 2026 : 599 articles de 21 sources, dont 453 en texte complet. Chaque question est posée au Reporter avec le calendrier du 7 au 8 novembre.

**Questions et étiquettes.** Elles sont fixées d'avance dans `spikes/rb1/questions.json` : 14 questions, chacune avec sa forme et ses motifs d'étiquettes R et C, écrits d'après les titres et les résumés du corpus, avant toute mesure.

| N° | Question | Forme | R | C |
|---|---|---|---|---|
| 1 | Pourquoi des milliers d'entrepreneurs ne peuvent-ils pas activer leur numéro de TVA ? | cause | 7 | 1 |
| 2 | Que s'est-il passé à Cracovie ? | actualité | 11 | 0 |
| 3 | Qui Donald Trump veut-il comme porte-parole de la Maison Blanche ? | fait précis | 5 | 0 |
| 4 | Pourquoi le président du Paraguay a-t-il été destitué ? | cause | 6 | 0 |
| 5 | Les tests d'appareils high-tech publiés récemment | genre | 7 | 2 |
| 6 | Quels sont les résultats du Grand Prix du Qatar de MotoGP ? | actualité | 21 | 0 |
| 7 | Les prix de l'énergie vont-ils augmenter cet hiver ? | prévision | 1 | 1 |
| 8 | Que prévoit la réforme de la police fédérale ? | fait précis | 2 | 1 |
| 9 | Pourquoi Stephen Miller remplace-t-il Susie Wiles ? | cause | 3 | 1 |
| 10 | Que reproche-t-on au patron de Nvidia ? | actualité | 6 | 0 |
| 11 | Les mobilisations sociales en France | thème | 11 | 5 |
| 12 | Qui a gagné la Route du Rhum ? | fait précis | 4 | 0 |
| 13 | Le Bitcoin va-t-il retrouver son record ? | prévision, réponse partielle | 1 | 0 |
| 14 | Quelles mesures la Belgique prend-elle contre la grippe aviaire ? | sans réponse | 0 | 0 |

Les classes sont celles de la note de conception (§2) : **R** répond, **C** contexte, **T** même thème, **H** hors sujet. R et C viennent des motifs ; R l'emporte quand un titre répond aux deux. Les autres articles trouvés sont étiquetés T ou H après la phase 1, sans afficher les verdicts du tri (`ask.jsonl` est lu titres et résumés seuls).

**Phase 1, Reporter et tri** (`rb1_ask.py`, conteneur worker). Pour chaque question, une conversation « [RB1] … » : la question avec le calendrier, puis « Trie-les » deux fois. Le premier passage est celui que voit l'auteur ; le second ne sert qu'à la stabilité. La réponse du Reporter (fait, lignes) est gardée pour être jugée juste, partielle ou fausse.

**Phase 2, brief et brouillon** (`rb1_brief.py`, conteneur api). Les étiquettes jouent l'auteur dans la liste à vérifier : les R en Matière (20 au plus), les C en Contexte (3 au plus), le reste décoché. Le brief porte la question comme titre, puis son brouillon est lancé comme le bouton « Générer ». Une question sans R n'a pas de brief : l'auteur n'a rien à rédiger.

**Fidélité.** Sur les 7 brouillons marqués `fidelity` (questions 1, 2, 4, 7, 8, 9, 10), chaque paragraphe est relu contre le texte des sources qu'il cite. Les autres brouillons sont lus en entier, mais sans ce contrôle paragraphe par paragraphe.

**Volume.** Phase 1 : 14 questions, environ 2 appels pour la réponse et 2 tris de 1 à 4 appels chacun, soit environ 80 appels. Phase 2 : 13 brouillons de 1 à 2 appels, soit environ 20 appels. Environ 100 appels en tout, 2 h 30 de modèle. Durée maximale : 4 h ; au-delà, la mesure s'arrête et ce qui manque est rapporté. Un état est posté dans le fil environ toutes les heures, et tout échec aussitôt.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Les corrections sont proposées à Joël, classées par origine et par gain.

## 4. Mesures

Le 2026-11-08, de 09 h 58 à 11 h 55 : 14 questions, 26 tris, 13 brouillons, sans aucune erreur. La question 14 n'a trouvé aucun article : il n'y a donc ni tri, ni brief. Fichiers : `spikes/rb1/results/mesures.txt` (`spikes/rb1/analyse.py`) et `spikes/rb1/results/brouillons.txt`. Les données restent sur .252, dans `~/s-rb1`.

| Étape | Mesure | Seuil | Mesuré | |
|---|---|---|---|---|
| Recherche | Articles R trouvés | ≥ 90 % | 83,5 % (71 sur 85) | ❌ |
| Recherche | Questions sous la moitié des R | 0 | 1 (tests high-tech : 1 sur 7) | ❌ |
| Recherche | Question 14, sans réponse | rien présenté comme réponse | ensemble vide, « je ne trouve pas » | ✅ |
| Tri | Précision | ≥ 80 % | 96,4 % (53 sur 55) | ✅ |
| Tri | Rappel | ≥ 85 % | 74,6 % (53 sur 71) | ❌ |
| Tri | R en « hors_sujet » | ≤ 3 % | 2,8 % (2) | ✅ |
| Tri | Stabilité | ≥ 85 % | 98,2 % | ✅ |
| Validation P3 | Liste ouverte quand un retenu ne répond pas | dans tous ces cas | 2 sur 2 ; elle s'ouvre aussi 2 fois pour des R laissés en « proche » | ✅ |
| Brief | Briefs avec plus de 20 R | 0 | 0 | ✅ |
| Rédaction | Champ « answer » juste | ≥ 80 % | 55 % (6 sur 11) | ❌ |
| Rédaction | Section sur le seul contexte | 0 | 0 | ✅ |
| Rédaction | Autre langue ou caractères parasites | 0 | 1 (citation à moitié néerlandaise, question 1) | ❌ |
| Fidélité des faits | Paragraphes fautifs sur 7 brouillons | ≤ 10 %, aucune inversion | 15,8 % (6 sur 38), aucune inversion | ❌ |

Remarque sur les étiquettes : à la question 2, « La fusillade en Pologne était un acte de "terrorisme" » répond, mais les motifs fixés d'avance ne l'avaient pas prévu. Il compte donc comme un non-R retenu ; sans cela, la précision serait de 98,2 %. Les deux dépêches identiques (questions 3 et 11), montrées une seule fois par le Reporter, comptent comme manquées.

## 5. Problèmes, classés par origine principale

| # | Origine | Question | Ce qu'on voit | Correction possible | Gain |
|---|---|---|---|---|---|
| 1 | Recherche | 5, 6 | Des mots secondaires de la question deviennent des concepts exigés (« publiés », « résultats »). Les tests high-tech n'écrivent pas « publiés » : 6 tests sur 7 manquent, et l'ensemble se remplit de 43 articles sans rapport. 2 articles du MotoGP manquent pour « résultats ». | Ne pas exiger ces mots, comme les mots qui posent la question depuis #125 : participes et noms génériques (« résultats », « publiés », « récents », « nouvelles », « dernières »). Rejouer sans modèle sur les 74 questions de l'historique. | Fort |
| 2 | Recherche | 2 | « Krakau » (néerlandais) n'est pas dans les termes (Cracovie, Kraków, Cracow) : un article néerlandais manque. | Ajouter à la proposition de termes les formes néerlandaises et anglaises des noms de lieux, et les garder dans le glossaire. | Moyen |
| 3 | Recherche | 9 | Les deux noms propres sont exigés (Stephen Miller et Susie Wiles) : l'article néerlandais qui ne nomme que Miller manque. | Pour « pourquoi X remplace Y », un seul nom propre suffit. | Faible |
| 4 | Recherche | 4 | « destitué » ne trouve pas « destitution » : un article du Monde manque. | Recherche par racine des mots (configuration française du plein texte), à mesurer. | Faible |
| 5 | Tri | 6, 4, 10, 2 | Le tri est précis et stable, mais il lit la question au mot près : 9 articles du MotoGP sur 20 (pole, qualifications, guide Michelin) restent en « proche ». | Aucune urgence : la liste P3 s'ouvre et montre ces proches à l'auteur. À revoir dans TRI3. | Faible |
| 6 | Validation P3 | 6, 10 | La liste s'ouvre aussi quand tous les retenus répondent, à cause des proches. C'est utile ici, puisque des réponses s'y trouvent. | Garder le seuil de 3 proches. | — |
| 7 | Brief | 5 | Brief sur une seule source, faute de recherche (voir 1). | Rien à corriger dans le brief. | — |
| 8 | Rédaction | 2, 6, 8, 9, 10 | Le champ « answer » dit « en partie » alors que les sources répondent. Le chapô ajoute alors des réserves inutiles : « absence de consensus » sur un bilan qui a simplement évolué (Cracovie), « ne confirment pas » (Nvidia), et « sans préciser les détails des éventuelles contestations » même quand il répond « oui » (Route du Rhum). | Ne demander de réserve que si la question reste sans réponse ; garder le champ, mais n'afficher l'avertissement que pour « non ». | Moyen |
| 9 | Rédaction | 9 | Pour tenir la longueur, le brouillon empile 8 sections dont 4 répètent qu'aucune source ne dit pourquoi. | Voir 10 : ne pas exiger la longueur quand la matière manque. | Moyen |
| 10 | Fidélité des faits | 8 | Sources minces : deux résumés, environ 90 mots. Renvoyé une fois pour « trop court », le brouillon invente 3 paragraphes sur 4 : décentralisation, réactivité face aux urgences, inquiétude des agents. | Ne pas renvoyer « trop court » quand la matière est limitée ou insuffisante : garder le brouillon court avec l'avertissement de matière. | Fort |
| 11 | Fidélité des faits | 3 | Dana White devient une femme (« elle a publié… une photo la représentant ») ; la source dit « le montrant ». | Difficile à contrôler sans modèle : à laisser à la relecture, et à signaler dans le guide de relecture. | Faible |
| 12 | Fidélité des faits | 10 | « Au printemps 2026 » devient « en avril 2026 ». | Le contrôle des dates absentes des sources (U05) ne voit pas « avril » ; l'étendre aux noms de mois. | Faible |
| 13 | Fidélité des faits | 1 | Citation abîmée, à moitié traduite : « sans btw-nummer est het stilstand » au lieu de « Zonder btw-nummer is het stilstand ». | Une citation entre guillemets doit se retrouver telle quelle dans une source, ou être signalée. | Moyen |
| 14 | Fidélité des faits | 12 (réponse du Reporter) | « Qui a gagné ? » : la conclusion est juste (Tom Laperche), mais la réponse aligne des chiffres sans rapport (500 km, 420 milles…) et les dit « divergents ». | Pour une question « qui », ne pas extraire de chiffres ni calculer leur concordance. | Moyen |
| 15 | Rédaction | 11 | Le modèle écrit les identifiants des sources. Le nettoyage les remplace par « comme indiqué dans LeMonde.fr (en continu) », répété 4 fois. | Nom d'éditeur sans « (en continu) », et une seule attribution par paragraphe. | Faible |

## 6. Conclusion

**Ce qui tient.** Le tri est désormais précis (96 %) et stable (98 %) : sur ce corpus, le problème du « même thème » de TRI2 ne réapparaît presque pas. P3 s'ouvre quand il faut. Le contexte reste à sa place. La question sans réponse donne « je ne trouve pas ». La plupart des faits des brouillons se retrouvent dans leurs sources : la Route du Rhum, le Paraguay, Nvidia et l'énergie sont justes et détaillés.

**Ce qui casse, par gain :**
1. **La recherche exige des mots secondaires de la question** (n° 1). C'est la plus grosse perte de matière.
2. **La règle « trop court » pousse à inventer quand la matière est mince** (n° 10). C'est la seule faute grave de fidélité du banc.
3. **Le champ « answer » rend le chapô trop prudent** (n° 8). Il dit « en partie » 5 fois sur 11 à tort.
4. Ensuite, des corrections plus petites : citations (n° 13), réponse « qui » du Reporter (n° 14), noms néerlandais (n° 2).

## 7. Ce que la preuve n'a pas couvert

- Une seule personne a écrit les étiquettes (Claude), d'après les titres. Un article qui répond a échappé aux motifs (question 2).
- La fidélité est relue sur 7 brouillons. Les autres sont lus en entier, sans contrôle paragraphe par paragraphe.
- Un seul modèle, qwen3:14b, et un seul passage de rédaction par question.
- Deux jours d'actualité surtout belge et française, avec des questions écrites par Claude d'après les titres du corpus.

## 8. Après la conclusion : corrections 1 et 10 (2026-11-08)

Ordre choisi par Joël : d'abord la recherche (les mots secondaires ne doivent être que des indices), puis la fidélité quand la matière est mince. Le champ « answer » passe après.

- **Correction 1 (50d3332).** « publiés », « parus », « résultats », « récemment » et « présentés » ne nomment plus de concept exigé. Ils restent dans le sens de la question, qui classe les articles.
  - Rejeu sans modèle des 134 premières questions du Reporter (`spikes/rb1/replay.py`, `results/rejeu-recherche.txt`) : 3 changent. Tests high-tech : 1 → 7 articles R sur 7, mais l'ensemble passe de 51 à 109 articles. MotoGP Qatar : 21 → 22.
  - En réel, la même question a trouvé **0 article** (conversation « [RB1-bis] Les tests… »). Le modèle a découpé la question autrement : trois concepts exigés, « tests », « high-tech » et « appareils, récents… ». Aucun article ne les tient tous, et le sens n'est consulté que si les mots trouvent quelque chose. Les mots secondaires ne sont donc qu'une forme du problème. Le fond : tous les concepts proposés par le modèle sont exigés ensemble.
- **Correction 10 (50d3332).** Un brouillon n'est plus renvoyé pour « trop court » quand la matière a fixé sa longueur. En réel, la réforme de la police (deux résumés) donne 3 paragraphes courts, en un seul appel, sans les inventions du banc. Il reste une extrapolation légère : « certains membres de la police expriment des doutes ».
- **Vu en passant (Fidélité des faits).** Le nouveau brouillon du MotoGP place Jorge Martín deuxième du sprint, alors que le premier le plaçait troisième derrière Di Giannantonio. À vérifier contre les sources avant toute conclusion.

Suite proposée à Joël : quand les concepts exigés ensemble ne trouvent rien, relâcher la recherche sans modèle, en essayant d'abord sans le concept le moins spécifique. Il ne faut jamais relâcher un nom propre ni le sujet : la question de la grippe aviaire doit continuer à ne rien trouver. Cette règle doit être mesurée avant d'entrer dans le produit : rejeu sur les 134 questions et sur RB1.

# RB1 — Banc complet du Reporter et du brief sur deux jours de veille

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 4 h de mesure (environ 2 h 30 de modèle attendues) |
| Temps passé | |
| Ouverte le / conclue le | 2026-11-08 / |
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

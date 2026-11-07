# Ce qui doit être retenu pour rédiger

| | |
|---|---|
| Statut | Définition validée par Joël le 2026-11-07 ; P2 et P3 construites, à essayer en usage réel |
| Date | 2026-11-07 |
| Origine | TRI1 et TRI2 (`docs/spikes/TRI1.md`, `docs/spikes/TRI2.md`) ; demande de Joël du 2026-11-07 |
| Choix concernés | ADR-0043 §5 et §10, ADR-0044 (Reporter), ADR-0041 (évaluateur de matière) |

Joël, 2026-11-07 : le résultat principal de TRI2 n'est pas une question de modèle, mais de définition de ce qui doit être retenu pour rédiger. On reste sur les modèles locaux tant que les pistes de conception du workflow ne sont pas épuisées.

Cette note ne change rien au produit. Elle propose une définition, regarde où les erreurs passent aujourd'hui et ordonne des pistes. Chiffre marqué *(après coup)* : calculé sur les données de TRI2 après sa conclusion. C'est une piste, pas une preuve, tant qu'un banc fixé d'avance ne l'a pas confirmé.

## 1. Ce que TRI2 a montré

**Deux sortes d'erreurs, qui ne se corrigent pas de la même façon.**

- **Des erreurs de hasard.** Entre deux passages identiques, un article retenu sur sept change de verdict. *(Après coup)* : les 13 articles retenus à un seul des deux passages ne répondent que 3 fois. Ceux retenus aux deux passages répondent dans 85,5 % des cas (65 sur 76), pour un rappel de 89 %. Le seuil de précision de TRI2 est tenu, alors qu'aucune variante ne le tenait.
- **Des erreurs systématiques.** Certains articles sont retenus à chaque passage, quel que soit le lot. Le double passage ne les retire pas : les motos restent à 10 sur 15.

**Les erreurs systématiques forment quatre familles.**

| Famille | Exemples dans TRI2 | Ce qui trompe le tri |
|---|---|---|
| Format voisin | 4 « Top 5 » de motos, sommaire d'Enduro Magazine | La question porte sur un genre (des essais). Le classement est tiré d'essais et en parle, sans en être un. |
| Contexte du sujet | Novaïa Gazeta (deux articles), satellite Cosmos, Poutine qui veut intensifier la guerre, réfugiés de Marioupol, drones en Bulgarie | Le sujet est l'arrière-plan de l'article, pas son objet. |
| Cause partagée vers un autre sujet | TotalEnergies (bénéfices liés aux conflits), inflation « due aux guerres », Olechky retenu pour les prix de l'énergie et les pertes d'emploi | Le sujet est cité comme cause de tout autre chose. |
| Pratique et consommation | Chauffage connecté en promotion, raclette, mouron du jardin | Le mot du thème (températures) est là, mais pas la réponse (pourquoi il fera froid). |

**Ce que la question « répond-il ? » (variante D) change.** Posée seule, elle écarte bien le contexte, la cause partagée et la pratique : Novaïa Gazeta, TotalEnergies, chauffage, Zontes et Kawasaki passent en « ne répond pas ». Elle échoue sur le format voisin : pour les « Top 5 », le modèle cite « Sur l'ensemble des essais réalisés cette année… » comme preuve. Sa notion de réponse reste celle des mots.

## 2. Définition proposée

**Matière de rédaction.** Un article est matière s'il apporte au moins un élément que le brief peut affirmer pour répondre à la question, en citant sa source : un fait, un chiffre, une cause, une déclaration, un résultat d'essai. Cet élément doit porter sur l'objet de la question et sur la période demandée.

Quatre classes, et non trois verdicts :

| Classe | Définition | Place dans le brief |
|---|---|---|
| **Répond** | Apporte un élément de réponse, au sens ci-dessus | Matière : peut porter une section |
| **Contexte** | Aide à comprendre la réponse sans en être une (arrière-plan, antécédent) | Une phrase au plus, jamais une section, jamais un fait central |
| **Même thème** | Partage le sujet, sans rien que le brief puisse affirmer pour répondre | Hors du brief ; reste visible dans le Reporter |
| **Hors sujet** | Sans rapport, ou lien par un mot seulement | Hors du brief |

**Ce qui compte comme réponse dépend de la forme de la question.** C'est ce qui manque aujourd'hui au tri.

| Forme de la question | Exemple du banc | Répond | Ne répond pas |
|---|---|---|---|
| Cause (« Pourquoi… ? ») | Froid | Donne une cause ou un mécanisme (anticyclone, vent du nord, vortex polaire) | Annonce le froid sans dire pourquoi ; conseils de saison |
| Actualité (« dernières actualités sur X ») | Ukraine | Un événement dont X est l'objet, dans la période | X comme arrière-plan ou comme cause d'autre chose |
| Genre (« les essais de… ») | Motos | Un article de ce genre | Classements, sommaires, nouveautés annoncées sans essai |
| Fait précis (« Que rachète… ? ») | Ahold Delhaize | Énonce le fait | Parle de l'entreprise sans ce fait |
| Prévision (« risquent-ils de… ? ») | Prix de l'énergie | Une prévision, un chiffre attendu, une décision qui le fixe | Des aides, des hausses passées sans lien avec la période |

## 3. Le parcours actuel, et où les erreurs passent

1. Le Reporter trouve l'ensemble (recherche, #125).
2. Le tri juge chaque article par lots de 25, sur le titre et 300 caractères de résumé : traite, proche ou hors sujet (B, #127).
3. Trois boutons mènent au brief (`ConversationPage.tsx`, `BRIEF_MAX = 20`) :
   - « Préparer un brief avec les N articles retenus » : les 20 premiers « traite », tels quels ;
   - une sélection cochée à la main ;
   - tous les articles du thème.
4. L'évaluateur de matière (A1a) juge l'ensemble du brief, puis la rédaction écrit à partir de tous les éléments, sans hiérarchie entre eux.

**Où les erreurs passent :**
- Au bouton des retenus. Le verdict d'un seul passage décide seul, et deux clics sur la même conversation peuvent donner deux briefs différents.
- À la rédaction. Tout élément du brief pèse autant qu'un autre. Un article de contexte peut ainsi devenir une section, comme la Bulgarie dans un brouillon de l'Ukraine, ou servir de remplissage, comme la raclette et le mouron dans le froid.
- Dans l'évaluateur. Il compte les sources sans savoir lesquelles répondent : un brief rempli de « même thème » paraît riche.

## 4. Pistes, avec des modèles locaux seulement

| Piste | Ce qu'elle fait | Erreurs visées | Coût | Modèle |
|---|---|---|---|---|
| **P1. Critère de réponse explicite** | Le Reporter écrit, pour la question, ce qui compte comme réponse, d'après sa forme (tableau du §2). L'auteur le voit et peut le corriger, comme les termes de l'Assistant. Le tri reçoit ce critère avec la question. | Systématiques, surtout le format voisin | Une ligne de plus dans l'écran ; un banc | Aucun pour la forme si une règle suffit ; sinon un appel |
| **P2. Deux niveaux dans le brief** | Les éléments du brief sont « Matière » ou « Contexte ». La rédaction ne fait de sections qu'avec la matière, et une phrase au plus par élément de contexte. | Bulgarie en section, remplissage | Prompt de rédaction et un champ par élément | Aucun de plus |
| **P3. L'auteur confirme la liste** | Le bouton des retenus ouvre une liste pré-cochée, avec la raison du modèle. L'auteur décoche avant la rédaction ; rien ne part sans cette étape. | Toutes, en dernier recours | Le temps de l'auteur, environ 20 lignes à lire | Aucun |
| **P4. Double passage du tri** | Le tri passe deux fois. Un article retenu aux deux passages est pré-coché ; un article retenu une seule fois est marqué « incertain » et laissé décoché. | Hasard | 2 × le temps du tri (24 → 48 min sur le banc) | Le même |
| **P5. Règles pour des familles reconnaissables** | Sans modèle : « Top N », « PRESSE – », sommaires et contenu promotionnel ne sont jamais pré-cochés. | Format voisin, pratique | Faible | Aucun |

Remarques :
- **P3 se combine avec les autres.** P1, P4 et P5 servent surtout à rendre la pré-coche plus juste, pour que la confirmation soit rapide. P3 seule fait porter tout le tri à l'auteur.
- **P4 est le seul chiffre déjà encourageant, mais il est calculé après coup.** Il doit passer un banc fixé d'avance, sur d'autres questions que les trois de référence. Il ne corrige pas les motos, et le froid y reste à 4 articles sur 6.
- **P5 risque d'être taillée sur les erreurs de TRI2.** Il faut la mesurer sur des questions nouvelles, et ne l'utiliser que pour ne pas pré-cocher, jamais pour exclure (ADR-0043 §5).
- **La citation de D peut servir autrement.** Montrée à l'auteur dans la liste de P3 (« ce passage répond »), elle aide à la lecture au lieu de filtrer, sans le risque d'une vérification trop stricte.

## 5. Ordre proposé

1. **P2 et P3 d'abord.** Elles touchent le parcours, pas le modèle : elles corrigent les briefs tout de suite, quel que soit le tri. On les essaie en usage réel sur le froid et l'Ukraine.
2. **Banc TRI3, en local.** Il compare B, P1 (le critère de réponse), P4 (le double passage) et P1 avec P4. Il reprend le jeu de TRI2 et ajoute des questions nouvelles, avec des étiquettes écrites avant toute mesure. Seuils fixés d'avance, comme toujours.
3. **P5 seulement si TRI3 laisse le format voisin.** Elle est mesurée sur les questions nouvelles.
4. **Un autre modèle**, local ou payant, seulement si ces pistes ne suffisent pas.

## 6. Questions pour Joël

- La définition du §2 te convient-elle, en particulier la classe « Contexte » distincte de « Même thème » ?
- Pour P3 : confirmer la liste doit-il être obligatoire avant chaque rédaction, ou seulement proposé quand le tri est incertain ?
- Pour les motos : les « Top 5 », tirés d'essais, sont-ils pour toi de la matière ou du même thème ? TRI1 les a étiquetés « même thème », mais c'est ta définition qui compte.

## 7. Décisions de Joël (2026-11-07)

- La définition en quatre classes convient.
- Les « Top 5 » de motos sont du **même thème** : ils utilisent des essais sans en être.
- La confirmation de la liste n'est pas obligatoire : elle intervient quand le tri est incertain ou que plusieurs articles sont « proches » plutôt que clairement répondants.
- Ordre : P2 et P3, puis TRI3.

## 8. Ce qui est construit (P2 et P3)

- **P2.** Chaque élément d'un brief est « Matière » ou « Contexte » (migration 0046, `brief_items.context`). Un brief garde au moins un élément de matière. Le nombre de sources, les mots de la matière et la longueur possible ne comptent que la matière ; l'évaluateur de matière ne reçoit qu'elle. Le prompt `redaction-19` marque le contexte (« context only ») : une phrase au plus, dans un paragraphe qui cite aussi la matière, jamais une section. Une réponse qui fait une section sur le seul contexte, ou qui cite un contexte dans plusieurs paragraphes, est renvoyée une fois au modèle. Un contexte non utilisé n'est pas un avertissement.
- **P3.** Dans le Reporter, après un tri, « Préparer un brief avec les articles retenus » ouvre une liste à vérifier quand au moins 3 articles sont « proches » (ou sans verdict), ou quand le tri en retient plus de 20. Les retenus y sont cochés en « Matière », les proches décochés ; un proche coché arrive en « Contexte ». Sinon, le bouton part comme avant.
- Le seuil de 3 proches est un choix de départ, à revoir après l'essai réel.

## 9. Premier essai (2026-11-07)

Sur .252, la liste à vérifier s'ouvre pour le froid (8 retenus, 14 proches) et l'Ukraine (65 retenus, 19 proches). Dans les deux brouillons « [Essai P2] », le contexte n'est pas utilisé et la Bulgarie n'a plus de section. Joël : P3 est plus convaincante que prévu ; on voit tout de suite ce qui est matière (vortex polaire, froid attendu, gelées, blocage) et ce qui ne l'est pas (raclette, chauffage, jardinage). Le seuil de 3 proches est gardé ; le parcours est observé en usage réel avant TRI3.

## 10. Dix essais [TEST] (2026-11-07 et 08)

À la demande de Joël, 10 questions nouvelles sur .252 avec qwen3:14b. Chacune a donné une conversation « [TEST] … » du Reporter (question, puis « Trie-les »), puis un brief « [TEST] … » et son brouillon. Claude a joué l'auteur dans la liste à vérifier, selon la définition du §2. Ce choix d'auteur est une simulation, pas celui de Joël. Scripts et sorties : `~/s-p2/` sur .252 (`test_p3_ask.py`, `test_p3_draft.py`, `choices.json`).

| Question | Forme | Ensemble | Retenus / proches | Liste à vérifier | Brouillon |
|---|---|---|---|---|---|
| Pourquoi y a-t-il une mobilisation sociale en Belgique ? | cause | 197 | 73 / 25 | oui | répond (austérité, enseignement, minerval) ; contexte dans un paragraphe |
| Dernières nouvelles du GP du Brésil de F1 | actualité | 48 | 25 / 2 | oui (> 20) | répond ; contexte dans un paragraphe |
| Les essais de smartphones récents | genre | 63 | 7 / 20 | oui | ne parle que de l'iPhone Duo : 2 essais sur 5 non utilisés |
| Qui est Pierre Louvrier ? | fait | 28 | 1 / 5 | oui | répond, mince (une source) |
| Les prix de l'immobilier vont-ils baisser ? | prévision | 33 | 9 / 8 | oui | ne répond pas (aucune prévision dans les sources, sans le dire) ; contexte dans 5 paragraphes et une section |
| Pourquoi Musk accuse-t-il l'Ukraine (Starlink) ? | cause | 18 | 3 / 4 | oui | répond ; contexte dans 5 paragraphes et une section |
| La suppression des provinces en Wallonie | thème | 20 | 7 / 0 | non | répond ; contexte non utilisé |
| Nouveautés motos du salon de Milan | genre | 60 | 26 / 7 | oui (> 20) | répond ; une erreur : DesertX attribuée à CF Moto (Ducati) |
| Que reprochent les CPAS à la circulaire Van Bossuyt ? | fait | 7 | 6 / 0 | non | répond |
| Dernières décisions de Donald Trump | actualité | 104 | 29 / 19 | oui | répond ; contexte dans un paragraphe |

Constats :
- **Le tri retient encore beaucoup de « même thème »**, comme TRI2 l'avait montré. Pour la mobilisation : les marches Adeps, les rassemblements de voitures, Skeyes. Pour la F1 : Haas, Cadillac, Hamilton contre Leclerc. La liste à vérifier est le seul endroit où ils sortent.
- **La liste s'ouvre 8 fois sur 10.** Elle est courte et utile quand le tri retient peu (Louvrier, Starlink, immobilier). Elle est lourde quand plus de 20 articles sont retenus : 98 lignes pour la mobilisation, 48 pour Trump.
- **Défaut de P2, corrigé le 2026-11-08 (e4bed7d).** La règle du contexte s'appliquait aussi à la réponse corrigée : 3 brouillons sur 10 avaient échoué. Elle n'est plus renvoyée qu'une fois, comme les autres règles, et les 3 brouillons ont été refaits.
- **Le contexte reste mal tenu quand la matière est mince.** Sur l'immobilier et sur Starlink, après la correction, le contexte porte encore une section et plusieurs paragraphes. Le prompt seul ne suffit pas.
- **Hors P2 :** une erreur de fait (DesertX), deux caractères parasites (« Lepo味 », relevé par le contrôle) et une question de prévision à laquelle le brouillon ne répond pas, sans dire que les sources ne répondent pas.

Pistes, sans modèle :
1. Envoyer le contexte en court (titre et début du résumé) au lieu de son texte entier : la rédaction ne peut plus en tirer une section.
2. Dans la liste à vérifier, quand plus de 20 articles sont retenus, ne cocher que les 20 premiers et replier les proches.
3. Pour une question de prévision ou de cause, dire dans le brouillon quand aucune source n'y répond.

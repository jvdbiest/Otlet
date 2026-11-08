# REL2 — L'aide à la relecture au niveau de la phrase, et le signal « peu soutenu »

| | |
|---|---|
| Statut | Conclue : partiel (aide à la phrase réussie, signal « peu soutenu » sous le seuil) |
| Durée maximale | 2 h (sans modèle) |
| Temps passé | 1 h 30 de préparation, de mesure et de relecture ; aucun appel au modèle |
| Ouverte le / conclue le | 2026-11-08 / 2026-11-08 |
| Choix concernés | REL1, FID1, U05, `docs/design/CAS_DE_REFERENCE.md` |
| Commande de rejeu | `python3 spikes/rel2/rel2.py measure <dossier>`, avec `rel1.py` à côté et le `frozen.json` de REL1 |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

L'auteur désigne une phrase du brouillon, et Otlet montre les phrases des sources qui partagent ses noms, ses chiffres et ses mots. Ces phrases permettent-elles de vérifier ou de contredire la phrase, même quand elle contient une erreur ? Et un paragraphe peu soutenu par ses sources est-il un bon signal des endroits où le modèle extrapole ?

Origine : Joël, 2026-11-08, après REL1. Au niveau du paragraphe, l'aide est trop grossière, car un paragraphe mêle plusieurs faits. Au niveau de la phrase, elle semblait retrouver la bonne phrase de source, mais ce chiffre a été obtenu après coup, sur les mêmes cas. L'objectif est de vérifier vite un passage suspect, pas de détecter automatiquement.

## 2. Critères de réussite

| Critère | Seuil |
|---|---|
| **Erreurs nouvelles** (permutations, §3) : la phrase de source qui soutenait la phrase avant l'erreur est encore montrée après | ≥ 80 % de 60 erreurs au plus |
| Les 5 erreurs connues de REL1, avec des motifs élargis : phrase révélatrice montrée | ≥ 4 sur 5 |
| Phrases du brouillon sans aucune phrase de source montrée | ≤ 20 % |
| Signal « peu soutenu » : les deux paragraphes inventés de la police (RB1, question 8) sont dans le dixième le moins soutenu | les deux |
| Signal « peu soutenu » : parmi les autres paragraphes marqués, ceux qui extrapolent ou disent plus que leurs sources, à la relecture | ≥ 50 % |

Les 5 erreurs connues ne sont plus inédites : REL1 a montré leurs phrases. Elles servent de vérification, et le premier critère, sur des erreurs que la mesure n'a jamais vues, compte le plus.

**Succès** : les 5 critères. **Partiel** : les erreurs nouvelles et les erreurs connues sont tenues, mais le signal « peu soutenu » ne l'est pas. Il faudrait alors faire l'aide à la phrase sans ce signal. **Échec** : moins de 80 % sur les erreurs nouvelles.

## 3. Protocole

**Corpus.** Le `frozen.json` de REL1, inchangé : 32 brouillons, leurs paragraphes, les sources citées par chaque paragraphe et leur texte. Aucun appel au modèle.

**L'aide à la phrase.** Pour chaque phrase d'au moins 40 caractères, on prend les phrases des sources que son paragraphe cite, avec le score de REL1 : mots partagés pondérés par leur rareté, plus 3 par nom partagé et 3 par chiffre partagé. On en montre au plus 3, parmi celles qui atteignent la moitié du meilleur score.

**Erreurs nouvelles, les permutations** (`perturbed`, `spikes/rel2/rel2.py`). Pour chaque phrase qui reçoit au moins une phrase de source, on retient la première phrase montrée, celle qui la soutient. On écrit ensuite dans la phrase du brouillon, une à la fois, les erreurs qu'un modèle fait :
- un chiffre augmenté de 1 ;
- un mois remplacé par le suivant ;
- un rang remplacé par le suivant (« troisième » devient « quatrième ») ;
- « il » remplacé par « elle » ;
- deux noms propres échangés.

On s'arrête à 60 erreurs, dans l'ordre du corpus. L'erreur est montrable si la phrase de source qui soutenait la phrase d'origine est encore parmi les 3 phrases montrées pour la phrase fautive : l'auteur a alors sous les yeux la phrase qui la contredit.

**Erreurs connues.** Les 5 cas de REL1. Les motifs de leurs phrases révélatrices sont élargis avant la mesure, par exemple « deuxième place qui lui a échappé » pour Martín. On applique l'aide à la phrase fautive, pas à son paragraphe.

**Signal « peu soutenu ».** Pour chaque paragraphe, on prend le meilleur score de ses phrases. Le dixième des paragraphes au score le plus bas est marqué « à vérifier ». On regarde si les deux paragraphes inventés de la police y sont, et on relit les autres paragraphes marqués contre leurs sources (`rel2.txt`).

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si l'aide réussit, son écran sera proposé à Joël à part : le clic ou le survol d'une phrase, et la marque « à vérifier ».

## 4. Mesures

Le 2026-11-08 au soir, sur le `frozen.json` de REL1 : 700 phrases et 232 paragraphes, sans aucun appel au modèle. Fichier : `spikes/rel2/results/rel2.txt`.

| Critère | Seuil | Mesuré | |
|---|---|---|---|
| Erreurs nouvelles : phrase qui soutenait encore montrée | ≥ 80 % | **98 %** (59 sur 60) | ✅ |
| Erreurs connues révélées | ≥ 4 sur 5 | 4 sur 5 : Martín au rang 1, Zarco au rang 3, Dana White au rang 1, la citation au rang 1 ; « avril » non révélé | ✅ |
| Phrases sans phrase de source montrée | ≤ 20 % | 2 % (12 sur 700) | ✅ |
| Les deux paragraphes inventés de la police marqués « peu soutenus » | les deux | les deux | ✅ |
| Autres paragraphes marqués qui extrapolent, à la relecture | ≥ 50 % | 43 % (9 sur 21) | ❌ |

**Répartition des erreurs injectées.** 34 échanges de noms, 14 chiffres, 10 mois, 2 rangs, aucun « il » devenu « elle » : les 60 premières erreurs du corpus. Les rangs et les pronoms sont donc peu couverts. L'unique erreur manquée est un mois.

**Le signal « peu soutenu » à la relecture.** 23 paragraphes sont marqués, le dixième le moins soutenu, sous un score de 17,2. Parmi les 21 autres que les deux de la police :
- **9 extrapolent ou déforment.** Deux viennent du nouveau brouillon de la police (« certains membres de la police expriment des doutes », « transfert de responsabilités »). Nvidia : un fait de la source attribué aux services de renseignement. Route du Rhum : Davy Beaudart salue en réalité Laperche. Landen : des « communautés congolaises ou africaines » et des « défis pour les écoles » absents des sources. Cracovie : l'« absence de consensus ». Les manifestations : des « conditions de travail des enseignants » quand la source parle du secteur hospitalier. La citation à moitié traduite. Le suspect de Cracovie : une « analyse de ses réseaux sociaux » absente des sources.
- **4 sont des chapôs ou des phrases sur les sources elles-mêmes** (« Les sources ne répondent pas directement… », « Aucune source ne fournit… »), peu soutenus par nature.
- **8 sont justes.**

Trois de ces extrapolations n'avaient été vues par aucune relecture précédente (Landen, Beaudart, les enseignants).

## 5. Conclusion

**Partiel**, au sens fixé d'avance : l'aide à la phrase tient tous ses critères, le signal « peu soutenu » non.
- **L'aide à la phrase marche.** Sur des erreurs qu'elle n'a jamais vues, la phrase de source qui contredit l'erreur reste affichée 59 fois sur 60, et 4 des 5 erreurs réelles sont révélées. On peut vérifier une phrase suspecte d'un coup d'œil.
- **Le signal « peu soutenu » est utile, mais bruité.** Il attrape les deux paragraphes inventés et trouve trois extrapolations que personne n'avait vues. Il ne passe pas le seuil : 43 % au lieu de 50 %. Quatre des faux signaux sont des chapôs sur les sources ; les écarter donnerait 9 sur 17 (53 %), mais c'est une lecture après coup.

## 6. Conséquences

| Document ou choix | Conséquence |
|---|---|
| Aide à la relecture à la phrase | À proposer à Joël pour le produit : un clic ou un survol sur une phrase du brouillon montre au plus 3 phrases des sources citées, avec les noms et chiffres partagés mis en évidence. Sans modèle |
| Signal « peu soutenu » | Pas dans le produit tel quel. Piste : écarter les phrases qui parlent des sources elles-mêmes, puis mesurer de nouveau sur des brouillons nouveaux |
| Cas de référence | Landen (communautés, écoles), Beaudart et les enseignants rejoignent `docs/design/CAS_DE_REFERENCE.md` |

## 7. Ce que la preuve n'a pas couvert

- Les erreurs injectées sont surtout des échanges de noms et des chiffres : 2 rangs et aucun pronom.
- Montrer la phrase qui contredit ne garantit pas que l'auteur voit l'erreur : le temps de vérification réel n'est pas mesuré.
- Le signal « peu soutenu » a été relu par Claude seul, sur un seuil relatif (le dixième le plus bas) ; sa valeur sur d'autres brouillons reste à voir.

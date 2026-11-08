# REL2 — L'aide à la relecture au niveau de la phrase, et le signal « peu soutenu »

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 2 h (sans modèle) |
| Temps passé | |
| Ouverte le / conclue le | 2026-11-08 / |
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

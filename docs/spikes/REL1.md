# REL1 — Une aide à la relecture : les phrases des sources sous chaque paragraphe

| | |
|---|---|
| Statut | Ouverte |
| Durée maximale | 2 h (sans modèle) |
| Temps passé | |
| Ouverte le / conclue le | 2026-11-08 / |
| Choix concernés | FID1, U05, `docs/design/CAS_DE_REFERENCE.md`, `docs/design/MATIERE_DU_BRIEF.md` |
| Commande de rejeu | `python3 spikes/rel1/rel1.py freeze` (conteneur worker), puis `python3 spikes/rel1/rel1.py measure <dossier>` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Si l'on montre, sous chaque paragraphe d'un brouillon, les phrases des sources citées qui partagent le plus avec lui (noms, chiffres, mots rares), l'auteur voit-il la phrase qui révèle une erreur ? Et sans avoir trop à lire ?

Origine : Joël, 2026-11-08, après l'échec de FID1. Plutôt qu'un contrôle qui décide, donner plus de contexte à l'auteur, comme P3, Matière et Contexte, ou les termes qui ne se rencontrent pas. Un contrôle par le modèle ne serait envisagé qu'ensuite.

## 2. Critères de réussite

| Critère | Seuil |
|---|---|
| Erreurs connues dont la phrase révélatrice est montrée sous le paragraphe fautif (5 cas, §3) | ≥ 4 sur 5 |
| Phrases montrées par paragraphe, en moyenne, sur tous les brouillons | ≤ 4 |
| Paragraphes sans aucune phrase montrée, sur tous les brouillons | ≤ 20 % |

Les paragraphes inventés de la police (RB1, question 8) sont rapportés à part, sans seuil : ce que l'aide montre quand les sources ne disent pas ce que dit le paragraphe.

**Succès** : les 3 critères. **Partiel** : le premier critère tenu, mais l'aide montre trop ou trop peu. **Échec** : moins de 4 erreurs révélées.

## 3. Protocole

**Corpus figé.** Comme pour FID1 : toutes les versions écrites par le modèle des briefs créés depuis le 2026-11-07, chacune avec ses paragraphes, les sources que chaque paragraphe cite et le texte de ces sources. `rel1.py freeze` les lit à travers la sécurité de l'espace de travail, en lecture seule. Aucun appel au modèle.

**L'aide, sans modèle.** Pour un paragraphe, on prend les phrases des sources qu'il cite ; pour le chapô, qui ne cite rien, toutes les sources. Chaque phrase reçoit un score : les mots partagés avec le paragraphe, pondérés par leur rareté dans les sources du corpus, plus 3 par nom à majuscule partagé et 3 par chiffre partagé. On montre au plus 5 phrases, les meilleures, et seulement celles qui atteignent la moitié du meilleur score. Rien de partagé, rien de montré.

**Erreurs connues** (fixées d'avance dans `CASES`, `spikes/rel1/rel1.py`). Pour chaque cas : le brief, un motif qui trouve le paragraphe fautif, et un motif qui trouve la phrase de source qui révèle l'erreur.

| Cas | Brief | Paragraphe fautif | Phrase qui révèle l'erreur |
|---|---|---|---|
| MotoGP : Martín deuxième au lieu de troisième | 0793d3f8 | « terminant deuxième » | « Il termine donc deuxième, devant Martin » ou « devance Jorge Martin dans le dernier tour » |
| MotoGP : 281 points donnés à Zarco | 0793d3f8 | « Johann Zarco, cinquième » | la phrase qui donne 281 points à Ogura |
| Dana White devenu « elle » | 83ba4b1f | « photo la représentant » | « photo le montrant » |
| « Au printemps » devenu « en avril » | c22f90fc | « avril 2026 » | « Au printemps 2026 » |
| Citation à moitié traduite | dcbdf698 | « btw-nummer est het » | « Zonder btw-nummer is het stilstand » |

Une erreur est révélée quand la phrase qui la révèle figure parmi les phrases montrées sous le paragraphe fautif.

**Ce qui est rapporté.** Le nombre de phrases montrées par paragraphe et la part des paragraphes sans phrase, sur tous les brouillons. Pour chaque cas, le rang de la phrase révélatrice. Et pour la relecture, ce que l'aide montre sous chaque paragraphe fautif et sous les paragraphes inventés de la police (`shown.txt`).

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si l'aide réussit, son affichage (sous le paragraphe, ou au survol de ses références [n]) sera proposé à Joël à part.

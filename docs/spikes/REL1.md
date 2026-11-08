# REL1 — Une aide à la relecture : les phrases des sources sous chaque paragraphe

| | |
|---|---|
| Statut | Conclue : échec selon les seuils ; à la lecture, piste utile au niveau de la phrase |
| Durée maximale | 2 h (sans modèle) |
| Temps passé | 1 h 30 de préparation, de mesure et de lecture ; aucun appel au modèle |
| Ouverte le / conclue le | 2026-11-08 / 2026-11-08 |
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

## 4. Mesures

Le 2026-11-08 au soir, 32 brouillons et 232 paragraphes, sans aucun appel au modèle. Fichier : `spikes/rel1/results/shown.txt`, avec ce que l'aide montre sous chaque paragraphe fautif.

| Critère | Seuil | Mesuré | |
|---|---|---|---|
| Erreurs connues révélées | ≥ 4 sur 5 | 2 sur 5 (Dana White au rang 1, citation au rang 3) | ❌ |
| Phrases montrées par paragraphe | ≤ 4 | 4,1 | ❌ |
| Paragraphes sans phrase montrée | ≤ 20 % | 0 % | ✅ |

**Lecture des cas.**
- **Martín** : la phrase qui révèle l'erreur est bien montrée, au rang 2 : « Malgré une deuxième place qui lui a échappé dans le dernier tour face à Fabio Di Giannantonio, Martín termine sur le podium ». Mais elle ne correspond pas aux motifs fixés d'avance, qui attendaient « Il termine donc deuxième, devant Martin ». Elle compte donc comme non révélée. À la lecture, l'aide aurait montré l'erreur.
- **Zarco et « avril »** : le paragraphe fautif est long et mêle plusieurs faits. Les phrases montrées se rapportent au début du paragraphe, et la phrase qui révèle l'erreur, sur un fait de la fin, n'y est pas.
- **Police (paragraphes inventés)** : sous le paragraphe qui invente la « décentralisation » et la réactivité « face aux situations d'urgence », l'aide ne montre que deux titres, avec un score très bas (2,9 contre 15 à 70 ailleurs). Sous celui qui prête une « inquiétude de nombreux agents », elle montre « Les syndicats sont circonspects. » Le peu qu'elle trouve rend l'invention visible.

**Après la mesure, hors protocole** (`spikes/rel1/apres_phrase.py`) : la même aide appliquée à la seule phrase fautive, et non au paragraphe. Elle montre la phrase de Martín au rang 1, toujours hors des motifs ; celle de Zarco au rang 3, de Dana White au rang 1, de la citation au rang 1. « Avril » reste non révélé. Cela fait 3 sur 5 selon les motifs, et 4 sur 5 à la lecture. Ce chiffre a été obtenu après coup, sur les mêmes cas, et n'est donc pas une preuve.

## 5. Conclusion

**Échec**, selon les seuils fixés d'avance : 2 erreurs révélées sur 5, et 4,1 phrases par paragraphe. À la lecture, le banc dit pourtant deux choses utiles :
- **Au niveau du paragraphe, l'aide est trop grossière.** Un paragraphe de quatre ou cinq faits reçoit des phrases sur son premier fait. Au niveau de la phrase, elle montre beaucoup plus souvent la bonne phrase de source.
- **Le peu qu'elle trouve est un signal.** Un paragraphe qui ne reçoit que des titres, avec un score bas, est un paragraphe à vérifier : c'est le cas de la police.

## 6. Conséquences

| Document ou choix | Conséquence |
|---|---|
| Produit | Rien ne change à cette étape |
| Piste à soumettre à Joël | Une aide à la phrase : l'auteur désigne une phrase du brouillon (clic ou survol), et Otlet montre les phrases des sources qui partagent ses noms, ses chiffres et ses mots. Un paragraphe peu soutenu (seulement des titres, score bas) serait marqué « à vérifier ». À mesurer dans REL2, avec des motifs de révélation plus larges et des erreurs nouvelles, venues de l'usage, en plus des cinq de REL1 |

## 7. Ce que la preuve n'a pas couvert

- Les motifs des phrases révélatrices ont été écrits par Claude seul, avant la mesure. Ils se sont révélés trop étroits pour Martín.
- 5 erreurs connues seulement, dont 2 dans le même brouillon.
- Le temps réel de vérification par l'auteur n'est pas mesuré : il faudrait le faire faire à Joël sur quelques paragraphes.

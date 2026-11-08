# FID1 — Contrôler qu'un nom reste associé à la bonne place, au bon rang, au bon chiffre

| | |
|---|---|
| Statut | Conclue : échec |
| Durée maximale | 2 h (sans modèle) |
| Temps passé | 2 h 30 de préparation, de mesure et de relecture ; aucun appel au modèle |
| Ouverte le / conclue le | 2026-11-08 / 2026-11-08 |
| Choix concernés | U05 (garde-fous de la rédaction), ADR-0038, ADR-0046, RB1 §9, `docs/design/CAS_DE_REFERENCE.md` |
| Commande de rejeu | `python3 spikes/fid1/fid1.py freeze` (conteneur worker), puis `python3 spikes/fid1/fid1.py measure <dossier>` |

> Les sections 1 à 3 sont fusionnées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite.

## 1. Question

Un contrôle sans modèle peut-il signaler un nom associé à une autre valeur que dans les sources ? Une valeur, c'est une place (« deuxième »), un rang (« 11e ») ou un chiffre. Le contrôle doit le faire sans noyer l'auteur sous les fausses alertes.

Origine : Joël, 2026-11-08. Le cas de référence est celui du MotoGP. Le brouillon écrit que Jorge Martín termine « deuxième » du sprint ; les sources le placent troisième, derrière Fabio Di Giannantonio. Les noms et les chiffres existent tous dans les sources, mais ils y sont associés autrement. Le contrôle actuel (U05) vérifie que les noms, dates et nombres d'un brouillon existent dans ses sources. Il ne vérifie pas leurs associations.

## 2. Critères de réussite

| Critère | Seuil |
|---|---|
| Cas de référence : « Martín ↔ deuxième » dans le brouillon du MotoGP (brief 0793d3f8) | signalé |
| Permutations : dans des phrases des brouillons qui associent deux noms à deux valeurs différentes, les deux valeurs sont échangées. Part des permutations qui ajoutent un signalement | ≥ 80 % (40 permutations au plus) |
| Brouillons tels qu'écrits : moyenne des signalements par brouillon | ≤ 2 |
| Brouillons tels qu'écrits : part des signalements qui sont de vraies erreurs, à la relecture | ≥ 50 % |

**Succès** : une variante tient les 4 critères. **Partiel** : une variante signale le cas de référence et tient le critère des permutations, mais signale trop. **Échec** : sinon. Le contrôle reste alors à faire par la relecture de l'auteur.

## 3. Protocole

**Corpus figé.** Toutes les versions écrites par le modèle des briefs créés depuis le 2026-11-07 sur .252, soit 32 versions au moment de la rédaction : les essais [TEST] et [Essai P2], RB1, RB1-bis et les briefs de Joël. Chaque version vient avec le texte de ses sources (titre et texte complet, ou résumé). `fid1.py freeze` les écrit dans `frozen.json`, en lecture seule. Aucun appel au modèle.

**Ce qu'on extrait.**
- *Noms* : les suites de mots à majuscule, réduites au dernier mot (« Jorge Martín » donne « Martín »), sans les mots courants à majuscule (« Le », « Selon », les jours, les mois…). On compare les noms sans accents ni casse.
- *Valeurs* : les places et les rangs (premier, deuxième, second, 2e, 11e, vainqueur…), ramenés à un numéro de rang, et les nombres, sauf les années.
- Un nom qu'aucune source n'écrit n'est pas jugé ici : U05 le signale déjà.

**Variantes**, sans modèle :
- **V1, la phrase.** Tout nom et toute valeur d'une même phrase sont associés. L'association tient si une phrase d'une source contient le même nom et la même valeur.
- **V2, la proposition.** Comme V1, mais dans des propositions : la phrase est coupée aux virgules, aux deux-points et aux parenthèses, et aux mots « devant », « derrière », « après », « avant », « face à », « par », « contre », « que », « qui ».
- **V3, le nom qui précède.** Chaque valeur est associée au dernier nom écrit avant elle dans sa phrase, dans le brouillon comme dans les sources. Dans « Il termine deuxième, devant Martin », « deuxième » n'est associé à personne. L'association tient si une phrase d'une source fait la même association.

**Mesures.**
1. Le cas de référence : « Martín ↔ rang 2 » est-il signalé dans la version 1 du brief 0793d3f8 ?
2. Les permutations : pour chaque phrase du corpus qui contient deux noms et au moins deux valeurs différentes, les deux premières valeurs sont échangées. Une permutation est attrapée quand la phrase échangée reçoit un signalement que la phrase d'origine n'avait pas. Ce sont les mêmes permutations pour toutes les variantes, les 40 premières dans l'ordre du corpus.
3. Les signalements sur les brouillons tels qu'écrits : leur nombre par brouillon, puis une relecture de chacun contre les sources (`flags-V*.txt`), jugé vraie erreur ou fausse alerte. La relecture est faite par Claude ; Joël peut la refaire.

**Hors du protocole.** Rien n'entre dans le produit à cette étape. Si une variante réussit, son passage dans U05 sera proposé à Joël à part, comme un avertissement de la version, au même titre que les noms absents des sources.

## 4. Mesures

Le 2026-11-08 au soir, 32 brouillons figés, sans aucun appel au modèle. Seul écart au montage : `freeze` lit la base à travers la sécurité de l'espace de travail, comme le produit (le rôle de l'application ne peut pas lever la sécurité par ligne). Fichiers : `spikes/fid1/results/flags-V1.txt`, `flags-V2.txt` et `flags-V3.txt`.

| Critère | Seuil | V1, la phrase | V2, la proposition | V3, le nom qui précède |
|---|---|---|---|---|
| Cas MotoGP « Martín ↔ deuxième » signalé | oui | ❌ | ❌ | ❌ |
| Permutations attrapées | ≥ 80 % | ❌ 0 sur 40 | ❌ 14 sur 40 (35 %) | ❌ 19 sur 40 (48 %) |
| Signalements par brouillon | ≤ 2 | ❌ 3,9 | ✅ 1,2 | ❌ 2,2 |
| Vraies erreurs parmi les signalements | ≥ 50 % | non relu (V1 échoue déjà) | ❌ aucune sur 39 à la relecture | ❌ 1 à 2 sur 72 |

**Pourquoi le cas MotoGP passe.** Le contrôle cherche si une source associe « Martín » et « deuxième ». Une source le fait : « Jorge Martín consolide sa deuxième place », mais au championnat. Le brouillon a pris la place au championnat pour la place dans la course. L'association existe bien dans les sources ; c'est sa dimension (course ou championnat) qui change, et une règle sans modèle ne la voit pas.

**La seule vraie erreur trouvée** (V3), dans le même brouillon [RB1-bis] du MotoGP que Martín (brief 0793d3f8) : « Pedro Acosta et Johann Zarco, cinquième, complètent le top 5 avec respectivement 299 et 281 points ». Les sources donnent 281 points à Ai Ogura, pas à Zarco : c'est une deuxième erreur d'association dans ce brouillon, que la relecture de RB1 §9 n'avait pas vue. Le premier brouillon de RB1 écrivait juste « Ai Ogura ».

**Les fausses alertes** viennent surtout de la paraphrase : des pourcentages regroupés (« 43 % en Flandre et 25 % en Wallonie »), « respectivement », des chiffres de fiches techniques (cm³, ch), des mots à majuscule qui ne sont pas des noms (« Plus », « Parmi », « Practice »), des dates en chiffres (« le 6 octobre »).

## 5. Conclusion

**Échec.** Aucune variante ne signale le cas MotoGP, aucune n'attrape la moitié des permutations, et les signalements sont presque tous de fausses alertes. Contrôler sans modèle qu'un nom reste associé à la bonne valeur ne marche pas sur des brouillons réels : la paraphrase casse les associations exactes, et l'erreur de référence garde une association vraie, mais dans une autre dimension.

Le banc confirme aussi que l'erreur n'est pas isolée : le même brouillon associe aussi 281 points au mauvais pilote.

## 6. Conséquences

| Document ou choix | Conséquence |
|---|---|
| U05 (garde-fous) | Inchangé : ni V1, ni V2, ni V3 n'y entrent |
| Fidélité des associations | Reste à la relecture de l'auteur. Deux pistes à soumettre à Joël : (1) une aide à la relecture sans modèle, qui montre, pour chaque paragraphe, les phrases des sources citées qui contiennent ses noms et ses chiffres ; (2) un contrôle par le modèle local, à mesurer sur les deux erreurs du MotoGP et sur des permutations, avant tout usage |
| Cas de référence | Le top 5 du MotoGP (Zarco ↔ 281 points) rejoint le cas de Martín dans `docs/design/CAS_DE_REFERENCE.md` |

## 7. Ce que la preuve n'a pas couvert

- 32 brouillons, dont beaucoup sur les mêmes sujets (motos, immobilier, MotoGP). Les autres domaines sont peu représentés.
- Les signalements ont été relus par Claude seul.
- Les permutations échangent deux valeurs d'une même phrase. Elles ne couvrent pas les erreurs de dimension comme celle de Martín.

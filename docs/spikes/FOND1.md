# FOND1 — Le modèle repère-t-il une déformation en relisant un paragraphe ?

| | |
|---|---|
| Statut | Conclue : échec (3 déformations sur 6, aucune fausse alerte) |
| Durée maximale | 1 h de calcul, 38 appels au modèle |
| Temps passé | journal de temps, tâche FOND1 |
| Ouverte le / conclue le | 2026-11-01 / 2026-11-01 |
| Choix concernés | Contrôle du fond, chantier distinct d'U05 (Joël, 2026-11-01) ; audit qualité du moteur de génération (ADR-0038) |
| Commande de rejeu | sur la VM de travail, depuis une copie de `spikes/fond1` : `OLLAMA_URL=… sh run-fond1.sh` |

> Les sections 1 à 3 sont commitées **avant** la première mesure (ADR-0018). Elles ne changent plus ensuite. Sur décision de Joël (« Tu peux lancer le test », 2026-11-01), ce test part du commit, sans attendre une fusion : il n'engage ni le produit ni le verdict de P02.

## 1. Question

Quand `qwen3:14b` relit un paragraphe face aux sources qu'il cite, repère-t-il les déformations déjà observées, sans crier au loup sur les paragraphes fidèles ?

Ce test est une **indication**, pas un taux : 19 paragraphes, dont des défauts que je connais déjà. Un succès justifie une vraie preuve sur un corpus plus large. Il ne prouve pas que le modèle attrape les déformations qu'on n'a pas encore vues.

## 2. Critères de réussite

Seuils proposés et acceptés par Joël le 2026-11-01. Chacun doit être tenu **à chacune des deux passes**.

| # | Critère | Seuil |
|---|---|---|
| C1 | Déformations repérées, sur D1 à D6 | **au moins 5 sur 6** |
| C2 | Fausses alertes, sur F1 à F12 | **au plus 2 sur 12** |

- **Repérée** : verdict `deforme`, et l'affirmation ou la raison donnée par le modèle porte sur le défaut, c'est-à-dire contient un des mots fixés dans `spikes/fond1/cases.json` (par exemple « confiance » pour D1). Un verdict `deforme` pour une autre raison est compté à part : il n'est pas une détection.
- **Fausse alerte** : verdict `deforme` sur un paragraphe fidèle, quelle qu'en soit la raison.
- **D7** est hors seuil, à titre d'indication.

## 3. Protocole

**Jeu d'essai** validé par Joël le 2026-11-01 : 6 déformations, 12 paragraphes fidèles et D7. Le fichier `cases.json` repère chaque paragraphe par son article et son début, avec ses sources citées. Pour D6, une réponse du Reporter qui ne cite rien, on prend les sources 2, 3 et 4 de l'article du même nom (décision de Joël). Les textes restent sur la VM de travail, dans `~/fond1`, et ne sont pas versionnés (ADR-0038).

**Comparaison** : le paragraphe, sans ses références, face au texte complet de ses seules sources citées.

**Consigne** : une seule, écrite dans `fond1.py`, volontairement générale. Elle demande si une affirmation dit autre chose que les sources ou affirme ce qu'elles ne disent pas, sans énumérer les types de défauts du jeu d'essai, pour ne pas lui souffler les réponses. Elle n'est pas retouchée pendant le test.

**Réponse attendue** : un objet JSON avec le verdict (`fidele` ou `deforme`), l'affirmation en cause, la phrase de la source la plus proche et la raison. Le programme vérifie sans modèle que cette phrase existe dans les sources, et rapporte le taux.

**Exécution** : `qwen3:14b` sur le PC de Joël, un appel à la fois, détaché, température 0,2, graine 1 puis 2, fenêtre de 8 192 jetons. Rien n'est écrit dans Otlet. Aucune autre étape lourde pendant le test. À 1 h de calcul, le test s'arrête et conclut avec ce qu'il a.

**Si échec** : une consigne ou un modèle plus adaptés, ou l'abandon de cette voie, sur décision de Joël.

## 4. Mesures

Mesure du 2026-11-01, sur la VM de travail, `qwen3:14b` sur le PC de Joël : 38 appels en un peu plus de 6 min de calcul, bien moins que l'heure prévue. Fenêtre jamais dépassée (5 381 jetons au plus). Résultats sans textes : `spikes/fond1/results/summary.json`.

| Critère | Seuil | Passe 1 | Passe 2 | Verdict |
|---|---|---|---|---|
| C1 déformations repérées | ≥ 5 sur 6 | 3 (D3, D4, D6) | 3 (D3, D4, D6) | ❌ |
| C2 fausses alertes | ≤ 2 sur 12 | 0 | 0 | ✅ |
| D7, hors seuil | — | manquée | manquée | — |

- **Manquées aux deux passes** : D1, D2, D5 et D7, toutes en verdict `fidele`. Sur D1, la raison ne parle que de la phrase sur S&P et jamais de la confiance des marchés.
- **D6 à moitié** : le modèle relève les noms des trains, pas la cause attribuée à la seule panne.
- **Réponse invalide** : à la passe 1, F7 a été coupée par la limite de sortie, en recopiant une longue phrase de source. Le début de la réponse dit `fidele`. Elle ne compte pas comme fausse alerte, ce que dit le §2 : une première version du résumé la comptait à tort, corrigée après la mesure sans toucher aux seuils.
- **Phrases de source retrouvées telles quelles** : 10 et 12 sur 19.

## 5. Conclusion

**Échec sur la détection, réussite sur le bruit.** Le modèle a repéré 3 déformations sur 6, sans aucune fausse alerte : tous ses verdicts `deforme` portaient sur une vraie déformation. Il ne suffit pas tel quel, et un article qui passe ce contrôle ne peut pas être présenté comme fidèle.

En relisant ses raisons, la taille du paragraphe explique mal les manques : sur D2, D5 et D7, le modèle a lu l'élément en cause et l'a validé ; seul D1 laisse penser qu'il ne l'a pas regardé. Limite du protocole : il donnait son verdict avant toute raison, réflexion désactivée, ce qui n'a pas été remesuré.

## 6. Conséquences

| Document ou choix | Conséquence | ADR |
|---|---|---|
| Contrôle du fond | **Décision de Joël (2026-11-01)** : piste arrêtée pour l'instant, résultats conservés, pas de second test. Conclusion provisoire : qwen3:14b peut aider à repérer certaines incohérences ou omissions, mais n'est pas aujourd'hui un garde-fou fiable contre les glissements de sens ou de nuance. Le sujet reste ouvert | — |
| U05, P02 | Inchangés | — |

Le code reste dans `spikes/fond1` (ADR-0018).

## 7. Ce que le test n'a pas couvert

- Une consigne affirmation par affirmation, un autre modèle.
- Le taux réel : 19 paragraphes, 4 articles, des défauts connus d'avance.
- Les paragraphes fidèles du budget fédéral (voir le jeu d'essai).

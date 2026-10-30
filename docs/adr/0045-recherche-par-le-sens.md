# ADR-0045 — Recherche par le sens, en plus des mots

| | |
|---|---|
| Statut | Accepté (2026-10-30) ; mise en œuvre par lots (sens-1 à sens-4) |
| Date | 2026-10-30 |
| Décideur | Joël |
| Documents touchés | ADR-0035 (recherche plein texte close pour É1), ADR-0033 (fonction de recherche), ADR-0043 (moteur de l'Assistant de veille), ADR-0044 (Reporter) ; `TECH_CHOICES.md` §8 ; ADR-0025 (qualité d'abord) |
| Origine | Bancs du Reporter des 29 et 30 octobre 2026 (≈ 110 questions avec qwen3:14b sur la Veille de Joël) ; demande de Joël : une solution pérenne, sans action de l'utilisateur, plutôt qu'un glossaire à entretenir |

## Contexte

Le Reporter et l'Assistant de veille trouvent les articles par leurs **mots** : un modèle traduit la question en termes, et le moteur plein texte de PostgreSQL cherche ces termes. Les bancs montrent la limite de cette approche.

- **La langue.** La Veille est en français, en néerlandais et en anglais. Si le modèle oublie une langue, ses articles disparaissent. « La situation financière des hôpitaux en Flandre » n'a pas trouvé « Geldproblemen dwingen Vlaamse ziekenhuizen tot fusies », faute de « ziekenhuizen ». « Le budget de la région Bruxelles-Capitale » n'a pas trouvé l'article de Bruzz, faute de « begroting ». Le prompt reporter-3 demande désormais les termes langue par langue, mais il dépend toujours du modèle de l'utilisateur.
- **Les mots qui se ressemblent.** La recherche combine les racines de huit langues. « strikes » trouve donc la « Dacia Striker », et « Bruxelles » trouve la « Fédération Wallonie-Bruxelles » (corrigé par une règle, ADR-0044).
- **Le sens sans mot commun.** « Qui sont les victimes ? », « l'IA à l'école », « les essais de motos » : l'article pertinent ne contient pas toujours les mots de la question.

Une douzaine de règles sans modèle ont corrigé ce qui pouvait l'être (lieux, pluriels, sigles, suites de conversation). Ce qui reste tient à la nature de la recherche par mots.

Joël ne veut pas d'un glossaire à gérer : la solution doit vivre seule.

## Options

1. **Recherche hybride : les mots et le sens (recommandé, après un spike).** À la collecte, chaque élément reçoit un vecteur calculé par un petit modèle d'encodage **multilingue**, exécuté **localement** dans le worker, sans fournisseur. Une question est encodée de la même façon. L'ensemble devient l'union des éléments trouvés par les mots et des plus proches par le sens, classés ensemble. Les termes restent visibles et modifiables (ADR-0044 §3). Le sens ajoute ce que les mots manquent, sans remplacer les mots.
   - Stockage : pgvector, déjà présent dans l'image PostgreSQL de production (`pgvector/pgvector:0.8.7-pg18-trixie`, `deploy/compose.yaml`) ; l'extension reste à activer par une migration.
   - Modèle candidat : un encodeur multilingue de petite taille (de l'ordre de 100 millions de paramètres, 384 dimensions), sous licence compatible AGPL, exécuté par une bibliothèque ONNX. Le choix exact est un résultat du spike.
2. **Encodage par le fournisseur IA de l'utilisateur** (Ollama, OpenAI…). Pas de modèle embarqué, mais la qualité et la disponibilité dépendent du profil de chaque utilisateur. Les vecteurs de deux modèles ne se comparent pas : changer de modèle oblige à tout réencoder. C'est contraire à « aucune dépendance obligatoire à un fournisseur ».
3. **Garder la recherche par mots seule.** On continue d'améliorer les règles et le prompt. Ça ne coûte rien de plus, mais le plafond est atteint pour les langues et le sens.

## Ce que le spike doit mesurer (avant toute décision)

- **Rappel** : sur les questions des bancs du 29 et du 30 octobre qui ont échoué faute de mots (hôpitaux flamands, budget bruxellois, grèves SNCB, IA à l'école, victimes de l'accident en Espagne…), combien d'articles de référence la recherche hybride retrouve, comparée à la recherche par mots seule.
- **Bruit** : combien d'articles hors sujet le sens ajoute dans les 30 premiers.
- **Coût d'encodage** : temps par élément sur la VM du NAS (Celeron, référence basse) et sur la VM du PC, pour le flux réel d'environ 1 300 éléments par jour et pour la reprise des éléments déjà collectés.
- **Mémoire et disque** : le poids du modèle chargé dans le worker, et la taille de l'index pour 30 000 éléments.
- **Latence** : le p95 de la recherche hybride, comparé au seuil de L2 (300 ms) qu'ADR-0035 remet à l'épreuve à I4.

## Résultats du spike (2026-10-30)

Rapport complet : `spikes/a2-sens/RAPPORT.md`. Sur 7 questions qui avaient échoué, avec MiniLM-L12 multilingue (384 dimensions, ONNX, local) :

- **hôpitaux en Flandre** : 0 article juste avec les mots, 3 sur 3 avec le sens, en tête ;
- **victimes de l'accident en Espagne** : 15 avec les mots, 20 avec l'hybride ;
- **pertes d'emploi en Belgique** : 5 avec les mots, 10 avec l'hybride ;
- **budget bruxellois** : 6 avec les mots, 8 avec l'hybride ;
- **IA à l'école** et **essais de motos** : gain faible ou nul ;
- l'hybride ne recule nettement sur aucune question.

Coût sur le NAS : 322 ms par élément (environ 7 minutes par jour pour le flux réel), 725 Mo de mémoire au pic, 0,22 Go de modèle, 6,5 Mo d'index pour 4 213 éléments. mpnet-base fait à peine mieux, pour trois fois le temps et deux fois la mémoire.

Recommandation du spike : l'option 1 avec MiniLM-L12 multilingue, et une mesure de mémoire de la pile complète sur le NAS avant de fermer le lot.

## Décision

Décision de Joël du 2026-10-30 (« ok » à la recommandation du spike) : **l'option 1, avec MiniLM-L12 multilingue** (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0, 384 dimensions), exécuté localement par fastembed (ONNX). Le modèle est **inclus dans l'image** : aucun téléchargement au démarrage, aucune sortie réseau, une installation hors ligne possible.

Lots :
1. **sens-1** : pgvector activé, un vecteur par élément (`source_items.meaning`), une tâche qui encode les éléments sans vecteur, les plus récents d'abord, par petits lots ;
2. **sens-2** : la recherche hybride (mots et sens, fusion par rang réciproque) dans le moteur de l'Assistant et du Reporter, les termes restant visibles ;
3. **sens-3** : un banc sur les questions des bancs A2 ;
4. **sens-4** : la mesure de mémoire de la pile complète sur le NAS, avant de fermer le lot.

## Conséquences si l'option 1 est retenue après le spike

- Plus de dépendance au modèle de l'utilisateur pour trouver la matière dans toutes les langues. Le modèle de l'utilisateur reste celui qui traduit, lit et rédige.
- Le worker charge un modèle de plus, à mesurer contre le profil de 4 Go (ADR-0025 : la qualité l'emporte, mais la mémoire de la pile complète décide).
- Une migration ajoute la colonne de vecteurs et son index, et une tâche encode les éléments déjà collectés.
- Les règles sans modèle d'ADR-0044 restent utiles : elles décident de l'opération et des filtres (langue, période, lieu).

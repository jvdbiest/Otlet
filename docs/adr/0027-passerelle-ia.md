# ADR-0027 — Passerelle IA : adaptateurs maison, budget à réservation, fournisseurs bloqués par défaut

| | |
|---|---|
| Statut | Proposé |
| Date | 2026-10-16 |
| Décideur | Joël |
| Documents touchés | `TECH_CHOICES.md` §11 (TC-08, TC-09) ; `ARCHITECTURE.md` §10 (passerelle IA) |
| Origine | Rapport S4 (conclu : partiel) |

## Contexte

S4 a mesuré une passerelle minimale (`docs/spikes/S4.md` §4). Elle repose sur un adaptateur compatible OpenAI et un adaptateur Anthropic natif, écrits sur les SDK officiels, avec un tableau des modèles et un budget à réservation dans PostgreSQL.

- **Modèle local** : `qwen2.5:1.5b-instruct` sous Ollama atteint 96 % de sorties valides sur le NAS.
- **Budget** : jamais dépassé sur 200 appels concurrents.
- **Replis** : 100 scénarios sur 100 corrects.

Les fournisseurs payants et ceux qui exigent un compte externe n'ont pas été mesurés, par décision de Joël (pas de dépense pour l'instant).

## Décision proposée

1. **TC-08 confirmé.** Les adaptateurs sont écrits sur les SDK officiels (`openai` avec URL de base, `anthropic`), derrière le contrat interne `generate`. Aucun autre module n'importe un SDK de fournisseur. LiteLLM n'est pas embarqué.
2. **Tableau des modèles** en fichier de données versionné, avec un statut par modèle :
   - **« testé »** : C1 tenu sur les 50 briefs de S4 ;
   - **« non testé »** : utilisable, avec un avertissement à l'utilisateur ;
   - **« bloqué »** : refusé par la passerelle avant tout appel. Tout fournisseur payant est **bloqué par défaut** tant que l'administrateur de l'instance ne l'a pas autorisé explicitement. Pour le projet, cette autorisation revient à Joël.
3. **Budget à réservation dans PostgreSQL.** Chaque appel réserve d'abord, par un `UPDATE` conditionnel sur la ligne du budget, le coût maximal estimé : entrée en caractères ÷ 3,5 avec 20 % de marge, plus la sortie maximale. **10 % du budget** sont tenus en réserve pour les fournisseurs qui facturent plus qu'annoncé. Le coût réel remplace la réservation après l'appel.
4. **Nouveaux essais et replis**, dans l'ordre de préférence du profil :
   - **429 avec un `Retry-After` de 2 s au plus** : attente, puis jusqu'à deux nouveaux essais sur le même fournisseur, puis repli ;
   - **5xx ou délai dépassé** : un nouvel essai, puis repli ;
   - **400** : arrêt immédiat, sans nouvel essai ni repli ;
   - **sortie invalide** : une seule réparation, sur le même fournisseur.

   Les SDK sont réglés sans nouvel essai propre (`max_retries=0`), pour que la passerelle seule décide.
5. **Schéma de sortie énumératif** : à chaque appel, la passerelle énumère les identifiants de sources du brief dans le JSON Schema transmis. C'était la cause des 2 échecs du modèle local. L'effet sera mesuré à la tranche verticale d'É1.
6. **Profil local** : `qwen2.5:1.5b-instruct` est le premier profil « testé ». Il est lent sur la plateforme minimale (7 min par article). Une machine plus puissante est recommandée pour le travail courant.
7. **Avant toute mise en service d'un fournisseur réel**, on mesure ses 50 briefs. Ces mesures se font quand Joël donne son accord pour chaque fournisseur, avec des plafonds de dépense posés chez le fournisseur.

## Conséquences

- La passerelle est utilisable sans aucun fournisseur payant, avec Ollama.
- Le tableau des modèles devient un document d'exploitation : son statut « bloqué » est la garantie technique de la règle « pas de dépense sans accord ».
- La réserve de 10 % réduit d'autant le budget utilisable. Elle pourra être ajustée fournisseur par fournisseur quand des dépassements réels seront mesurés.

## Options écartées

- **LiteLLM embarqué** : dépendance large au cœur de la chaîne des clés d'API, et déjà compromise une fois (TC-08).
- **Nouveaux essais laissés aux SDK** : la passerelle ne pourrait plus réserver le budget avant chaque appel, ni journaliser chaque tentative.
- **Budget vérifié après l'appel** : il ne peut empêcher un dépassement sous des appels concurrents.

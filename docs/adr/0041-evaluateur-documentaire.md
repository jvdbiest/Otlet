# ADR-0041 — Évaluateur documentaire : juger la matière d'un brief sur cinq critères

| | |
|---|---|
| Statut | Accepté (2026-10-23) ; mise en œuvre par lots (A1a-1 d'abord) |
| Date | 2026-10-23 |
| Décideur | Joël |
| Documents touchés | ADR-0038 (calcul du niveau de matière) ; ADR-0039 (textes réservés) ; ADR-0024 et U05 (corroboration) ; backlog d'É1 (A1a-1, A1a-2, A1b) |
| Origine | Fil de Joël du 2026-10-23 ; documents partagés « Otlet · Briefs par conversation (Chat + IA) », « Otlet · A1 : proposer un brief en un tour » et « Otlet · A1a : évaluateur documentaire dans le formulaire de brief » |

## Contexte

En préparant un assistant de brief (« Partir d'une idée »), les cas réels de la Veille de Joël ont montré que le niveau de matière d'ADR-0038, fondé sur le seul nombre de mots, se trompe dans les deux sens. Les « flottes d'entreprise » paraissaient suffisantes (1 827 mots), alors qu'un seul élément traitait le sujet et que son texte était réservé. La « moto électrique » paraissait suffisante avec 6 éléments, alors que 5 venaient du même site. Joël a demandé que la matière tienne compte du nombre de sources, de leur diversité, des mots, de la fraîcheur et de la corroboration. Le diagnostic doit déboucher sur une action. L'évaluateur qui en résulte fonctionne sans IA et améliore tous les briefs : Joël en fait une fonctionnalité centrale d'Otlet, et pas seulement une étape vers l'assistant.

## Décision

1. **Principe : ce que disent les sources n'est pas l'interprétation éditoriale.** Otlet distingue toujours ce qui vient des sources de ce qui vient de l'auteur. Par exemple : « Les sources parlent des entreprises en général ; l'angle PME est le tien. » Le principe vaut pour l'évaluateur, pour l'assistant de brief, et plus tard pour la rédaction (règle d'attribution d'ADR-0038, U05).
2. **Cinq critères**, calculés sur les éléments du brief. Un doublon compte une fois. L'éditeur est la source du flux, ou l'origine déclarée d'une saisie manuelle. Un texte réservé ne compte que pour son résumé. La date est celle de publication, sinon celle de collecte.

   | Critère | ✓ | ! | ✗ |
   |---|---|---|---|
   | Sources : éléments qui traitent le cœur du sujet | 3 ou plus | 1 ou 2 | aucun |
   | Diversité : éditeurs distincts | 3 ou plus | 2 | 1 seul |
   | Mots : règle d'ADR-0038 (80 % des mots, plancher 150) | longueur demandée possible | longueur réduite | sous le plancher |
   | Fraîcheur : âge de l'élément le plus récent | 7 jours ou moins | 8 à 30 jours | plus de 30 jours |
   | Corroboration : faits principaux rapportés par deux éditeurs au moins | la plupart | quelques-uns | aucun |

   Ces seuils sont un point de départ. Ils seront recalibrés après usage, en commençant par réévaluer les briefs existants de Joël.
3. **Règle hybride**, retenue contre une règle stricte (le critère le plus faible décide toujours) et contre une règle pondérée (un score). Comparées sur les cas réels, la stricte rejetait à tort un dossier de fond et un Panorama, et la pondérée donnait 88/100 à six éléments venant à cinq d'un même site.
   - **Bloquants** : sources, mots, diversité. Un ✗ donne « insuffisante ». Un seul éditeur revient à réécrire sa couverture, avec le risque de recopie qu'ADR-0038 combat.
   - **De qualité** : les bloquants, plus la corroboration en Synthèse et la fraîcheur pour une actualité. S'ils ne sont pas tous ✓, la matière est « limitée ».
   - **Informatifs** : affichés, sans effet sur le niveau. C'est la fraîcheur pour un dossier de fond et la corroboration en Panorama.
4. **Nouveau champ du brief, Nature** : Actualité (par défaut, valeur des briefs existants) ou Dossier de fond. Il ne sert qu'à juger la matière. Il ne change ni la longueur, ni le ton, ni le prompt ; un usage plus large serait une décision à part.
5. **Affichage.** Un panneau sous les éléments du brief remplace la ligne « Matière disponible ». Il donne le niveau et sa raison en une demi-phrase, puis les cinq critères avec leur valeur concrète, marqués ✓, !, ✗ ou « i ». Il n'affiche jamais de score, et jamais les mots « bloquant » ou « qualité ». Il ne bloque jamais l'enregistrement d'un brief. Il est ouvert quand la matière est limitée ou insuffisante, et se réduit à une ligne quand elle suffit. La première fois, une ligne l'explique. Le même panneau, en lecture seule, accompagne le bouton « Générer ».
6. **Une seule règle, côté serveur.** Une fonction d'évaluation du domaine `writing` rend les critères, le niveau et sa raison. L'interface l'appelle à chaque changement et ne garde pas sa propre copie de la règle. Le contrôle à la génération reste celui d'ADR-0038 : 409 quand les mots sont insuffisants, et « Générer quand même ».

   **L'évaluateur aide à décider, il n'interdit pas (Joël, 2026-10-24).** Son niveau ne bloque jamais la génération. Une matière suffisante se génère sans rien dire. Une matière limitée se génère avec un avertissement. Une matière insuffisante se génère avec un avertissement renforcé, affiché près de « Générer ». L'utilisateur reste responsable de sa décision. Mesure de cadrage à l'appui : sur les 14 briefs réels de Joël, 11 n'avaient qu'un éditeur et aucun n'en avait trois.
7. **Corroboration** : elle n'est pas évaluée dans le premier lot (affichée « pas encore évaluée par Otlet », sans effet sur le niveau). Elle le sera par l'assistant de brief, où le modèle regroupe les éléments par fait et le serveur vérifie les éditeurs, puis sans modèle par la similarité d'U05.
8. **Actions.** Chaque critère en défaut propose une action concrète : chercher dans la Veille, voir d'autres éditeurs, déclarer ses droits (ADR-0039), choisir une longueur plus courte, créer un sujet de veille. Changer de Nature n'est jamais proposé comme correction : la Nature décrit ce que l'on écrit.
9. **Découpage prudent** (Joël) : A1a-1, le diagnostic et le panneau avec des liens simples, puis une validation en usage réel. A1a-2, les actions sur place (listes de suggestions, ajout direct), seulement si l'usage montre qu'elles apportent une vraie valeur. Puis A1b, l'assistant « Partir d'une idée », qui réutilise l'évaluateur. Ordre dans le backlog : F08 (sauvegarde), puis A1a-1, puis A1b.

## Conséquences

- ADR-0038 garde la longueur liée à la matière et les trois niveaux. Le calcul du niveau passe ici (voir sa révision du 2026-10-23).
- Migration : colonne `briefs.nature` (`news` par défaut, `in_depth`).
- Les éléments du brief doivent porter l'éditeur, les dates et le lien de doublon. L'évaluation d'une sélection non enregistrée passe par l'API.
- La règle des mots qui existe aujourd'hui dans l'interface (`matterLevel` de `BriefsPage.tsx`) disparaît au profit de l'appel au serveur.
- Le panneau doit rester simple. Toute addition (actions avancées, nouveaux critères) attend l'observation de son usage réel.

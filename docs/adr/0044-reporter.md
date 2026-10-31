# ADR-0044 — Reporter : un assistant documentaire progressif

| | |
|---|---|
| Statut | Accepté (2026-10-25) ; mise en œuvre par lots (A2-1, A2-2, A2-3) |
| Date | 2026-10-25 |
| Décideur | Joël |
| Documents touchés | ADR-0043 (moteur de l'Assistant de veille, règles sans modèle §10) ; ADR-0041 (évaluateur, perspective du pilote automatique) ; ADR-0038 (contrôles après génération) ; ADR-0027 (choix du modèle par l'utilisateur) ; backlog d'É1 (A2-1 à A2-3) |
| Origine | Fil de Joël du 2026-10-25 ; document partagé « Otlet · A2 : Reporter » ; bancs `spikes/a2-reporter` (`replay.py`, `bench.py`, `reconstitute.py`) |

## Contexte

L'Assistant de veille (ADR-0043) trouve la matière d'un sujet et la trie. Joël veut aussi pouvoir interroger sa Veille par conversation : « Les articles sur la tempête Austen », « Lesquels concernent Bruxelles ? », « Combien de blessés ? ». Il ne veut pas un chatbot qui répond de mémoire, mais un outil de vérification : chaque réponse est un ensemble d'articles qu'on ouvre, et chaque chiffre est cité par source.

Les bancs A2 du 2026-10-25, sur la Veille de Joël avec qwen3:14b local, ont donné :

- **traduire une question en opération** : 24 fois sur 25 ;
- **retrouver la matière** : 88 % des articles de référence avec les termes du modèle, après deux garde-fous sans modèle (un concept n'est gardé que si la question le nomme ; une langue demandée est un filtre) et le filtre des termes trop généraux ;
- **répondre à une question de fait** : 8 réponses justes sur 10, avec leur contexte, aucune addition entre sources ;
- **étiqueter la concordance entre sources** : le modèle se trompe souvent (5 sur 11). Une règle calculée sur les lignes donne la bonne étiquette 10 fois sur 11 ;
- **reconstituer** (chronologie ou synthèse sur plusieurs sources), en six passages :
  - justes et riches pour les émeutes à Bruxelles et pour le budget fédéral ;
  - « je ne trouve pas » pour la culture des OGM, ce qui est juste ;
  - faible sur le début et la fin de la tempête Austen, ce que la confiance calculée signale ;
  - 2 à 7 minutes par reconstitution avec un modèle local.

Dans chaque banc, l'essentiel du progrès est venu de règles sans modèle, pas de retouches du prompt.

## Décision

1. **Un assistant documentaire progressif.** Le Reporter trouve, filtre, vérifie, compare, puis, seulement si l'auteur le demande, reconstitue. Pas d'analyse IA systématique dès la première réponse.
2. **Partage des rôles.** Le modèle comprend l'intention de l'auteur et fait les traductions difficiles (question en opération, termes, lignes de fait). La vérification, la concordance et les contrôles de cohérence sont des règles du moteur, explicables, vérifiables et communes à A1b et A2 (ADR-0043 §10).
3. **Sept opérations**, sur l'ensemble courant :
   - **chercher** : un ou deux concepts et leurs termes, élargis par le glossaire, avec le filtre des termes trop généraux ;
   - **restreindre** : un concept ajouté, ou une langue (toujours un filtre) ;
   - **élargir** : des termes ajoutés à un concept ;
   - **trier** : le tri de l'Assistant de veille ;
   - **fait** : réponse immédiate ;
   - **reconstituer** : sur demande ;
   - **agir** : garder, préparer un brief.

   Chaque réponse est un ensemble cliquable ; les termes restent visibles et modifiables.
4. **Garde-fous de la traduction** : un concept proposé par le modèle n'est gardé que si la question le nomme ; une langue nommée dans la question devient un filtre ; seules fr, nl et en sont des langues. Une période nommée (« ces derniers jours », « cette semaine » : 7 jours ; « aujourd'hui », « du jour » : 1 jour) est aussi un filtre (Joël, 2026-10-25 : « ces derniers jours » gardait les 30 jours de la conversation, et le brief datait des événements de septembre).
5. **Réponse de fait.** Une ligne par chiffre ou date : source, ce qu'il mesure, quand, où, extrait exact. Une ligne dont l'extrait n'est pas dans l'article est retirée. Aucune addition entre sources. « Je ne trouve pas » quand aucune ligne ne tient. La conversation est transmise pour lire « Combien ? » après « des blessés ? ».
6. **Concordance calculée par le moteur**, jamais étiquetée par le modèle. Elle a cinq états : concordent, divergent, partiel, une source, absent. Deux lignes de sources différentes sont comparées quand elles mesurent la même chose, au même moment et au même lieu. Le lieu est normalisé par le glossaire ; un lieu plus étroit n'est pas comparé. Le Reporter montre toujours les lignes comparées, qu'elles concordent ou qu'elles divergent.
7. **Reconstituer**, la septième opération :
   - **Lancement.** Jamais d'office : quand une question en demande une, le Reporter répond d'abord ce qu'il peut (l'ensemble, les faits) et propose un seul bouton, « Reconstituer ».
   - **Forme.** Le Reporter choisit lui-même la forme, chronologie ou synthèse.
   - **Exécution.** Elle tourne en tâche de fond, comme le tri d'un dossier, et son résultat s'ajoute au fil quand il est prêt.
   - **Chaîne.** Elle se fait en quatre étapes :
     - le tri de l'Assistant d'abord : « proche » complète la matière, il ne la fait jamais ; sans un article qui traite le sujet, le Reporter ne trouve pas ;
     - une extraction par volet ;
     - les règles de lignes ;
     - les lignes présentées par date, les volets servant de filtres.
   - **Analyse IA.** Elle est écrite à partir des lignes retenues seulement. Chaque phrase renvoie à ses lignes, et une déduction est dite comme telle. Une phrase dont un nom, un chiffre ou une date n'est ni dans ses articles ni dans leurs dates est signalée.
   - **Confiance.** Elle est calculée :
     - forte quand chaque volet a deux sources ou plus et qu'aucun ne diverge ;
     - moyenne quand un volet ne tient qu'à une source ;
     - faible quand un volet est vide ou diverge.

     Elle est affichée avec sa raison.
8. **Règles de lignes** (bancs du 2026-10-25) :
   - une ligne qui ne dit rien de plus que la question, ou « n'est pas mentionné », est retirée ;
   - les noms et chiffres d'une ligne doivent être dans son article, sinon elle est « à vérifier » et n'alimente pas l'analyse ;
   - un jour de semaine que le calendrier dément (« mercredi 23 octobre ») est refusé ;
   - un jour de semaine écrit dans un article est résolu par la date de l'article ;
   - un même extrait ne donne qu'une ligne.
9. **Les faits sourcés restent la réponse de référence.** La reconstitution est une couche d'analyse distincte, marquée « Analyse IA » avec sa confiance.
10. **Vers la rédaction.** « Préparer un brief » pré-remplit le brief existant, sans modèle :
    - **Contenu.** Les éléments qui portent une ligne retenue, le titre de travail, l'angle, la nature (chronologie, actualité ; synthèse, fond) et le plan dans les instructions.
    - **Faits vérifiés.** Un nouveau champ reprend les lignes retenues avec source et extrait. La rédaction les reçoit comme faits à respecter, et les chiffres et dates du brouillon sont contrôlés contre les sources et ces faits.
    - **Analyse IA.** Elle accompagne le brief dans un encadré distinct, pour comprendre le sujet. Elle n'est jamais une source ni un contenu publiable et n'est pas transmise par défaut au modèle de rédaction. La comparaison signale tout passage du brouillon qui en reprend les mots.

    En résumé : **les faits vérifiés pour écrire, l'analyse IA pour comprendre.**
11. **Traçabilité.** Le brief garde le lien vers la conversation. Depuis un article de la bibliothèque, on remonte au brief, à la conversation, à la ligne, à l'extrait et à l'article d'origine.
12. **Le modèle de l'utilisateur** (ADR-0027), local ou hébergé. Rien n'est enregistré, généré ou publié sans action de l'auteur.
13. **Le banc est rejoué à chaque changement des prompts du Reporter**, avec les douze conversations, les dix questions de fait et les quatre reconstitutions. Le cas des OGM (« je ne trouve pas ») est un contrôle permanent.
14. **Découpage** :
    - **A2-1** : la conversation (opérations sauf reconstituer), la réponse de fait immédiate, la concordance calculée, les garde-fous de la traduction, les ensembles cliquables ;
    - **A2-2** : « Reconstituer » en tâche de fond, chronologie d'abord, volets en filtres, analyse IA et confiance calculée ;
    - **A2-3** : « Préparer un brief » depuis le Reporter, le champ « Faits vérifiés », l'encadré « Analyse IA », les deux garde-fous dans la comparaison, la traçabilité.

15. **Règles ajoutées à l'usage** (2026-10-25, premiers essais de Joël) : seules des mesures identiques se comparent (une température minimale et une maximale ne divergent pas) ; une réponse de fait peut lire 15 articles de plus, ses lignes s'ajoutent et la concordance est recalculée ; au-delà de 20 articles non triés, le Reporter invite à trier avant le brief. Côté rédaction : des dates demandées par l'auteur sont annoncées au modèle et contrôlées après la génération, et une section recopiée par le modèle est retirée sans modèle.

16. **Deux types de reconstitution** (Joël, 2026-10-31, après « Les découvertes en astronomie » : le bloc « En bref » résumait des actualités indépendantes sans les reconstituer). « Reconstituer » repère d'abord les sujets distincts dans les articles lus. Le choix se fait **sur les articles et non sur la question**, que le modèle classe mal (le budget fédéral et les péages lus comme des domaines, banc du 2026-10-31) :
    - **plusieurs sujets indépendants**, aucun ne tenant 60 % des articles lus : un **panorama**, la liste des principaux sujets avec leurs sources, et « Reconstituer ce sujet » sur chacun, qui ouvre une question sur ses seuls articles ;
    - **un sujet** : la reconstitution de §7, « En bref » en tête, puis les faits et l'analyse repliés.

    **Un seul sujet, malgré plusieurs titres** : le modèle découpe parfois une même affaire en angles. Le budget fédéral a donné 8 « sujets », le plus gros tenant 8 articles sur 15, mais 29 mentions pour 15 articles : ils se partagent les articles. Plus de 1,3 mention par article signifie donc une seule affaire (astronomie 9 pour 8, motos 11 pour 15, Austen 22 pour 15, budget 29 pour 15). Seuil tiré de cinq ensembles, à revoir si d'autres cas le contredisent.

    **Confiance** : un volet vide n'est plus à lui seul une faiblesse, le modèle en invente (« Impact environnemental »). Elle devient moyenne, et faible quand la moitié des volets au moins sont vides, ou qu'un volet diverge.

## Conséquences

- Le Reporter réutilise le moteur de l'Assistant de veille (concepts, glossaire, termes trop généraux, tri) ; il ne le recopie pas. L'Assistant reste le mode avancé.
- Une reconstitution coûte plusieurs minutes avec un modèle local : c'est une tâche qu'on lance et qu'on retrouve, jamais une attente bloquante.
- Les règles sans modèle (concordance, calendrier, ancrage dans l'article) deviennent des briques communes, réutilisables par l'évaluateur, la rédaction et le futur pilote automatique.
- Le tri du modèle varie d'un passage à l'autre ; la sélection d'une reconstitution peut donc varier, ce que l'auteur voit puisque les lignes et leurs articles sont affichés.
- Les nombres écrits en lettres (« quatre milliards ») restent à lire par une règle avant A2-2, pour ne plus mettre « à vérifier » une ligne juste.
- Le pilote automatique (perspective, ADR-0041) pourra partir d'une question enregistrée et suivre le même chemin, sans rien publier que l'auteur n'ait explicitement autorisé.

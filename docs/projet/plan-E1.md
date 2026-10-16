# Plan d'É1 — Tranche verticale personnelle

| | |
|---|---|
| Statut | **Validé** par Joël le 2026-10-16 (réponses du §7) |
| Date | 2026-10-16 |
| Origine | `ROADMAP.md` §5.2 et annexe B.2 ; décision P1 (`docs/projet/P1.md`) ; demandes de Joël du 2026-10-16 |
| Backlog | `docs/projet/backlog-E1.csv` |

## 1. Objet et principes

**Objet** (`ROADMAP.md` §5.2) : le plus petit produit qui rende un service réel à Joël lui-même. Il est construit sur les fondations définitives : on ne jette rien, on ne contourne rien.

`Sources RSS → tri → brief (avec apport propre) → brouillon sourcé → contrôles → relecture → « préparer et copier » vers son site → instantané et archive`

**Principes retenus** (décisions de Joël) :

1. **Utilisable le plus tôt possible.** É1 est découpée en **incréments**. Chacun se termine par quelque chose que Joël peut réellement utiliser sur son instance. Les fondations ne sont construites que dans la mesure où l'incrément suivant en a besoin, mais toujours sous leur forme définitive.
2. **La qualité avant l'optimisation** (ADR-0025). Un composant qui apporte une valeur démontrée est gardé, même s'il coûte de la mémoire ou du CPU. La mémoire de la pile complète, mesurée, fait foi.
3. **Le fournisseur et le modèle d'IA sont choisis par l'utilisateur final** (ADR-0027). Les profils sont rattachés à l'utilisateur dans le modèle de données ; l'administrateur ne fait qu'autoriser ou bloquer les fournisseurs. Les fournisseurs payants restent bloqués par défaut.
4. **L'agent local consultatif est une piste à évaluer.** Une évaluation courte est prévue (P05) ; il ne publie jamais et ne contourne aucune validation.
5. **Le NAS est la référence basse, pas la référence recommandée** (§3).
6. **Protocole des preuves inchangé** (ADR-0018) : toute mesure à seuil a son rapport fusionné avant de commencer.

**Condition d'exploitation** (`ROADMAP.md` §5.2) : instance **non exposée publiquement**, joignable seulement par réseau privé ou derrière un proxy d'authentification, avec un seul utilisateur. Les parcours de compte complets (ASVS niveau 2) arrivent en É2.

## 2. Trois natures de travail

Chaque tâche du backlog porte l'une de ces natures, demandées par Joël, ou la nature P pour les mesures.

| Nature | Définition | Heures centrales | Part |
|---|---|---|---|
| **F — Fondations techniques** | Invisible à l'écran, mais exigé par la sûreté, l'isolation, la fiabilité ou la reprise : données, identité, tâches, passerelle, PDP, audit, sauvegarde | 202 h | 31 % |
| **U — Fonctionnalités visibles** | Ce que l'utilisateur fait avec le produit : sources, veille, brief, rédaction, garde-fous, traçabilité, copie | 293 h | 45 % |
| **X — Expérience utilisateur** | La manière dont il le fait : coquille, accueil, tri, éditeur, bibliothèque, réglages, textes d'interface | 140 h | 21 % |
| **P — Preuves et mesures** | Points ouverts d'É0 et mesures sur les deux références | 22 h | 3 % |
| **Total** | | **657 h** | |

Les estimations reprennent l'annexe B.2 de la roadmap (640 h en valeur centrale). S'y ajoutent les points ouverts d'É0 : remesures sur corpus réel, mémoire de la pile, VPS, agent local et nettoyeur de collage.

## 3. Deux environnements

| | **Référence basse** | **Référence de travail** |
|---|---|---|
| Machine | VM sur le NAS : `192.168.129.249`, 2 vCPU sans AVX, 3,8 Go | VM sur le PC de Joël : `192.168.129.252`, 8 vCPU, 16 Go, 79 Go |
| Rôle | Configuration minimale démontrée : **viabilité minimale** | Développement quotidien, essais, mesures longues, IA locale |
| Toujours là | Sauf panne ou restauration d'instantané | **Seulement quand le PC de Joël est allumé** |
| Ce qui y tourne obligatoirement | Les critères de sortie d'É1 qui portent sur le profil minimal : parcours complet, mémoire de la pile complète (P03), garde-fous mesurés. Un passage de vérification à la fin de chaque incrément | — |
| Ce qui y tourne de préférence | — | Tout le reste : construction, essais d'intégration, Ollama, corpus réels, calibrations |

**Règle de validité.** Une preuve dont le rapport désigne la référence basse s'y mesure, et son verdict reste celui-là. Une mesure faite sur la référence de travail est toujours étiquetée comme telle, et ne remplace jamais une mesure sur la référence basse. Quand les deux existent, les deux sont rapportées. L'écart entre elles est une information utile : il dit ce que coûte le matériel minimal.

**Disponibilité.** La référence de travail s'éteint avec le PC de Joël. Les traitements longs n'y sont lancés que si Joël a prévu de laisser le PC allumé. Sinon, ils vont sur le NAS, ou ils attendent.

## 4. Incréments

Chaque incrément se termine par une **démonstration à Joël** sur son instance, puis par le passage de vérification sur la référence basse. Les durées sont en heures journalisées, à la vélocité prudente de 2,4 (décision D1 de P1). Le calendrier dépend surtout du rythme des sessions et des fusions.

| Incrément | Ce que Joël peut faire à la fin | Tâches | Heures estimées | Heures journalisées (÷ 2,4) | Cumul |
|---|---|---|---|---|---|
| **I0 Socle produit** | Se connecter à son instance, vide mais réelle | F01 à F04, X01 | 115 | 48 | 48 |
| **I1 Lire** | **Utiliser Otlet comme lecteur de veille** : ajouter ses flux RSS, trier, chercher, définir ses sujets. C'est la **première fonctionnalité réellement utilisable** | U01, U02, X02, P01 | 127 | 53 | 101 |
| **I2 Rédiger** | Construire un brief sur des éléments triés, choisir son modèle, obtenir un brouillon sourcé, le retoucher dans l'éditeur ; ses données sont sauvegardées et restaurables | F05, U03, U04, X03, F08 | 174 | 73 | 174 |
| **I3 Contrôler et copier** | Faire passer les garde-fous, publier sur son site par « préparer et copier », retrouver l'article et ses sources dans la bibliothèque | U05, U06, U07, X04, P02 | 164 | 68 | 242 |
| **I4 Fiabiliser** | Les mêmes gestes, avec automatisations encadrées, journal d'audit et réglages complets | F06, F07, X05, P03 à P05 | 77 | 32 | 274 |

Pourquoi cet ordre :

- **I1 vient avant la passerelle IA.** Un lecteur de veille qui trie et cherche rend déjà service, et il alimente le corpus réel dont dépendent les remesures de S1 et de S5.
- **L'identité d'I0 est minimale**, mais définitive : compte administrateur, Argon2id, sessions serveur, CSRF. Le modèle à identités multiples est posé dès le départ.
- **I4 regroupe les fondations qui ne bloquent aucun geste.** Le PDP et le journal d'audit encadrent l'automatisation. Avant I4, aucune automatisation ne publie : la seule sortie d'I3 est « préparer et copier », un geste manuel, ce qui respecte la règle « aucune publication automatique sans activation explicite ».
- **La sauvegarde est avancée à I2** (réponse de Joël, §7) : il rédigera de vrais articles dès I2, qui doivent donc être sauvegardés et restaurables avant d'avoir de la valeur.

## 5. Backlog

Le détail, avec un « fini quand » vérifiable pour chaque tâche, est dans `docs/projet/backlog-E1.csv`. En résumé :

| ID | Nature | Tâche | h |
|---|---|---|---|
| F01 | F | Modèle de données : espaces, comptes à identités multiples, colonne d'espace, RLS forcée, migrations | 25 |
| F02 | F | Identité minimale : compte administrateur, Argon2id, sessions serveur, CSRF, limitation de débit, ré-authentification | 25 |
| F03 | F | Isolation : « sans contexte = zéro ligne » étendu à l'API, base des tests d'isolation | 15 |
| F04 | F | Tâches et planificateur (ADR-0022), relance des tâches bloquées | 25 |
| X01 | X | Coquille de l'interface : connexion, navigation, mise en page, clés de traduction FR | 25 |
| U01 | U | Sources RSS : ajout, collecte planifiée, protection SSRF, robots.txt et TDMRep, statut juridique visible, saisie manuelle encadrée | 55 |
| U02 | U | Veille : sujets, dédoublonnage, score lexical explicable, recherche (classement borné, ADR-0021) | 38 |
| X02 | X | Flux de tri et parcours d'accueil (FA §7.7) | 30 |
| P01 | P | Remesure de la recherche plein texte sur corpus réel (ADR-0021) | 4 |
| F05 | F | Passerelle IA de production : adaptateur compatible, tableau des modèles, budgets à réservation, secrets, **profils par utilisateur** | 42 |
| U03 | U | Brief : éléments triés, « angle et apport propre » (M-19), choix du modèle par l'utilisateur | 20 |
| U04 | U | Rédaction : document structuré, origine par bloc, versions, modèles de prompt, schéma énumératif (ADR-0027) | 42 |
| X03 | X | Éditeur Tiptap : nœuds du projet, concordance en CI, nettoyeur de collage (ADR-0023) | 45 |
| F08 | F | Sauvegarde automatique, restauration testée en CI | 25 |
| U05 | U | Garde-fous : similarité potion int8 inter-langues bloquante, volet lexical par plus longue séquence commune, citations mot pour mot, mots interdits | 50 |
| U06 | U | Traçabilité : archives de sources, instantanés au rendu figé, bloc Sources, mention IA, rendu Python | 68 |
| U07 | U | « Préparer et copier », export | 20 |
| X04 | X | Bibliothèque d'articles : états, versions, instantanés, sources | 20 |
| P02 | P | Remesure des seuils de similarité sur corpus réel, calibration du volet lexical (ADR-0024) | 6 |
| F06 | F | PDP point unique, niveaux 0 à 2, tests de propriétés | 25 |
| F07 | F | Journal d'audit chaîné | 20 |
| X05 | X | Réglages essentiels : fournisseurs et modèles de l'utilisateur, budgets, sources, compte | 20 |
| P03 | P | Mémoire de la pile complète avec potion, sur la référence basse (S5b) | 3 |
| P04 | P | Installation chronométrée sur machine vierge (critère 6 d'É0, D2) | 3 |
| P05 | P | Évaluation courte de l'agent local consultatif | 6 |

## 6. Critères de sortie d'É1

Les critères de `ROADMAP.md` §5.2 sont repris, et l'environnement de chacun est précisé.

| # | Critère | Où |
|---|---|---|
| 1 | Parcours complet du §1 réalisé sur l'instance de Joël | **Référence basse** (profil minimal), et sur la référence de travail pour l'usage quotidien |
| 2 | « Requête sans contexte = zéro ligne » et tests d'isolation de l'API verts ; tests de propriétés du PDP verts pour les niveaux 0 à 2 | CI |
| 3 | Restauration de sauvegarde testée en CI | CI |
| 4 | Chaque contenu copié a son instantané et ses archives de sources | Référence de travail, vérifié sur la référence basse |
| 5 | Garde-fous de similarité, dont l'inter-langues, bloquants et calibrés selon S5, puis remesurés sur corpus réel (P02) | Mesure sur la **référence basse** ; calibration sur la référence de travail |
| 6 | Mémoire de la pile complète mesurée, sous 3,4 Go ou, à défaut, décision de Joël selon ADR-0025 (P03) | **Référence basse** |
| 7 | Installation chronométrée sur machine vierge (P04, critère 6 d'É0) | VM vierge sur le PC de Joël, Ubuntu 26.04 (§7, question 2) ; critère noté « VPS non démontré » |
| 8 | **Critère d'usage** : Joël se sert d'Otlet pour ses propres articles **au moins deux fois par semaine pendant six semaines** (CA7) | Son instance |

## 7. Décisions de Joël (2026-10-16)

1. **Plan** : le découpage en incréments et l'ordre I0 à I4 sont validés tels quels.
2. **P04, machine vierge** : l'installation est rejouée sur une **VM vierge créée sur le PC de Joël**, sans dépense. Ce n'est pas un VPS : le critère reste noté « VPS non démontré ». La VM a le profil minimal documenté : 2 vCPU, 4 Go de mémoire, 40 Go de disque. Son système est **Ubuntu 26.04 LTS**, la LTS qu'un nouvel utilisateur prendrait aujourd'hui. Joël installe la version Desktop, plus simple à gérer pour lui. L'interface graphique est donc désactivée pendant la mesure (`systemctl set-default multi-user.target`), puis rétablie. Un instantané pris juste après l'installation garde la machine vierge jusqu'à la mesure. Si l'installation réussit sur 26.04, cette version est ajoutée à `docs/exploitation/installation.md`.
3. **Sauvegarde** : elle est avancée à **I2** (F08), parce que Joël rédigera de vrais articles dès I2.
4. **Temps de Joël** : il est journalisé dans `docs/projet/journal-temps.csv` (domaine `projet`), avec une ligne par semaine et son estimation grossière, pour que la vélocité de P2 soit juste.

## 8. Règles de travail inchangées

Une branche par tâche, commits signés DCO en français, code en anglais. Joël fusionne. Heures journalisées par Claude à la fin de chaque tâche. Aucune dépense, aucun service externe ni logiciel système sans l'accord de Joël. `docs/projet/ETAT_DU_PROJET.md` est tenu à jour à chaque fin d'incrément.

# Plan d'exécution — Étape É0 (preuves de concept et socle)

| | |
|---|---|
| Statut | En vigueur depuis P0 (2026-10-11) ; dépôt créé, commit initial `e0b203d` |
| Source | `ROADMAP.md` v1.0 §5.1, annexe B.1, §10, §13 ; `RISKS.md` v1.0 §8, §11.2 ; `TECH_CHOICES.md` v1.0 §21, §25 |
| Effort | **248 h** de fonctions au plafond des preuves (enveloppe roadmap : 180 à 260 h, central 220 h) |
| Fichiers du premier commit | `/mnt/project-files/repo-bootstrap/` |

Ce document n'ajoute aucune décision de conception. Il ordonne et découpe ce que la roadmap a validé. Les seuils des preuves sont ceux de `ROADMAP.md` §5.1 ; ils ne sont pas recopiés ici.

---

## 1. À trancher avant le premier commit

| # | Question | Défaut retenu si rien n'est dit |
|---|---|---|
| **P0-a** | Nom du projet | **Tranché le 2026-10-11 : Otlet** (dépôt `otlet`, paquet Python `otlet`), sous réserve des vérifications TMview et WIPO faites par Joël. Justification : `IDENTITE_DECISION_FINALE.md` |
| **P0-b** | Forge et intégration continue | **Tranché le 2026-10-11 : GitHub + GitHub Actions** (minutes gratuites pour un dépôt public, conteneurs de service PostgreSQL, signalement privé de vulnérabilités, visibilité pour d'éventuels contributeurs). Alternative : Codeberg + Forgejo Actions (forge libre, capacité d'intégration continue plus limitée). Sortie peu coûteuse dans les deux sens : Git + fichiers YAML. ADR-0015 |
| **P0-c** | Date de M0 (PP1) | **Lundi 12 octobre 2026**. P1 visé fin février 2027 (central), entre mi-janvier et mi-avril 2027 |
| **P0-d** | Variante de licence | **AGPL-3.0-or-later** : sans accord de cession (DCO seulement), c'est la seule façon de pouvoir passer un jour à une version ultérieure de l'AGPL sans l'accord de chaque contributeur. ADR-0013 |

---

## 2. Ordre exact des preuves S1 à S7

L'ordre validé par la roadmap est conservé : **S6 → S1 → S2 → S3 → S5 → S4 → S7**. Ce plan fixe seulement où s'insèrent les tâches du socle et les prérequis externes.

| Rang | Bloc | Tâches | Heures | Cumul | Semaines actives* | Pourquoi à ce rang |
|---|---|---|---|---|---|---|
| 1 | Démarrage du socle | B01 à B07 | 27 | 27 | 1 à 2 | L'intégration continue et `import-linter` doivent exister avant la première ligne de code produit (RISKS §4.15) |
| 2 | **S6** Squelette de livraison | B08, S6.1 à S6.6 | 4 + 24 | 55 | 3 à 4 | L'image, Compose et la base servent à toutes les autres preuves |
| 3 | **S1** Charge PostgreSQL et RLS | B09, S1.1 à S1.5 | 5 + 24 | 84 | 5 à 7 | Le schéma, les rôles et la RLS de S1 sont réutilisés par S2 (V8) ; même VPS que S6 |
| 4 | **S2** File de tâches | S2.1 à S2.6 | 24 | 108 | 7 à 9 | A besoin de la RLS de S1 ; la file sert ensuite de cadre aux tests de pannes de S4 et S7 |
| 5 | **S3** Format de document | S3.1 à S3.7 | 32 | 140 | 9 à 11 | Monte les WordPress et Ghost locaux que S7 réutilise ; S7 a besoin du format |
| 6 | Pause « socle » | B10 | 6 | 146 | 12 | Liste ASVS ; sans dépendance, placée ici pour couper deux preuves longues |
| 7 | **S5** Similarité | S5.1 à S5.6 | 32 | 178 | 12 à 14 | Indépendante ; avant S4 pour que S4 n'attende pas la construction du corpus |
| 8 | **S4** Passerelle IA | S4.1 à S4.6 | 24 | 202 | 14 à 16 | Indépendante ; ses clés de fournisseurs sont prises en rang 5 |
| 9 | **S7** Connecteurs CMS | S7.1 à S7.7 | 40 | 242 | 16 à 19 | Réutilise le format de S3, le squelette de S6 et l'hébergement mutualisé commandé en rang 5 |
| 10 | Clôture | B11 | 6 | 248 | 19 | Vélocité, recalibrage, rapport P1 |

\* À environ 13 h de fonctions par semaine (17,5 h brutes × 75 %, ROADMAP §2.2). Au plafond de toutes les preuves, É0 dure donc environ 19 semaines actives, soit 5 mois ; le central de la roadmap (4,4 mois, 220 h) suppose que certaines preuves concluent avant leur plafond.

**Règles d'enchaînement**

1. Une preuve commence quand la précédente a son rapport **conclu** (succès, échec ou partiel), ou quand elle a atteint sa durée maximale.
2. Un échec ou une contradiction avec un document validé ne bloque pas la preuve suivante : il ouvre un ADR « proposé » soumis à Joël, et le travail continue. Seule exception : un échec de S3 suspend S7 jusqu'à la décision de Joël sur TC-07.
3. Les attentes machine (un banc qui tourne une nuit) peuvent recouvrir la préparation de la preuve suivante ; le travail humain, non.

**Prérequis externes** (temps « projet », hors des 248 h ; montants estimés, non vérifiés)

| ID | Prérequis | Avant | Coût indicatif |
|---|---|---|---|
| A1 | VPS vierge 2 vCPU / 4 Go, détruit et recréé pour la mesure d'installation de S6 | S6 | 5 à 10 € par mois, environ 5 mois |
| A2 | Hébergement mutualisé avec WordPress et une extension de sécurité (ou un hébergement déjà disponible chez Joël) | Commande au rang 5, utilisé en S7 | 0 à 5 € par mois, 2 mois |
| A3 | Clés de fournisseurs IA avec plafond de dépense : Anthropic (payant), Groq ou OpenRouter (offres gratuites), Ollama sur l'ordinateur de Joël | S4 | 10 à 20 € au total |

Total estimé pour É0 : **50 à 100 €** à la charge de Joël. Sans ce budget, S6 et S1 peuvent être mesurés sur une machine locale bridée à 2 vCPU / 4 Go, au prix d'un critère « VPS vierge » non démontré.

---

## 3. Structure du dépôt Git

Un seul dépôt public (monodépôt). En gras, ce qui existe à la fin d'É0 ; le reste est créé en É1, module par module.

```text
otlet/
├── README.md  LICENSE  DCO  CONTRIBUTING.md  SECURITY.md
├── .editorconfig  .gitattributes  .gitignore
├── .github/                     CI, robot de mises à jour, modèle de PR      (B04, B06)
├── backend/
│   ├── pyproject.toml  uv.lock  .importlinter                               (B02, B03)
│   ├── migrations/              Alembic                                     (S6)
│   ├── src/otlet/
│   │   ├── platform/            config, journaux, fabrique de sessions avec contexte d'espace (S6, S1)
│   │   ├── entrypoints/         api/ (FastAPI), worker/, scheduler/, cli/    (S6)
│   │   ├── jobs/                module Tâches, promu depuis S2               (fin S2, réécrit avec tests)
│   │   └── <module>/            É1 : identity, workspaces, audit, sources, monitoring,
│   │       ├── domain/               drafting, guardrails, traceability, publishing,
│   │       ├── application/          ai_gateway, automation…
│   │       └── adapters/
│   └── tests/                   unit/, integration/ (PostgreSQL réel), architecture/
├── frontend/                    Vite + React + TypeScript strict             (B08)
├── deploy/                      Containerfile, compose.yaml, Caddyfile, .env.example (S6)
├── spikes/                      code jetable des preuves : s1-postgres/, s2-queue/, s3-document/,
│                                s4-ai-gateway/, s5-similarity/, s7-cms/, bench/ (B09)
├── tools/                       journal_temps.py et outils du mainteneur
└── docs/
    ├── design/                  les six documents de conception, figés en v1.0
    ├── adr/                     README.md (index), 0000-modele.md, 0012-…
    ├── spikes/                  MODELE.md, S1.md … S7.md (rapports)
    ├── security/                asvs-l2.md                                   (B10)
    └── projet/                  plan-E0.md, backlog-E0.csv, journal-temps.csv, journal-temps.md
```

**Règles** (détail dans ADR-0014)

- **Code en anglais** (identifiants, commentaires), **documentation et messages de commit en français** jusqu'au lot 1b ; README bilingue.
- **Le code des preuves vit dans `spikes/`** et n'est jamais importé par `backend/` (contrat `import-linter`). Ce qui est conservé est **réécrit** dans `backend/` avec ses tests. Seule S6 produit directement du code définitif (squelette, `deploy/`, `platform/`, `entrypoints/`).
- Le dossier `spikes/` n'a ni typage strict ni couverture exigés ; il doit seulement s'exécuter et être reproductible (commande unique documentée dans le rapport).
- `docs/design/` ne se réécrit plus (PP9) : toute modification passe par un ADR qui cite la section concernée.

---

## 4. ADR initiaux

La numérotation continue celle d'`ARCHITECTURE.md` (ADR-01 à ADR-11), pour éviter deux « ADR-03 ». Les décisions DT, DR et DRM restent dans leurs documents et sont indexées dans `docs/adr/README.md`. Modèle : `docs/adr/0000-modele.md`.

| ADR | Titre | Statut au premier commit | Contenu |
|---|---|---|---|
| **0012** | Décisions consignées dans le dépôt | Accepté | Documents de conception figés en v1.0 ; toute modification par ADR (PP9) ; qui accepte (Joël) ; cycle proposé → accepté → remplacé |
| **0013** | Licence AGPL-3.0-or-later et DCO | Accepté (sous réserve de P0-d) | Licence, en-têtes SPDX, signature `Signed-off-by` obligatoire et vérifiée en CI, pas d'accord de cession |
| **0014** | Structure du dépôt et isolement des preuves | Accepté | Arborescence du §3, langue du code, règles de `spikes/` |
| **0015** | Forge et intégration continue | Accepté selon P0-b | GitHub + Actions, branche `main` protégée, CI obligatoire avant fusion, même pour le mainteneur |
| **0016** | Chaîne d'outils | Proposé, accepté en B02 | Python 3.13, `uv`, `ruff`, `mypy --strict`, `pytest`, `hypothesis` ; Node LTS, `npm`, ESLint ; PostgreSQL 18 + `pgvector` |
| **0017** | Contrats d'imports | Proposé, accepté en B03 | Domaine sans FastAPI, SQLAlchemy, psycopg, httpx ni SDK IA ; couches `adapters → application → domain` ; seul `ai_gateway` importe `openai` et `anthropic` (MD4) ; seul `publishing` charge les connecteurs (MD3) ; `entrypoints` au sommet ; zéro exception |
| **0018** | Protocole des preuves de concept | Accepté | Seuils figés par un commit du rapport **avant** toute mesure ; durée maximale stricte suivie au journal ; conclusion obligatoire ; contradiction ⇒ ADR proposé à Joël |

ADR attendus pendant É0 (un par preuve dont la conclusion confirme ou modifie un choix) : file de tâches (S2), format et éditeur (S3), modèle d'embeddings et seuils (S5), protocole de passerelle (S4), stratégie d'idempotence CMS et « WordPress d'abord » (S7), séparation des secrets (S6), profil mémoire solo (S1).

---

## 5. Backlog É0

Estimations en heures de fonctions. Les tâches de preuve sont chiffrées **à leur part de la durée maximale** : une preuve qui conclut plus tôt s'arrête, elle ne remplit pas sa boîte. Chaque tâche a un « fini quand » vérifiable. Le backlog machine-lisible est `docs/projet/backlog-E0.csv`.

### 5.1 Socle (48 h)

| ID | Tâche | h | Dépend de | Fini quand |
|---|---|---|---|---|
| B01 | Créer le dépôt avec les fichiers d'amorçage ; protéger `main` ; activer le signalement privé de vulnérabilités | 3 | P0-a, P0-b | Premier commit signé visible ; une poussée directe sur `main` est refusée |
| B02 | Projet Python : `backend/pyproject.toml`, `uv`, Python 3.13, `ruff`, `mypy --strict`, `pytest`, crochets de pré-commit ; ADR-0016 accepté | 4 | B01 | `uv run pytest` passe sur un test trivial ; `mypy --strict` vert |
| B03 | Contrats `import-linter` de l'ADR-0017 ; un test qui introduit une violation et vérifie qu'elle est rejetée | 4 | B02 | Contrats verts ; la violation volontaire fait échouer la commande |
| B04 | CI : lint, types, tests, `import-linter`, vérification DCO, cache `uv` ; toute vérification bloquante | 5 | B03 | PR de test refusée sans `Signed-off-by` et sur violation d'import |
| B05 | CI : PostgreSQL 18 + `pgvector` éphémère ; fixture `pytest` ; rôles propriétaire, migration et applicatif séparés (M-12) | 4 | B04 | Un test d'intégration se connecte avec le rôle applicatif, qui ne peut pas créer de table |
| B06 | Chaîne d'approvisionnement : verrous à empreintes, robot de mises à jour avec quarantaine de 7 jours, `pip-audit`, `npm audit` | 4 | B04 | Le robot ouvre ses PR ; un audit en échec bloque la CI |
| B07 | Contrôle automatique des licences des dépendances (liste de TECH_CHOICES §1.1) | 3 | B06 | Une dépendance sous SSPL ajoutée en test fait échouer la CI |
| B08 | Interface : Vite + React + TypeScript strict + ESLint ; construction en CI | 4 | B04 | `npm run build` produit les fichiers statiques en CI |
| B09 | Banc de mesure commun `spikes/bench/` : chronométrage, p50/p95, mémoire par conteneur, sortie JSON, exécution distante sur le VPS | 5 | S6 | Une mesure de `/health` sur le VPS produit un JSON versionné |
| B10 | Liste de contrôle ASVS 5.0 niveau 2 restreinte au périmètre du lot 1, dans `docs/security/asvs-l2.md` | 6 | — | Chaque exigence a un statut (applicable, non applicable, lot) et un module responsable |
| B11 | Clôture : vélocité mesurée, projection CA4, ré-estimation d'É1, revue du registre des risques (ROADMAP §8.5), rapport P1 soumis à Joël | 6 | Tout | Rapport `docs/projet/P1.md` soumis ; voir §7 |

### 5.2 S6 — Squelette de livraison (24 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S6.1 | Rapport ouvert : question, seuils, protocole de la mesure d'installation (commit avant mesure) | 2 | `docs/spikes/S6.md` commité |
| S6.2 | Image OCI multi-étape et multirôle (`api`, `worker`, `scheduler` par argument), interface construite dedans, utilisateur non root | 5 | L'image démarre les trois rôles ; Node absent de l'image finale |
| S6.3 | `compose.yaml` solo (Caddy, application, worker, PostgreSQL), `Caddyfile`, contrôles de santé, `.env.example` | 4 | `docker compose up` sert l'interface et `/health` en HTTPS local |
| S6.4 | FastAPI minimal, première migration Alembic, mise à jour avec migration et retour arrière documentés | 4 | Montée puis descente de version jouées en CI |
| S6.5 | Secrets chiffrés par clé publique côté API, déchiffrés par le worker seul (DR6) | 5 | Un test démontre que le processus API ne peut pas déchiffrer ; la clé privée n'est pas montée dans le conteneur API |
| S6.6 | Installation chronométrée sur VPS vierge en suivant la documentation ; rapport conclu | 4 | Durée mesurée (cible ≤ 15 min) ; rapport conclu |

### 5.3 S1 — Charge PostgreSQL et RLS (24 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S1.1 | Rapport ouvert ; schéma minimal couvrant les cinq lectures ; trois rôles séparés | 4 | Rapport commité, schéma migré |
| S1.2 | Générateur du jeu synthétique (200 sources, 100 000 éléments, 300 000 passages vectorisés, 2 000 articles), reproductible par graine | 5 | Jeu chargé sur le VPS en une commande |
| S1.3 | RLS forcée, `SET LOCAL` par la fabrique de sessions, test « requête sans contexte = zéro ligne » | 4 | Test vert en CI |
| S1.4 | Mesures p95 des cinq lectures avec et sans RLS, mémoire de la pile sous charge | 7 | JSON de mesures versionnés |
| S1.5 | Analyse et conclusion ; ADR du profil solo si un seuil change | 4 | Rapport conclu |

### 5.4 S2 — File de tâches (24 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S2.1 | Rapport ouvert ; banc de tâches à clé d'idempotence avec compteur d'effets | 4 | Rapport commité |
| S2.2 | Procrastinate : enfilage dans la transaction SQLAlchemy, 100 annulations | 4 | 0 tâche sur 100 ou échec documenté |
| S2.3 | Procrastinate : 1 000 tâches, arrêts brutaux aléatoires du worker, reprise, annulation ciblée | 6 | Pertes, doubles effets et délai de reprise mesurés |
| S2.4 | Procrastinate sous RLS avec `SET LOCAL` (V8) | 3 | Comportement établi et testé |
| S2.5 | DBOS : mêmes scénarios, au besoin réduits | 5 | Tableau comparatif rempli |
| S2.6 | Conclusion, ADR de la file | 2 | Rapport conclu, ADR proposé ou accepté |

### 5.5 S3 — Format de document et éditeur (32 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S3.1 | Rapport ouvert ; corpus de 30 documents (10 collés depuis Word et Google Docs, 10 sorties IA en Markdown restreint, 10 rédigés) | 5 | Corpus versionné sous licence libre |
| S3.2 | Schéma « Document plateforme v1 » en ébauche, avec nœuds obligatoires (bloc Sources, mention IA) | 5 | Schéma JSON publié dans `spikes/` |
| S3.3 | Rendu Python JSON → HTML ; conversion Markdown restreint → JSON | 6 | Corpus rendu sans erreur |
| S3.4 | Éditeur Tiptap minimal : collage, export JSON ; test de concordance rendu Python / rendu éditeur | 7 | Taux de concordance mesuré |
| S3.5 | BlockNote sur le même corpus, comparaison courte | 3 | Comparaison écrite |
| S3.6 | WordPress et Ghost en conteneurs locaux ; aller-retour et contrôle des éléments obligatoires | 4 | Taux de conservation mesuré par élément |
| S3.7 | Conclusion, décision Tiptap ou BlockNote, ADR | 2 | Rapport conclu |

### 5.6 S5 — Similarité et embeddings (32 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S5.1 | Rapport ouvert ; définitions de « quasi-copie » et « traduction détectée » | 2 | Rapport commité |
| S5.2 | Corpus de 200 paires FR / EN sous licence libre (50 traductions, 50 paraphrases, 100 indépendants), réutilisable par M-14 | 8 | Corpus et sa licence versionnés |
| S5.3 | `fastembed` : deux ou trois modèles multilingues compacts ; mémoire et débit sur 2 vCPU | 6 | Mémoire et débit mesurés par modèle |
| S5.4 | Volet lexical : n-grammes, MinHash / LSH, `rapidfuzz` | 5 | Détection des quasi-copies de même langue mesurée |
| S5.5 | Calibration des seuils, courbes rappel / faux positifs, seuils inter-langues (DR4) | 7 | Seuils retenus avec leurs taux |
| S5.6 | Conclusion ; ADR du modèle et des seuils ; DR4 confirmé ou soumis à Joël | 4 | Rapport conclu |

### 5.7 S4 — Passerelle IA (24 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S4.1 | Rapport ouvert ; 50 briefs ; schéma de sortie structurée ; plafonds de dépense posés chez chaque fournisseur | 4 | Rapport commité |
| S4.2 | Port de passerelle et adaptateur générique compatible OpenAI (Ollama, Groq ou OpenRouter) | 6 | Un appel structuré réussit sur deux fournisseurs |
| S4.3 | Adaptateur Anthropic natif | 3 | Même appel réussi |
| S4.4 | Validation et réparation unique ; 50 briefs × 4 fournisseurs | 4 | Taux de sorties valides par fournisseur |
| S4.5 | Budget à réservation sur 200 appels concurrents (faux fournisseur) ; replis sur 429 et 5xx simulés | 5 | Dépassement nul démontré ; replis testés |
| S4.6 | Conclusion ; profils « testés » et « non testés » ; ADR | 2 | Rapport conclu |

### 5.8 S7 — Connecteurs CMS (40 h)

| ID | Tâche | h | Fini quand |
|---|---|---|---|
| S7.1 | Rapport ouvert ; quatre environnements : WordPress récent, WordPress version majeure précédente, WordPress mutualisé avec extension de sécurité (A2), Ghost | 6 | Les quatre répondent à l'API |
| S7.2 | Vérification de V1, V2, V3 (RISKS §11.2) | 5 | Chaque point confirmé ou infirmé, avec preuve |
| S7.3 | Prototype WordPress : machine à états minimale, clé d'idempotence, rapprochement | 8 | Publication et rapprochement sur un cas nominal |
| S7.4 | Prototype Ghost : idem | 6 | Idem |
| S7.5 | Injecteur de pannes (délai dépassé après envoi, coupure) ; 100 publications par configuration | 7 | Doublons, taux de rapprochement et états « inconnu » mesurés |
| S7.6 | Extension WordPress compagnon facultative : évaluation courte | 4 | Recommandation écrite |
| S7.7 | Conclusion ; « WordPress d'abord » confirmé ou inversé ; ADR | 4 | Rapport conclu, décision soumise à Joël si inversion |

---

## 6. Journal de temps

Définition complète : `docs/projet/journal-temps.md` ; outil : `tools/journal_temps.py` (bibliothèque standard Python, aucune dépendance).

**Fichier** `docs/projet/journal-temps.csv`, **une ligne par tâche terminée**, avec une estimation grossière des heures passées (décision de Joël du 2026-10-11 : pas de saisie par session). Colonnes inchangées : `date` (fin de la tâche), `heures`, `domaine`, `etape`, `tache`, `note`.

| Domaine | Contenu | Critères alimentés |
|---|---|---|
| `preuve` | Tâches S1 à S7 | CA1, vélocité |
| `fonction` | Tâches du socle (B01 à B11) | CA1, vélocité |
| `compte` | Parcours de compte ; vide en É0 | CA5 |
| `entretien` | Facultatif : un gros chantier d'entretien noté comme une tâche | CA6 (indicatif) |

**Ce qui reste mesuré** : heures réelles contre estimation par tâche, cumul d'É0 face aux seuils de CA1 (alerte à **275 h**, réduction à **330 h**, soit +25 % et +50 % du central de 220 h), vélocité.

**Ce qui devient un jugement de Joël** : CA2 et CA3 (heures hebdomadaires trop basses ou au-delà du plafond de 20 h) et la part « entretien » de CA6. Ils ne sont plus calculés ; Joël les signale lui-même à chaque point de décision.

**Rituel** : à chaque tâche terminée, une ligne ; `python tools/journal_temps.py` affiche le cumul, les écarts et la vélocité.

**Vélocité** pour P1 = somme des estimations des tâches terminées ÷ somme des heures réelles passées dessus. Une tâche est terminée quand son « fini quand » est vrai ; le statut se tient dans `docs/projet/backlog-E0.csv`.

Le journal est public avec le dépôt (une durée par tâche, jamais d'horaires). Si Joël préfère le garder privé, il suffit de l'ajouter à `.gitignore` ; le script fonctionne pareil.

---

## 7. Premier commit recommandé

**Contenu** : fichiers de gouvernance et de documentation uniquement, aucun code produit. Le premier code (B02) arrive dans le commit suivant, avec ses contrats d'imports, ce qui tient l'exigence « `import-linter` bloquant dès le premier commit de code ».

```text
LICENSE                       texte intégral AGPL-3.0
DCO                           Developer Certificate of Origin 1.1
README.md                     présentation FR + EN, statut « pré-alpha, non destiné à la production »
CONTRIBUTING.md               signature DCO, ADR, conventions
SECURITY.md                   signalement privé, aucune version prise en charge
.gitignore .gitattributes .editorconfig
docs/design/                  les six documents validés, inchangés
docs/adr/                     README.md, 0000-modele.md, 0012 à 0018
docs/spikes/MODELE.md         gabarit de rapport de preuve
docs/projet/                  plan-E0.md (ce document), backlog-E0.csv, journal-temps.csv, journal-temps.md
tools/journal_temps.py
```

**Procédure** : `bash repo-bootstrap/amorcer-depot.sh` (testé à blanc) crée le dossier `otlet/`, y copie les documents de conception et ce plan, initialise Git sur `main` et crée le commit signé. Il ne pousse rien.

**Message** :

```text
Initialise le dépôt Otlet : licence, DCO, documents de conception validés, ADR initiaux

Documents de conception v1.0 validés le 2026-10-11 (point P0),
ADR-0012 à ADR-0018, gabarits de rapport de preuve, journal de temps.
Aucun code à ce stade.

Signed-off-by: Joël <adresse publique de commit>
```

La première ligne du journal de temps est la tâche B01 elle-même (`fonction`, heures estimées).

---

## 8. Critères de fin d'É0

É0 est terminée quand **tous** les points suivants sont vrais (PP3). Un point non atteint retient l'étape ; il n'est pas reporté.

| # | Critère | Vérification |
|---|---|---|
| 1 | S1 à S7 ont chacune un rapport `docs/spikes/Sx.md` au statut « conclu » (succès, échec ou partiel) | Fichiers sur `main` |
| 2 | Les seuils de chaque preuve ont été commités **avant** sa première mesure | Historique Git du rapport |
| 3 | Aucune preuve n'a dépassé sa durée maximale de plus de 10 % sans décision écrite de Joël | Journal de temps, par tâche |
| 4 | Toute contradiction avec un document validé a un ADR accepté par Joël ; aucun ADR d'É0 n'est encore « proposé » | `docs/adr/README.md` |
| 5 | CI verte sur `main` : lint, `mypy --strict`, tests avec PostgreSQL réel, `import-linter` sans aucune exception, DCO, audit des dépendances, licences, construction de l'interface | Dernière exécution de la CI |
| 6 | Le squelette de S6 est sur `main` et la documentation d'installation a été suivie sur un VPS vierge | Rapport S6 |
| 7 | La liste ASVS niveau 2 du lot 1 est versionnée | `docs/security/asvs-l2.md` |
| 8 | Chaque tâche terminée d'É0 a sa ligne d'heures au journal | `tools/journal_temps.py` : aucune tâche `fait` sans heures |
| 9 | Vélocité mesurée, projection CA4 calculée, estimation d'É1 recalibrée | `docs/projet/P1.md` |
| 10 | Revue du registre des risques faite ; risques touchés par les preuves recotés | Section dédiée de `P1.md` |
| 11 | Aucun code de fonction d'É1 n'a été écrit en dehors du squelette | Revue de `backend/src/` |
| 12 | Joël a pris la décision P1 : démarrer É1 tel quel, recalibré, ou avec réductions | Décision consignée dans `P1.md` |

**Garde-fou d'effort pendant É0** : à **275 h** de fonctions cumulées, alerte et ré-estimation du reste ; à **330 h**, application de la réduction suivante de la roadmap (CA1). Une preuve qui atteint sa durée maximale conclut avec ce qu'elle a mesuré.

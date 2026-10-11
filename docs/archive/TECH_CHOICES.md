# Choix technologiques — Plateforme Open Source de Veille et de Diffusion IA

| Champ | Valeur |
|---|---|
| Document | `TECH_CHOICES.md` |
| Version | 0.1 (brouillon pour validation) |
| Date | 2026-10-11 |
| Statut | À valider par Joël |
| Phase | Conception — aucun code |
| Documents d'entrée | `FUNCTIONAL_ANALYSIS.md` v0.2 (validée le 2026-10-11), `ARCHITECTURE.md` v0.1 (approuvée le 2026-10-11, DA1 à DA10 acceptés tels que proposés) |
| Documents suivants | `RISKS.md` (détaillé), `ROADMAP.md` |

**Historique**

| Version | Date | Changements |
|---|---|---|
| 0.1 | 2026-10-11 | Première version |

> Ce document choisit les **technologies** qui réalisent l'architecture approuvée. Il répond aux questions du §26 de `ARCHITECTURE.md` et aux quatre points de vigilance formulés par Joël lors de l'approbation : **seuil réel de validité d'ADR-02**, **place des agents dans les premiers lots**, **simplification UX de la Marque en mode solo**, **stratégie long terme du contrôle factuel**. Les pistes initiales (Next.js, FastAPI, PostgreSQL, Docker, IA multi-fournisseurs, cadre d'agents à déterminer) sont **évaluées comme des candidates parmi d'autres**, avec les mêmes critères ; trois sont retenues, une ne l'est pas pour l'application (Next.js, §6), et la dernière reçoit une réponse progressive (§12).

---

## Sommaire

1. [Méthode et critères](#1-méthode-et-critères)
2. [Synthèse des choix](#2-synthèse-des-choix)
3. [Contraintes transverses](#3-contraintes-transverses)
4. [Langage du back-end](#4-langage-du-back-end)
5. [Cadre Web, accès aux données et structure du back-end](#5-cadre-web-accès-aux-données-et-structure-du-back-end)
6. [Interface Web](#6-interface-web)
7. [Base de données](#7-base-de-données)
8. [Point de vigilance 1 — Seuil réel de validité d'ADR-02](#8-point-de-vigilance-1--seuil-réel-de-validité-dadr-02)
9. [File de tâches et planificateur](#9-file-de-tâches-et-planificateur)
10. [Format de document et éditeur](#10-format-de-document-et-éditeur)
11. [Passerelle IA](#11-passerelle-ia)
12. [Cadre d'agents et point de vigilance 2 — Place des agents dans les premiers lots](#12-cadre-dagents-et-point-de-vigilance-2--place-des-agents-dans-les-premiers-lots)
13. [Similarité, dédoublonnage et embeddings](#13-similarité-dédoublonnage-et-embeddings)
14. [Collecte et extraction](#14-collecte-et-extraction)
15. [Générateur de site](#15-générateur-de-site)
16. [Stockage de fichiers](#16-stockage-de-fichiers)
17. [Médias](#17-médias)
18. [Authentification](#18-authentification)
19. [Conteneurisation, proxy et livraison](#19-conteneurisation-proxy-et-livraison)
20. [Observabilité](#20-observabilité)
21. [Qualité, tests et chaîne d'approvisionnement](#21-qualité-tests-et-chaîne-dapprovisionnement)
22. [Point de vigilance 3 — Simplification UX de la Marque en mode solo](#22-point-de-vigilance-3--simplification-ux-de-la-marque-en-mode-solo)
23. [Point de vigilance 4 — Stratégie long terme du contrôle factuel](#23-point-de-vigilance-4--stratégie-long-terme-du-contrôle-factuel)
24. [Dépendances critiques et plans de sortie](#24-dépendances-critiques-et-plans-de-sortie)
25. [Preuves de concept au démarrage du lot 1](#25-preuves-de-concept-au-démarrage-du-lot-1)
26. [Registre des décisions techniques](#26-registre-des-décisions-techniques)
27. [Points à valider](#27-points-à-valider)

---

## 1. Méthode et critères

### 1.1 Critères

Les critères sont ceux du §26 de l'architecture, pondérés selon le classement des moteurs d'architecture (§2 de l'architecture : contrôle et sûreté, puis sécurité, fiabilité, traçabilité, extensibilité, simplicité d'exploitation, indépendance, performance).

| Code | Critère | Poids | Question posée |
|---|---|---|---|
| **K1** | Adéquation aux exigences | 5 | Couvre-t-il les exigences de l'architecture sans contorsion ? |
| **K2** | Maturité et pérennité | 4 | Âge, stabilité des versions, gouvernance (fondation, entreprise, mainteneur unique), probabilité d'être encore maintenu dans 10 ans |
| **K3** | Simplicité d'exploitation sur un petit VPS | 4 | Nombre de processus et de conteneurs, mémoire, sauvegarde, mises à jour |
| **K4** | Sécurité | 4 | Historique de vulnérabilités, surface d'attaque, réactivité des correctifs |
| **K5** | Écosystème | 3 | Bibliothèques disponibles pour l'IA, l'extraction Web, les images, l'édition riche |
| **K6** | Communauté et facilité de contribution | 3 | Nombre de contributeurs potentiels, courbe d'apprentissage, documentation |
| **K7** | Indépendance | 3 | Absence de dépendance à un éditeur ou à un service ; possibilité de remplacement |

**Filtre éliminatoire** (avant toute notation) : licence **compatible avec l'AGPL-3.0** (D2) pour tout ce qui est livré dans l'image ou chargé dans le processus. Sont compatibles : MIT, BSD, Apache-2.0, ISC, MPL-2.0, LGPL, GPL-3.0, AGPL-3.0, licence PostgreSQL. Sont **exclues** : licences à source disponible (SSPL, BSL, RSAL, « Elastic License »), licences propriétaires, GPL-2.0 « seule » pour du code lié dans le processus. Un service externe facultatif appelé par réseau (ex. une API de fournisseur IA) n'est pas soumis à ce filtre, mais ne doit jamais être obligatoire (CT-02).

### 1.2 Lecture des évaluations

- Les tableaux comparatifs notent les candidats de 1 (faible) à 5 (excellent) sur les critères pertinents ; le **total pondéré** n'est donné que lorsque les candidats sont réellement comparables. Une note est un jugement argumenté, pas une mesure ; les arguments sont donnés à côté.
- Chaque choix porte un **niveau de confiance** : **élevé** (choix sûr, réversible à faible coût ou très largement éprouvé), **moyen** (choix raisonnable, à confirmer par une preuve de concept, §25), **faible** (pari assumé, plan de sortie prévu).
- Les **versions** citées sont des planchers indicatifs ; les versions exactes seront verrouillées au démarrage du code.
- Les **seuils chiffrés** (§8) sont des ordres de grandeur issus de la pratique et de calculs de dimensionnement ; ils seront **calibrés** par les tests de charge de la preuve de concept S1.

---

## 2. Synthèse des choix

| Domaine | Choix recommandé | Repli identifié | Piste initiale | Confiance |
|---|---|---|---|---|
| Langage du back-end | **Python 3.12+** (typage statique vérifié) | TypeScript / Node.js | Python : **retenu** | Élevée |
| Cadre Web | **FastAPI** + Pydantic v2 | Litestar ; Django + Django Ninja | FastAPI : **retenu**, avec conditions (§5.2) | Moyenne |
| Accès aux données | **SQLAlchemy 2** + **Alembic** | — | — | Élevée |
| Interface Web | **Application monopage React + TypeScript, construite avec Vite**, servie en fichiers statiques | Vue 3 ; SvelteKit en mode statique | Next.js : **non retenu pour l'application** (§6) | Moyenne |
| Base de données | **PostgreSQL 18+** avec `pgvector`, `pg_trgm`, `unaccent` | — (aucune autre base supportée) | PostgreSQL : **retenu** | Élevée |
| File de tâches | **Module interne sur PostgreSQL** (`SKIP LOCKED`, baux, verrous consultatifs), derrière l'interface du module Tâches | Procrastinate ; DBOS Transact | — | Moyenne (S2) |
| Planificateur | **Intégré au module Tâches** (échéances en base, verrou de leader) | — | — | Élevée |
| Format de document | **Schéma ProseMirror publié et versionné** (JSON) | Portable Text | — | Moyenne (S3) |
| Éditeur | **Tiptap** (cœur MIT, extensions libres uniquement) | ProseMirror nu ; BlockNote | — | Moyenne (S3) |
| Passerelle IA | **Adaptateurs maison minces** sur les SDK officiels (`openai` pour le protocole compatible, `anthropic` en natif) | Pydantic AI comme couche d'adaptateurs | Multi-fournisseurs : **retenu** | Élevée |
| Cadre d'agents | **Aucun avant le lot 3** ; au lot 3, **Pydantic AI** à l'intérieur des étapes d'agent | Boucle d'outils maison | « À déterminer » : **tranché par lot** (§12) | Moyenne |
| Similarité, quasi-doublons | **MinHash / LSH** (`datasketch`), n-grammes, `rapidfuzz`, `pg_trgm` | `simhash` | — | Élevée |
| Embeddings locaux | **`fastembed`** (ONNX sur CPU), modèle multilingue compact | `sentence-transformers` | — | Moyenne (S5) |
| Extraction | **`trafilatura`**, `feedparser`, `httpx`, `protego`, `nh3`, `py3langid` | `readability-lxml` | — | Élevée |
| Générateur de site | **Intégré** : gabarits **Jinja2** + recherche statique **Pagefind** | Hugo (binaire externe) | — | Moyenne |
| Stockage | Interface interne, adaptateurs **disque local** et **compatible S3** | — | — | Élevée |
| Médias | **Pillow** (lot 2), **`c2pa-python`** pour la provenance, **FFmpeg** en sous-processus (lot 4) | `pyvips` | — | Moyenne |
| Authentification | **Implémentation propre sur bibliothèques éprouvées** : `argon2-cffi`, `pyotp`, `webauthn`, `Authlib` (OIDC) | Fournisseur d'identité externe via OIDC (lot 4) | — | Moyenne |
| Conteneurs | **Image OCI unique multirôle** + **fichier Compose** ; Docker Engine ou Podman | Installation sans conteneurs non supportée officiellement | Docker : **retenu** (sous forme « compatible OCI ») | Élevée |
| Proxy inverse | **Caddy** (TLS automatique) | Traefik ; proxy déjà présent | — | Élevée |
| Observabilité | **`structlog`** (JSON), **OpenTelemetry** (export facultatif), métriques Prometheus | — | — | Élevée |

**Conséquence globale** : l'installation solo reste à **4 conteneurs** (proxy, application, worker, base), avec **un seul environnement d'exécution** (Python) en production ; Node.js n'est utilisé qu'à la **construction** de l'interface, jamais à l'exécution.

---

## 3. Contraintes transverses

### 3.1 Un seul environnement d'exécution en production

L'architecture prévoit une image applicative unique (§20.2 de l'architecture). Chaque environnement d'exécution supplémentaire (Node.js, JVM, binaire Go) ajoute : un processus à surveiller, une chaîne de mises à jour de sécurité, de la mémoire, une compétence à maintenir. Pour un projet porté par peu de mainteneurs (R-O05) et installé par des non-experts (O9), **un seul environnement d'exécution** côté serveur est un objectif explicite de ce document. Il pèse dans le choix de l'interface (§6) et du générateur de site (§15).

### 3.2 Budget mémoire du profil solo

Cible : **2 vCPU, 4 Go de RAM**, sans IA locale (§1.2 de l'architecture). Répartition estimée, à vérifier par S1 :

| Composant | Mémoire estimée | Remarque |
|---|---|---|
| Système et Docker | 300 à 400 Mo | Debian ou Ubuntu minimal |
| Caddy | 30 à 60 Mo | |
| PostgreSQL | 1 à 1,5 Go | `shared_buffers` ≈ 512 Mo à 1 Go ; index vectoriel compris (§8.3) |
| Application (API, 2 processus) | 300 à 500 Mo | |
| Worker (toutes files + planificateur) | 400 à 900 Mo | Dont modèle d'embeddings local compact : 150 à 500 Mo selon le modèle |
| **Total** | **≈ 2,1 à 3,4 Go** | Marge de 0,6 à 1,9 Go pour les pics (extraction, génération de site) |

Ce budget exclut les modèles IA génératifs locaux, qui tournent sur une autre machine ou sur un serveur plus grand (F-IA-07, §6.2 de l'architecture).

### 3.3 Compatibilité de licence

Toutes les dépendances proposées ont été vérifiées au regard du filtre du §1.1. Points d'attention :

- **Tiptap** : le cœur et la plupart des extensions sont sous MIT, mais certaines extensions et services (« Pro », collaboration hébergée, conversion) sont commerciaux. Règle : **seules les extensions MIT sont utilisées** ; un test d'intégration continue vérifie les licences des paquets de l'interface (§21).
- **Redis** : changé de licence en 2024 (licences à source disponible), puis ajout de l'AGPL en 2025. Il n'est pas requis (P7) ; si un courtier devient nécessaire, **Valkey** (BSD, fondation Linux) est préféré pour éviter de lier le projet à un éditeur qui a déjà changé de licence une fois.
- **Stockage objet** : le projet communautaire MinIO est passé en mode maintenance fin 2025. La plateforme ne livre **aucun** serveur de stockage objet ; elle se connecte à n'importe quel service compatible S3 (fournisseur cloud, Garage, SeaweedFS, Ceph). La documentation ne recommandera pas MinIO.
- **Modèles d'embeddings** : la licence des **poids** est vérifiée modèle par modèle (Apache-2.0 ou MIT exigées pour le modèle par défaut).

---

## 4. Langage du back-end

### 4.1 Exigences

Écosystème IA et extraction Web riche ; tâches de fond ; typage pour des contrats d'extension stables ; chargement de modules ; tests d'architecture (§26 de l'architecture).

### 4.2 Évaluation

| Critère (poids) | Python | TypeScript / Node.js | Go | Java / Kotlin | PHP (Laravel) |
|---|---|---|---|---|---|
| K1 Adéquation (5) | 5 : tous les besoins couverts par des bibliothèques mûres | 4 : bon pour l'API ; extraction et NLP plus pauvres | 3 : extraction, NLP, traitement de documents à réécrire | 4 : complet mais verbeux | 3 : bon pour le Web, faible pour l'IA et les tâches longues |
| K2 Maturité (4) | 5 : PSF, 30 ans | 4 : OpenJS ; écosystème très mouvant | 5 : Google, stable | 5 | 4 |
| K3 Exploitation (4) | 4 : mémoire moyenne ; emballage simplifié par `uv` | 4 | 5 : binaire unique, peu de mémoire | 2 : JVM gourmande pour 4 Go | 4 |
| K4 Sécurité (4) | 4 | 3 : chaîne npm très exposée aux attaques de dépendances | 5 | 4 | 3 |
| K5 Écosystème (3) | **5** : extraction (`trafilatura`), NLP, embeddings, SDK IA de référence, images | 3 | 2 | 3 | 2 |
| K6 Contribution (3) | **5** : langage le plus pratiqué en IA et en données ; public visé par le projet | 5 | 3 | 3 | 4 |
| K7 Indépendance (3) | 5 | 5 | 4 | 4 | 5 |
| **Total pondéré** (sur 130) | **122** | 103 | 102 | 94 | 92 |

### 4.3 Décision

**Python 3.12 ou plus récent**, retenu. L'avantage décisif est l'écosystème (K5) : extraction Web, détection de langue, embeddings locaux, similarité, SDK officiels des fournisseurs IA, provenance C2PA existent tous en Python, maintenus et sous licence compatible. Le recrutement de contributeurs (K6) va dans le même sens.

**Faiblesses assumées et réponses** :

| Faiblesse | Réponse |
|---|---|
| Typage optionnel, contrats fragiles | Typage complet vérifié en intégration continue (`mypy` en mode strict ou `pyright`) ; contrats d'extension exprimés en **modèles Pydantic** et protocoles typés, validés à l'exécution aux frontières |
| Performance brute | Charge modeste (§1.2 de l'architecture) ; calculs lourds délégués à des bibliothèques natives (ONNX, `rapidfuzz`, PostgreSQL) ; files séparées |
| Emballage et environnements | Gestion des dépendances par **`uv`** (fichier de verrouillage, reproductible) ; image construite une seule fois |
| Parallélisme (verrou global de l'interpréteur) | Entrées-sorties asynchrones pour l'API et la collecte ; processus séparés pour les workers ; aucun besoin de calcul parallèle intensif dans le processus |

---

## 5. Cadre Web, accès aux données et structure du back-end

### 5.1 Évaluation du cadre Web

| Critère (poids) | FastAPI | Litestar | Django + Django Ninja | Flask |
|---|---|---|---|---|
| K1 Adéquation (5) | 5 : asynchrone, OpenAPI généré (P8, §18.2), Pydantic natif | 5 : mêmes atouts, plus de fonctions intégrées | 4 : très complet (admin, auth, migrations) mais ORM et modèle de modules imposés, asynchrone partiel | 3 : tout à assembler |
| K2 Maturité (4) | 4 : très adopté ; **gouvernance centrée sur un mainteneur principal** | 3 : communauté plus petite, gouvernance collective | **5** : fondation (DSF) depuis 2008 | 5 |
| K3 Exploitation (4) | 5 | 5 | 4 | 5 |
| K4 Sécurité (4) | 4 : fin, peu de surface ; s'appuie sur Starlette | 4 | 5 : protections intégrées éprouvées | 4 |
| K5 Écosystème (3) | 5 | 3 | 5 | 4 |
| K6 Contribution (3) | 5 : le plus connu des développeurs Python d'API | 3 | 5 | 4 |
| K7 Indépendance (3) | 4 | 4 | 4 : couplage fort de tout le code à Django | 5 |
| **Total pondéré** (sur 130) | **119** | 103 | 118 | 110 |

### 5.2 Décision

**FastAPI**, retenu, avec **trois conditions** qui répondent à sa faiblesse principale (gouvernance concentrée) :

1. **Le domaine ne dépend pas du cadre Web.** FastAPI n'est utilisé que dans la couche d'entrée (routes, dépendances, sérialisation). Les modules métier, le PDP, les adaptateurs et les tâches n'importent jamais FastAPI. Un test d'architecture le vérifie (§5.4).
2. **Les fondations sont des projets indépendants** : Starlette (serveur ASGI), Pydantic (validation), SQLAlchemy (données). En cas d'abandon de FastAPI, **Litestar** ou Starlette seul reprennent la couche d'entrée sans toucher au domaine.
3. **Les fonctions intégrées manquantes** (authentification, sessions, protection CSRF, limitation de débit) sont fournies par le module Identité et accès du projet (§18), pas par des greffons tiers peu maintenus.

**Pourquoi pas Django**, malgré un score presque égal (118 contre 119) et une meilleure pérennité : l'écart de notation n'est pas décisif, l'argument architectural l'est. Son modèle (applications Django, ORM actif, signaux) s'oppose au découpage hexagonal choisi (ADR-01, §7.3 de l'architecture) ; l'ORM Django rend difficile l'application stricte de MD1 et MD6 sans contournements ; l'administration intégrée, son principal atout, ne servirait pas (P8 : toute fonction passe par l'API publique). Django reste le **repli** si les conditions ci-dessus s'avéraient trop coûteuses.

### 5.3 Accès aux données

| Choix | Justification |
|---|---|
| **SQLAlchemy 2** (mode « Core » et ORM déclaratif typé) | Référence de l'écosystème depuis 2006 ; contrôle fin du SQL (nécessaire pour `SKIP LOCKED`, verrous consultatifs, recherche plein texte, `pgvector`) ; sessions et transactions explicites (boîte d'envoi transactionnelle, §12.2 de l'architecture) |
| **Alembic** | Migrations versionnées ; migrations automatiques au démarrage précédées d'une sauvegarde (§20.4 de l'architecture) |
| **Pilote `psycopg` 3** | Pilote officiel moderne, synchrone et asynchrone, `LISTEN/NOTIFY` |
| **Contexte de tenance** | Une fabrique de sessions par requête et par tâche, qui positionne l'espace courant dans la session PostgreSQL (`SET LOCAL`) pour les politiques de sécurité au niveau des lignes (§7.3) et filtre toute requête construite par la couche d'accès (MD6) |

### 5.4 Structure et tests d'architecture

| Besoin | Outil | Licence |
|---|---|---|
| Frontières entre modules (MD1, MD2) et indépendance du domaine | **`import-linter`** : contrats d'imports vérifiés en intégration continue | BSD |
| Chargement des modules et connecteurs | **Points d'entrée Python** (`entry points` des paquets) lus par le registre des modules, validés par leur manifeste Pydantic | — |
| Serveur ASGI | **Uvicorn** (processus gérés par le conteneur) | BSD |
| Validation des manifestes et schémas de configuration | **Pydantic v2** ; les schémas JSON des formulaires de configuration (§9.2 de l'architecture) sont générés à partir des modèles | MIT |

---

## 6. Interface Web

### 6.1 Exigences

Éditeur riche de documents structurés, accessibilité (WCAG 2.1 AA visé), internationalisation FR + EN dès le lot 1, suivi en temps réel, déploiement simple, compétences de la communauté (§18.1 et §26 de l'architecture). Contexte déterminant : l'interface est une **application authentifiée** (aucun besoin de référencement), qui n'utilise **que l'API publique** (P8). Le site public des marques est un produit séparé (CMS externe ou site statique généré, §15).

### 6.2 Trois familles d'approches

| Approche | Principe | Conséquence pour le déploiement |
|---|---|---|
| **A. Application monopage (SPA)** | L'interface est un ensemble de fichiers statiques (HTML, JS, CSS) qui appelle l'API | Aucun processus supplémentaire : fichiers servis par Caddy ou par l'application. **Node.js seulement à la construction** |
| **B. Cadre de rendu serveur JavaScript** (Next.js, Nuxt, SvelteKit en mode serveur) | Un serveur Node.js rend les pages et peut contenir de la logique | **Un environnement d'exécution et un conteneur de plus** (§3.1) ; logique côté serveur JavaScript tentante, contraire à P8 |
| **C. Rendu serveur Python + interactivité légère** (gabarits Jinja2 + htmx) | Le back-end produit le HTML | Le plus simple à déployer ; **mal adapté** à un éditeur riche, à l'édition côte à côte avec les sources et au temps réel ; API publique à maintenir séparément de l'interface |

### 6.3 Évaluation de Next.js (piste initiale)

Next.js est un cadre de très grande qualité, le plus utilisé de l'écosystème React. Il est évalué ici **pour ce produit précis** :

| Atout de Next.js | Utile ici ? | Pourquoi |
|---|---|---|
| Rendu serveur, référencement, premier affichage rapide | **Non** | Application derrière authentification ; le site public n'est pas servi par l'application |
| Composants serveur, actions serveur | **Non, et contraire à P8** | Placer de la logique dans un serveur JavaScript crée un second back-end à côté de Python ; l'architecture exige que l'interface n'utilise que l'API publique |
| Routage par fichiers, optimisation d'images | Partiellement | Des équivalents existent pour les SPA |
| Écosystème React (éditeurs, composants accessibles) | **Oui** | Mais il est entièrement disponible **sans** Next.js |

| Coût de Next.js | Constat |
|---|---|
| Exploitation | Un serveur Node.js en production : 5ᵉ conteneur en solo, 150 à 300 Mo de RAM, mises à jour de sécurité d'un second environnement (contraire à §3.1, K3) |
| Sécurité | Deux vulnérabilités critiques récentes touchent précisément les fonctions serveur : contournement d'autorisation par le middleware (CVE-2025-29927, mars 2025) et exécution de code à distance dans les composants serveur React (CVE-2025-55182, décembre 2025). Une SPA statique n'expose pas cette surface (K4) |
| Pérennité et indépendance | Cadre dirigé par une entreprise dont le modèle économique est l'hébergement ; changements de paradigme fréquents (Pages Router → App Router → composants serveur) ; auto-hébergement possible mais secondaire dans ses priorités (K2, K7) |

**Conclusion** : Next.js n'est **pas retenu pour l'application**. Ses atouts ne servent pas ce produit, ses coûts touchent trois critères de rang élevé. L'écosystème React, lui, est retenu.

### 6.4 Évaluation des SPA

| Critère (poids) | React + Vite | Vue 3 + Vite | Svelte 5 / SvelteKit statique | Angular |
|---|---|---|---|---|
| K1 Adéquation (5) | **5** : meilleurs éditeurs riches (Tiptap, ProseMirror, Lexical, BlockNote) et composants accessibles (React Aria) | 4 : Tiptap disponible ; composants accessibles moins complets | 3 : éditeurs et composants accessibles moins mûrs | 4 |
| K2 Maturité (4) | 5 : React (Meta, fondation React annoncée en 2025) | 5 : gouvernance communautaire | 4 | 5 : Google |
| K3 Exploitation (4) | 5 : fichiers statiques | 5 | 5 | 5 |
| K4 Sécurité (4) | 4 | 4 | 4 | 4 |
| K5 Écosystème (3) | **5** | 4 | 3 | 3 |
| K6 Contribution (3) | **5** : le plus large vivier | 4 | 3 | 3 |
| K7 Indépendance (3) | 4 | 5 | 5 | 3 |
| **Total pondéré** (sur 130) | **123** | 115 | 100 | 103 |

### 6.5 Décision

**Application monopage React + TypeScript, construite avec Vite**, servie sous forme de fichiers statiques. Pile proposée :

| Besoin | Choix | Licence | Justification |
|---|---|---|---|
| Construction | **Vite** | MIT | Standard de fait, rapide, indépendant d'un hébergeur |
| Routage | **TanStack Router** | MIT | Routage typé ; alternative : React Router |
| Données serveur et cache | **TanStack Query** | MIT | Cache, invalidation, reprises ; s'articule avec les événements temps réel |
| Client d'API | **Généré à partir de la spécification OpenAPI** de FastAPI (`openapi-typescript` ou équivalent) | MIT | Types partagés sans duplication manuelle ; l'interface consomme exactement l'API publique (P8) |
| Composants accessibles | **React Aria Components** (Adobe) | Apache-2.0 | Accessibilité de référence (clavier, lecteurs d'écran, internationalisation intégrée) |
| Styles | **Tailwind CSS** ou CSS modules (à trancher par les contributeurs de l'interface) | MIT | Sans impact architectural |
| Internationalisation | **i18next** + `react-i18next`, messages au format ICU | MIT | FR + EN dès le lot 1 ; pluriels et formats localisés ; même catalogue pour les libellés générés depuis les manifestes |
| Temps réel | **Événements serveur (Server-Sent Events)** natifs du navigateur, repli par interrogation | — | Flux serveur → navigateur suffisant (§18.1 de l'architecture) ; plus simple que WebSocket à traverser les proxys |
| Formulaires de configuration des modules | Génération à partir du **schéma JSON** des manifestes (ex. `react-jsonschema-form` ou composant maison sur React Aria) | Apache-2.0 | §9.2 de l'architecture : aucun code d'interface dans les modules |

**Réversibilité** : si la communauté du projet préférait Vue, seule l'interface change ; l'API, le format de document (ProseMirror est indépendant du cadre) et le reste de l'architecture sont inchangés.

---

## 7. Base de données

### 7.1 Exigences

Transactions fiables ; verrouillage adapté aux files (« prendre la prochaine tâche libre » sans contention) ; recherche plein texte multilingue ; index vectoriel ; types semi-structurés (JSON) ; sécurité au niveau des lignes ; sauvegarde simple (§6.3, §8.1, §26 de l'architecture).

### 7.2 Évaluation

| Exigence | PostgreSQL 18 | MariaDB 11 / MySQL 8 | SQLite |
|---|---|---|---|
| Transactions, intégrité | Complètes | Complètes (InnoDB) | Complètes, **un seul écrivain à la fois** |
| File de tâches : `FOR UPDATE SKIP LOCKED` | Oui (depuis 9.5) | Oui (MySQL 8, MariaDB 10.6) | Non (pas de verrou de ligne) |
| Verrous consultatifs (verrou de leader) | Oui | `GET_LOCK` | Non |
| Plein texte multilingue | Natif (`tsvector`, dictionnaires FR, EN et une vingtaine d'autres langues), `unaccent`, trigrammes `pg_trgm` | Natif mais plus limité (racinisation absente en natif) | FTS5, sans racinisation française native |
| Index vectoriel | Extension **`pgvector`** (HNSW, IVFFlat, demi-précision, quantification binaire) | MariaDB 11.7+ : type vecteur natif, récent ; MySQL : non (communautaire) | Extensions récentes peu mûres |
| JSON | `jsonb` indexable | JSON (moins riche) | JSON1 |
| **Sécurité au niveau des lignes** | **Native** (`ROW LEVEL SECURITY`) | **Absente** | Absente |
| Licence | PostgreSQL (permissive) | GPL-2.0 (serveur, utilisé par réseau : acceptable) | Domaine public |
| Sauvegarde | `pg_dump` cohérent, sauvegarde physique, archivage WAL | `mariadb-dump` | Copie de fichier |
| Gouvernance | Communautaire, sans éditeur dominant, depuis 1996 | Fondation MariaDB / Oracle | Petite équipe |

### 7.3 Décision

**PostgreSQL 18 ou plus récent**, seule base supportée, avec les extensions **`pgvector`** (licence PostgreSQL), **`pg_trgm`** et **`unaccent`** (livrées avec PostgreSQL). Image officielle de la communauté PostgreSQL complétée de `pgvector` (ou image publiée par le projet `pgvector`).

Raisons décisives : c'est la seule option qui satisfait **toutes** les exigences, dont deux éliminatoires pour les autres (sécurité au niveau des lignes, verrouillage de file et vecteurs mûrs dans le même moteur). PostgreSQL 18 apporte en plus la génération native d'identifiants **UUIDv7** (opaques et triables dans le temps, §8.5 de l'architecture) et des entrées-sorties asynchrones utiles aux parcours d'index.

**Une seule base supportée** : SQLite aurait été séduisant pour une installation « démo », mais supporter deux bases double les tests, interdit les fonctions spécifiques (RLS, `SKIP LOCKED`, `pgvector`) et contredit R-O05. Une installation de démonstration utilisera le même fichier Compose.

### 7.4 Usage des fonctions propres à PostgreSQL

Chaque fonction spécifique est **cantonnée à un adaptateur** du module qui en a besoin, pour qu'un remplacement partiel reste possible (§8.5).

| Fonction | Module | Rôle | Substitut si un jour nécessaire |
|---|---|---|---|
| `FOR UPDATE SKIP LOCKED` | Tâches | Réservation de tâches sans contention | Courtier de messages (§8.4) |
| Verrous consultatifs | Tâches | Verrou de leader du planificateur ; sérialisation par clé | Verrou distribué du courtier |
| `LISTEN / NOTIFY` | Tâches, temps réel | Réveil des workers et des flux SSE (optimisation ; l'interrogation périodique reste le mécanisme de sûreté) | Abonnements du courtier |
| `ROW LEVEL SECURITY` | Socle (accès aux données) | Seconde barrière d'isolation par espace (§8.1 de l'architecture) | Aucune nécessité : la première barrière est applicative |
| `tsvector`, GIN, `unaccent`, `pg_trgm` | Veille, Bibliothèque | Recherche plein texte et approximative | Moteur de recherche dédié (§8.4) |
| `pgvector` (HNSW, `halfvec`) | Veille, Garde-fous | Proximité sémantique, quasi-doublons, retour de tri | Base vectorielle dédiée (§8.4) |
| `jsonb` | Tous | Paramètres de connecteurs, rapports, document structuré | Natif dans toute base moderne |
| Partitionnement déclaratif | Veille, Passerelle IA | Éléments collectés et journal des appels par mois (purge par détachement de partition) | — |

**Sécurité au niveau des lignes : mode d'emploi.** Les politiques RLS filtrent sur un paramètre de session (`app.espace_courant`) positionné par la fabrique de sessions (§5.3). L'application se connecte avec un rôle **sans** privilège de contournement ; les migrations et l'administration utilisent un rôle distinct. Le coût en performance est faible si les index commencent par la colonne d'espace ; il sera mesuré dans S1.

---

## 8. Point de vigilance 1 — Seuil réel de validité d'ADR-02

ADR-02 fait de la base relationnelle le **centre de gravité** : source de vérité, file de tâches, recherche plein texte et vectorielle. La question posée est : **jusqu'où cette décision tient-elle, et à quel signal faut-il en sortir ?** La réponse est découpée par charge, car les trois usages n'atteignent pas leur plafond au même moment.

### 8.1 Charges estimées par profil

Hypothèses : profils du §1.2 de l'architecture ; éléments non retenus conservés 90 jours (§8.6 de l'architecture) ; un embedding par élément collecté, de dimension 384, stocké en demi-précision (`halfvec`, 2 octets par dimension, soit environ 0,8 Ko par vecteur) ; environ 3 tâches par élément collecté (récupération, analyse et score, embedding) plus les tâches de rédaction, de publication et de maintenance.

| Grandeur | Solo | Petite rédaction | Instance partagée |
|---|---|---|---|
| Éléments collectés / jour | 500 à 5 000 | 5 000 à 30 000 | 100 000+ |
| Éléments conservés (fenêtre de 90 jours) | ≤ 450 000 | ≤ 2,7 millions | ≥ 9 millions |
| Tâches / jour (moyenne) | ≤ 15 000 (≈ 0,2 / s) | ≤ 100 000 (≈ 1,2 / s) | ≥ 300 000 (≈ 4 / s) |
| Pics de tâches (collecte groupée) | ≈ 10 / s | ≈ 50 / s | ≥ 200 / s |
| Volume des vecteurs (brut) | ≤ 0,4 Go | ≤ 2,2 Go | ≥ 7 Go |
| Index HNSW estimé (≈ 1,3 à 1,5 × le brut) | ≤ 0,6 Go | ≤ 3,3 Go | ≥ 10 Go |
| Texte extrait (≈ 5 Ko par élément, avant compression) | ≤ 2,3 Go | ≤ 14 Go | ≥ 45 Go |

### 8.2 Plafonds pratiques de PostgreSQL pour chaque usage

| Usage | Ce qui limite réellement | Ordre de grandeur du plafond sur un serveur unique | Marge au profil petite rédaction |
|---|---|---|---|
| **File de tâches** | Pas le débit brut (une file `SKIP LOCKED` bien conçue traite des **centaines à milliers de tâches par seconde**), mais le **gonflement de la table** (lignes mortes à chaque changement d'état, nettoyage automatique en retard) et le verrou global pris par `NOTIFY` à la validation des transactions quand les notifications sont très nombreuses | ≈ 100 tâches / s **soutenues** sans réglage particulier ; au-delà, réglages nécessaires | **× 50 à × 100** sur la moyenne, × 2 sur les pics |
| **Recherche plein texte** | Le **classement** (`ts_rank`) calculé sur toutes les lignes correspondantes ; l'absence de tolérance aux fautes de frappe et de classement BM25 en natif ; des langues sans dictionnaire (chinois, japonais, arabe…) | ≈ 5 à 10 millions de documents interrogeables avec des temps < 300 ms, **à condition** de filtrer par espace et par fenêtre de dates | × 2 à × 4 |
| **Recherche vectorielle** | La **mémoire** : un index HNSW doit tenir en cache pour être rapide ; sa construction est coûteuse | Index de quelques millions de vecteurs de dimension 384 en demi-précision, si sa taille reste sous ≈ 50 % de la RAM disponible pour la base | **× 1,5 à × 3** : c'est le **premier plafond** |
| **Volume total et sauvegarde** | Durée de `pg_dump` et de restauration | ≈ 100 Go avant de passer à une sauvegarde physique (`pgBackRest`) | × 5 |

### 8.3 Verdict

1. **Profils solo et petite rédaction : ADR-02 est valide avec une marge confortable.** La file de tâches est loin de son plafond (marge d'un facteur 50 au moins sur la moyenne) ; la recherche plein texte garde un facteur 2 à 4 ; la recherche vectorielle est le seul usage dont la marge est faible au profil solo maximal sur 4 Go de RAM (index jusqu'à 0,6 Go).
2. **Le premier plafond atteint sera la recherche vectorielle, pas la file de tâches.** C'est contre-intuitif mais important : le risque d'ADR-02 n'est pas « Postgres comme file de tâches », c'est « Postgres comme moteur vectoriel sur un petit serveur ».
3. **Profil instance partagée : ADR-02 n'est plus valide tel quel au-delà d'environ 5 à 10 millions d'éléments conservés** dans une même instance. Il faut alors un moteur dédié pour la recherche et les vecteurs, et probablement un courtier pour la file.
4. **Cas de l'offre hébergée (D1)** : si elle est réalisée en « **une instance par client** » (option déjà prévue au §8.1 de l'architecture), chaque instance reste un profil solo ou petite rédaction, et ADR-02 reste valide **sans limite de nombre de clients**. C'est un argument fort pour ce modèle d'hébergement si D1 est un jour activée.

### 8.4 Leviers dans l'ordre, avant d'ajouter un composant

| Ordre | Levier | Effet | Coût |
|---|---|---|---|
| 1 | **Partitionner les éléments collectés par mois** et ne construire l'index vectoriel que sur les partitions récentes (par défaut 30 jours ; la veille porte sur l'actualité) | Divise l'index vectoriel par 3 ; la purge devient un détachement de partition | Faible, prévu dès le lot 1 |
| 2 | **N'embarquer que ce qui sert** : embeddings calculés seulement pour les espaces dont un sujet utilise la proximité sémantique, et après un premier filtre lexical | Réduit le volume de vecteurs de 30 à 80 % selon les sujets | Faible |
| 3 | **Quantification** (`halfvec`, puis quantification binaire avec reclassement) ; dimension 384 plutôt que 768 ou 1024 | Divise la mémoire par 2 à 16 | Faible ; perte de qualité à mesurer (S5) |
| 4 | **Hygiène de la file** : table de tâches actives réduite (tâches terminées déplacées vers une table d'historique partitionnée), `fillfactor` réduit, nettoyage automatique réglé sur cette table, notifications regroupées | Repousse le plafond de la file d'un ordre de grandeur | Faible, prévu dès le lot 1 |
| 5 | **Réplica de lecture** pour la recherche | Isole les recherches lourdes des écritures | Moyen (exploitation) |
| 6 | **Composant dédié** derrière le port existant : moteur de recherche (**Meilisearch**, MIT, ou **OpenSearch**, Apache-2.0), base vectorielle (**Qdrant**, Apache-2.0), courtier (**Valkey**, BSD, ou **RabbitMQ**, MPL-2.0) | Lève le plafond correspondant | Élevé : composant à installer, sauvegarder, surveiller ; deux sources de vérité à synchroniser |

### 8.5 Signaux de sortie (indicateurs surveillés)

Ces indicateurs sont affichés dans le **tableau de santé** de l'administration (F-ADM-02, §21 de l'architecture). Les seuils proposés sont des valeurs de départ, à calibrer par S1.

| Indicateur | Seuil d'alerte | Seuil de décision (envisager le levier 5 ou 6) |
|---|---|---|
| Débit soutenu de la file (moyenne sur 1 h) | > 50 tâches / s | > 100 tâches / s malgré le levier 4 |
| Délai de prise en charge d'une tâche prête (95ᵉ centile, file `publication`) | > 2 s | > 10 s |
| Lignes mortes de la table des tâches actives | > 20 % | Nettoyage automatique incapable de suivre pendant 24 h |
| Temps de recherche dans la veille (95ᵉ centile) | > 300 ms | > 1 s |
| Taille de l'index vectoriel / mémoire disponible pour la base | > 35 % | > 50 % malgré les leviers 1 à 3 |
| Éléments interrogeables dans l'instance | > 3 millions | > 8 millions |
| Taille de la base | > 50 Go | > 100 Go (sauvegarde physique obligatoire) |
| Besoin fonctionnel non couvert | — | Langue sans dictionnaire PostgreSQL utilisée par une marque ; tolérance aux fautes de frappe demandée |

### 8.6 Conditions pour que la sortie reste possible

ADR-02 n'est un bon choix que s'il est **réversible**. Trois conditions, vérifiées dès le lot 1 :

1. **Ports internes stricts** : la file (`Tâches`), l'index de recherche et l'index vectoriel sont des **interfaces** du code ; aucun module n'écrit de SQL de file ou de recherche en dehors de leur adaptateur PostgreSQL (vérifié par `import-linter`, §5.4).
2. **Index reconstructibles** : les index plein texte et vectoriels se reconstruisent à partir des données (§8.4 de l'architecture) ; un moteur dédié est donc alimenté par une tâche de réindexation, sans migration de données.
3. **Boîte d'envoi conservée** : même avec un courtier, la tâche est d'abord écrite en base dans la transaction métier, puis relayée vers le courtier ; la garantie « rien de perdu, rien en double » (R-T08) ne dépend jamais du courtier.

### 8.7 Risque d'exploitation oublié : les mises à jour majeures de PostgreSQL

Le vrai coût d'ADR-02 pour un installateur non expert n'est pas la performance, ce sont les **montées de version majeure** de PostgreSQL (une par an ; chaque version est maintenue 5 ans), qui exigent un export et une restauration ou `pg_upgrade`, opération délicate dans des conteneurs. Réponse proposée :

- la version majeure de PostgreSQL est **fixée par version majeure du produit** et ne change jamais lors d'une mise à jour mineure ;
- une **commande de montée de version assistée** (sauvegarde, export, nouvelle base, restauration, vérification) est fournie et testée dans l'intégration continue ;
- le tableau de santé signale la fin de support de la version de PostgreSQL utilisée.

---

## 9. File de tâches et planificateur

### 9.1 Exigences

File durable sur la base, écriture dans la transaction métier (boîte d'envoi), baux de réservation, reprises avec délai croissant, priorités, **concurrence limitée par clé** (canal, domaine, fournisseur IA), états riches couplés à la machine à états de publication (« inconnu », « à vérifier », « suspendue »), annulation sur arrêt d'urgence, verrou de leader du planificateur, rattrapage des échéances manquées selon une règle par type (§12 de l'architecture).

### 9.2 Évaluation

| Candidat | Principe | Licence | Couverture des exigences | Écart principal |
|---|---|---|---|---|
| **Celery** | Bibliothèque de tâches distribuées | BSD | Bonne sur le traitement | **Exige un courtier** (Redis, RabbitMQ) : contraire à ADR-02 ; écriture transactionnelle impossible sans boîte d'envoi supplémentaire |
| **Dramatiq**, **RQ**, **arq** | Bibliothèques plus simples | LGPL / BSD / MIT | Partielle | Même écart (courtier Redis ou RabbitMQ) |
| **Temporal** | Moteur d'exécution durable | MIT | Très bonne (flux de travail durables, reprises) | **Serveur dédié et sa propre base** : deux composants de plus en solo, contraire à P7 et K3 |
| **Hatchet** | Moteur de tâches sur PostgreSQL | MIT | Bonne | **Moteur séparé** (service à déployer) ; jeune |
| **Procrastinate** | Bibliothèque Python de tâches **sur PostgreSQL** | MIT | Bonne : `SKIP LOCKED`, `LISTEN/NOTIFY`, tâches périodiques, verrous par clé, reprises | Concurrence par clé limitée à 1 (sérialisation), pas de quotas par clé > 1 ; écriture dans la transaction applicative à valider avec SQLAlchemy ; communauté modeste |
| **DBOS Transact** | Bibliothèque d'exécution durable **sur PostgreSQL** | MIT | Bonne : flux de travail durables, files avec limites de concurrence, tâches planifiées, idempotence | Jeune (2024), portée par une entreprise ; modèle « flux de travail » qui recouvre partiellement le moteur de pipelines du projet |
| **Module interne** sur PostgreSQL | Table de tâches, `SKIP LOCKED`, baux, verrous consultatifs | — (code du projet) | **Totale par construction** | Code à écrire et à maintenir ; risque de bogues subtils sur la concurrence |

### 9.3 Décision

**Module Tâches interne**, conçu sur PostgreSQL, avec une **preuve de concept comparative (S2)** contre Procrastinate et DBOS avant de le figer.

Raisons :

- La file n'est pas un détail d'infrastructure : elle porte la **garantie de fiabilité de rang 3** (R-T08) et elle est **couplée** à la machine à états de publication et au PDP (revérification de dernier moment, suspension sur arrêt d'urgence). Les candidats génériques couvrent 70 à 90 % du besoin ; le reste (états « inconnu » et « à vérifier », quotas par clé > 1, annulation ciblée par marque) devrait être construit **par-dessus**, ce qui crée une double logique.
- Le noyau d'une file `SKIP LOCKED` est un **patron très documenté** et compact ; ce qui coûte, ce sont les tests (concurrence, pannes de worker, expiration des baux). Ces tests sont nécessaires quel que soit le choix, puisque la garantie R-T08 doit être démontrée de bout en bout.
- La décision reste **réversible** : l'interface du module Tâches est le seul point de contact (§8.6).

**Critère de bascule après S2** : si Procrastinate ou DBOS couvrent sans contournement l'écriture transactionnelle avec SQLAlchemy, la concurrence par clé et l'annulation ciblée, le candidat externe est préféré (moins de code à maintenir).

### 9.4 Planificateur

Intégré au module Tâches : échéances stockées en base, calcul des récurrences dans le fuseau de la marque avec **`zoneinfo`** (bibliothèque standard) et une bibliothèque d'expressions de récurrence (`croniter`, MIT, ou règles RFC 5545 via `python-dateutil`, BSD) ; **verrou consultatif PostgreSQL** pour garantir un seul planificateur actif ; règles de rattrapage par type (§12.5 de l'architecture). Pas de composant externe (`cron` système, APScheduler) : la planification fait partie du domaine (publications planifiées, délais de grâce).

---

## 10. Format de document et éditeur

### 10.1 Exigences

Schéma ouvert et documenté ; conversion fiable vers HTML et Markdown ; **origine de chaque bloc** (généré, modifié, humain) pour la part d'IA (D8) ; **références de sources** attachées aux passages ; citations typées comparables mot pour mot ; comparaison de versions bloc par bloc ; édition collaborative possible plus tard ; rendu côté serveur, en Python, par le moteur de rendu central (§14.2 et §14.5 de l'architecture).

### 10.2 Évaluation

| Critère | ProseMirror (via Tiptap) | Lexical | BlockNote | Editor.js | Portable Text |
|---|---|---|---|---|---|
| Nature | Boîte à outils d'édition à **schéma strict** ; Tiptap en est la surcouche la plus utilisée | Éditeur de Meta | Éditeur « par blocs » construit sur ProseMirror et Tiptap | Éditeur par blocs | **Spécification** ouverte de texte riche (Sanity) |
| Licence | MIT (ProseMirror) ; MIT pour le cœur Tiptap, extensions « Pro » commerciales à éviter | MIT | MPL-2.0 pour le cœur ; certains paquets sous GPL-3.0 ou licence commerciale | Apache-2.0 | MIT |
| Schéma déclaratif et validable | **Oui**, c'est son principe | Oui, moins formalisé | Hérité de ProseMirror, contraint par BlockNote | Faible (blocs libres) | Oui (spécification) |
| Attributs par bloc et par marque (origine, référence de source) | **Natif** (attributs de nœuds et marques) | Oui | Oui (limité au modèle de BlockNote) | Par bloc seulement, pas dans le texte | Oui (« marks » et annotations) |
| Collaboration future | **Yjs** (`y-prosemirror`), éprouvé | Yjs | Yjs | Non | Non (côté éditeur) |
| Outils côté serveur Python | Format JSON simple à parcourir ; portage `prosemirror-py` (application des transformations) | Aucun | Comme ProseMirror | JSON simple | Bibliothèques de rendu Python modestes |
| Maturité | ProseMirror depuis 2015, très utilisé (Atlassian, NYT, Guardian…) | Depuis 2022 | Depuis 2023 | Depuis 2018 | Éditeur de référence lié à un produit commercial |

### 10.3 Décision

- **Format** : **« Document plateforme v1 »**, un document JSON au **schéma ProseMirror** défini par le projet, **publié** (JSON Schema dans la documentation) et **versionné** (champ `version_schema` dans chaque document ; migrations de documents écrites comme des migrations de base). Nœuds prévus : titre, paragraphe, liste, citation (attribut : référence de source obligatoire), image (référence de média), encadré, séparateur, intertitre ; marques : gras, italique, lien, **référence de source** (annotation d'un passage). Chaque nœud de bloc porte un attribut **`origine`** (`ia`, `ia_modifie`, `humain`) et un identifiant stable de bloc (comparaison de versions).
- **Éditeur** : **Tiptap** (cœur MIT et extensions libres), avec des extensions propres au projet pour la référence de source, la citation typée et l'origine des blocs. La mise à jour de l'attribut `origine` (passage de `ia` à `ia_modifie` lors d'une modification humaine) est faite dans l'éditeur **et revérifiée côté serveur** par comparaison avec la version précédente : le serveur ne fait pas confiance au navigateur pour le calcul de la part d'IA.
- **Rendu** : un **moteur de rendu Python** propre au projet parcourt le JSON et produit HTML, Markdown et texte brut (§14.5 de l'architecture). Il est volontairement **indépendant** de la bibliothèque JavaScript : c'est lui qui fait foi pour les publications.
- **Repli** : ProseMirror nu (si Tiptap changeait de licence ou de cap : Tiptap n'est qu'une surcouche, le format reste identique). BlockNote reste une option d'**expérience utilisateur** à évaluer dans S3 (édition par blocs plus conviviale), sous réserve de n'utiliser que ses paquets MPL-2.0.

**Preuve de concept S3** : aller-retour JSON → HTML → WordPress et Ghost → relecture ; collage depuis Word et Google Docs (nettoyage) ; calcul de la part d'IA sur 20 scénarios d'édition ; comparaison de versions.

---

## 11. Passerelle IA

### 11.1 Exigences

Adaptateur générique « protocole compatible OpenAI » (Groq, OpenRouter, Ollama, OpenAI, Mistral et d'autres) et adaptateurs natifs (Anthropic au moins) ; sortie structurée validée ; embeddings, images, vision ; erreurs normalisées ; comptage des jetons et des coûts ; budgets à réservation ; **aucune dépendance** du reste du code autre que le contrat interne (§9.4 et §10 de l'architecture).

### 11.2 Évaluation

| Option | Licence | Atouts | Écarts |
|---|---|---|---|
| **LiteLLM** (bibliothèque ou proxy) | MIT (sauf dossier « entreprise ») | Plus d'une centaine de fournisseurs, tableau des prix tenu à jour, interface unique | Dépendance très large et très mouvante, au cœur de la chaîne la plus sensible (clés d'API) ; **paquet PyPI compromis en mars 2026** (versions piégées volant des identifiants) : le risque de chaîne d'approvisionnement n'est pas théorique ; recouvre et contredit en partie la passerelle du projet (budgets, replis, journal) |
| **Pydantic AI** | MIT | Équipe de Pydantic ; nombreux fournisseurs ; **sortie structurée typée** ; limites d'usage (requêtes, jetons) ; gestion d'outils pour les agents | Cadre plus large que le besoin des lots 1 et 2 ; évolutions rapides |
| **LangChain** (couche modèles) | MIT | Très large écosystème | Abstractions lourdes, changements fréquents d'interfaces ; dépendances nombreuses |
| **SDK officiels + adaptateurs maison** | `openai` : Apache-2.0 ; `anthropic` : MIT | Dépendances minimales et maintenues par les fournisseurs ; contrôle total du contrat interne ; le SDK `openai` accepte une **URL de base** et couvre donc tout le protocole compatible | Adaptateurs à écrire (un générique, un par fournisseur natif) ; tableau des capacités et des prix à tenir |

### 11.3 Décision

**Adaptateurs maison minces sur les SDK officiels**, derrière le contrat interne de la passerelle :

| Adaptateur | Base | Lot |
|---|---|---|
| **Compatible OpenAI** (générique) | SDK `openai` avec URL de base ; couvre OpenAI, Groq, OpenRouter, Mistral, Ollama, vLLM, LM Studio, LocalAI… | 1 |
| **Anthropic** (natif) | SDK `anthropic` | 1 |
| **Embeddings locaux** | `fastembed` dans le worker (§13) ; ou modèle d'embeddings d'un fournisseur via l'adaptateur générique | 1 |
| **Images** | Adaptateur générique (points d'accès compatibles) puis adaptateurs dédiés selon les fournisseurs retenus | 2 |
| **Adaptateur LiteLLM** (facultatif) | Pour qui veut un fournisseur non couvert : la plateforme parle au **proxy LiteLLM** de l'utilisateur via le protocole compatible, sans embarquer la bibliothèque | 2, documentation seulement |

Compléments techniques :

| Besoin | Choix |
|---|---|
| Sortie structurée | Schémas définis en **modèles Pydantic**, convertis en JSON Schema pour les fournisseurs qui supportent la sortie contrainte ; sinon, consigne + validation + réparation bornée (§10.4 de l'architecture) |
| Estimation avant appel (réservation de budget) | Taille d'entrée estimée par un compteur de jetons approché (`tiktoken`, MIT, pour les familles compatibles ; à défaut caractères ÷ 3,5 avec marge de 20 %) + sortie maximale demandée |
| Coût réel | Jetons **renvoyés par le fournisseur** × tableau des prix |
| Tableau des capacités et des prix | **Fichier de données versionné** dans le dépôt, modifiable par l'administrateur ; peut être initialisé à partir de données publiques sous licence libre (par exemple le fichier de prix de LiteLLM, sous MIT), sans dépendre de la bibliothèque |
| Reprises et délais | `tenacity` (Apache-2.0) ou logique propre de la passerelle, avec erreurs normalisées |
| Tests | Fournisseur **factice déterministe** pour l'intégration continue ; jeux d'enregistrements anonymisés pour les tests de non-régression des adaptateurs |

**Pourquoi pas Pydantic AI dès le lot 1** : aux lots 1 et 2, chaque appel est un **appel unique à sortie structurée** ; Pydantic AI apporterait surtout sa gestion d'agents, inutile avant le lot 3 (§12). Il est retenu **à l'intérieur des étapes d'agent** à partir du lot 3. S'il s'avérait meilleur que les adaptateurs maison (S4), il pourrait aussi servir de base aux adaptateurs, toujours derrière le contrat interne.

**Preuve de concept S4** : même usage (« rédaction » avec schéma de références de sources) exécuté sur 4 fournisseurs (un modèle local via Ollama, Groq, OpenRouter, Anthropic) ; mesure du taux de sorties valides sans réparation, du coût, de la durée.

---

## 12. Cadre d'agents et point de vigilance 2 — Place des agents dans les premiers lots

### 12.1 Rappel des décisions

D6 et ADR-05 : l'automatisation est faite de **pipelines déterministes** ; un agent est une **étape de proposition** sans effet externe, avec outils en lecture, budget et nombre d'itérations bornés (§11.5 de l'architecture). L'architecture place les premiers agents bornés (tri, brief) au **lot 3** (§24 de l'architecture).

### 12.2 Ce que l'utilisateur obtient sans agent

Une grande partie de ce que le cahier des charges appelle « agents autonomes » est livrée **sans agent** dès les lots 1 et 2, par des étapes de pipeline qui appellent un modèle une fois, avec une sortie structurée :

| Besoin exprimé | Réalisation sans agent | Lot |
|---|---|---|
| « L'IA trie ma veille » | Score explicable (lexical, sémantique, source, fraîcheur) + **classification par un petit modèle** dans l'étape de tri, au niveau 2 (propositions) | 1 |
| « L'IA me propose des articles » | Étape « proposer un brief » : un appel structuré à partir d'un élément ou d'un regroupement | 1 |
| « L'IA rédige » | Étape « rédaction » (UC-07) | 1 |
| « Ça tourne tout seul chaque matin » | **Recettes** de pipeline planifiées (« digest quotidien », « veille + brouillons à valider ») | 2 |
| « L'IA illustre » | Étape « illustration » avec le modèle d'image de la marque | 2 |

### 12.3 Où un agent apporte réellement quelque chose

Un agent (boucle où le modèle choisit ses outils et itère) n'est justifié que lorsque **le nombre et l'ordre des étapes ne sont pas connus à l'avance**. Dans ce produit, trois cas s'y prêtent :

| Agent candidat | Pourquoi une boucle est utile | Outils en lecture | Lot proposé |
|---|---|---|---|
| **Recherche de sources complémentaires** pour un brief | Il faut chercher, lire, juger si la source corrobore, recommencer | Rechercher dans la veille de l'espace, lire un élément, demander une récupération au module Collecte (avec ses contrôles) | 3 |
| **Préparation de dossier** (regroupement → plan d'article avec angles et sources) | Exploration de plusieurs éléments et regroupements liés | Rechercher, lire, lire la ligne éditoriale | 3 |
| **Contrôle factuel approfondi** (§23) | Pour chaque affirmation, chercher le passage qui l'étaye, éventuellement dans d'autres sources | Rechercher dans les archives et la veille | 3 ou 4 |

### 12.4 Décision : place des agents par lot

| Lot | Place des agents | Ce qui est livré pour les préparer |
|---|---|---|
| **Lot 1** | **Aucun agent.** Étapes d'IA à appel unique seulement | Contrat « étape » avec effets déclarés ; journal des actions automatiques (F-AUT-07) ; budgets par exécution ; PDP. Tout ce dont un agent aura besoin pour être borné existe déjà |
| **Lot 2** | **Aucun agent en production.** Constitution des **jeux d'évaluation** (briefs acceptés ou rejetés, tris corrigés) à partir de l'usage réel | Jeux d'évaluation ; outillage de mesure (§21) ; contrat « étape d'agent » (outils déclarés, itérations et coût maximum) publié en version expérimentale |
| **Lot 3** | **Premiers agents bornés**, au **niveau 2 uniquement** (propositions dans la boîte de travail) : recherche de sources complémentaires, préparation de dossier | Bibliothèque d'agents (§12.5) à l'intérieur de l'étape ; simulation ; désactivation sur anomalie |
| **Lot 4** | Agents fournis par des **modules** (F-AUT-09) ; protocole standard d'outils éventuel (Model Context Protocol, §9.6 de l'architecture) ; contrôle factuel approfondi | Protocole hors processus |

**Critère d'entrée d'un agent en production** : sur le jeu d'évaluation, il fait **mieux que l'étape déterministe équivalente** (taux d'acceptation des propositions, qualité jugée) pour un **coût par exécution borné** et connu. Sinon, l'étape déterministe reste.

**Pourquoi cette prudence** : les agents sont la partie la plus coûteuse, la moins prévisible et la plus exposée à l'injection de prompt (R-T04) ; les livrer tôt, avant les jeux d'évaluation et les mécanismes de supervision, irait contre le rang 1 des moteurs d'architecture. Les repousser ne retire rien de visible à l'utilisateur des lots 1 et 2 (§12.2).

### 12.5 Choix du cadre d'agents (pour le lot 3)

| Critère | Pydantic AI | LangGraph | CrewAI | OpenAI Agents SDK | smolagents | Boucle maison |
|---|---|---|---|---|---|---|
| Licence | MIT | MIT | MIT | MIT | Apache-2.0 | — |
| Multi-fournisseurs (dont local) | Oui | Oui (via LangChain) | Oui | Oui, orienté OpenAI | Oui | Oui (passerelle) |
| Outils typés, sortie structurée | **Oui, natif** | Oui | Partiel | Oui | Partiel | À écrire |
| Bornes (itérations, jetons, coût) | **Limites d'usage intégrées** | À configurer | Limitées | Partielles | Limitées | À écrire |
| Agents multiples, rôles | Possible | **Graphes d'états riches** | **Cœur du produit** | Transferts entre agents | Possible | Non |
| Modèle d'exécution | Boucle d'outils | Graphe d'états avec persistance | Équipes d'agents | Boucle + transferts | **Agents qui écrivent et exécutent du code** | Boucle d'outils |
| Poids des dépendances | Modéré | Élevé (écosystème LangChain) | Élevé | Faible | Faible | Nul |
| Adéquation à ADR-05 | **Bonne** | Bonne mais surdimensionnée (le moteur de pipelines du projet joue déjà ce rôle) | Faible (autonomie multi-agents, peu de contrôle) | Moyenne | **Rejeté** : exécution de code généré, contraire à P3 | Bonne |

**Décision** : **Pydantic AI**, utilisé **uniquement à l'intérieur d'une étape d'agent**, avec ses appels de modèle routés par la **passerelle IA du projet** (budgets, journal, confidentialité ; MD4) et des **outils fournis par le projet** (lecture seule, données de l'espace et de la marque de l'exécution). **Repli** : une boucle d'outils maison, simple à écrire une fois la passerelle disponible ; c'est aussi l'option si Pydantic AI ne permet pas de faire passer ses appels par la passerelle sans contournement (à vérifier dans S4).

LangGraph, CrewAI et les autres cadres d'orchestration ne sont **pas** retenus : l'orchestration (enchaînement, reprise, persistance, supervision) est la responsabilité du moteur de pipelines du projet, et c'est précisément ce qui garantit les promesses de sûreté.

---

## 13. Similarité, dédoublonnage et embeddings

### 13.1 Exigences

Dédoublonnage à trois niveaux (URL normalisée, empreinte exacte, quasi-doublon) ; garde-fou de **similarité par source** combinant mesures lexicales (recouvrement de séquences de mots, plus longue séquence commune) et sémantiques (embeddings par passage), avec passages surlignés ; embeddings **locaux possibles** sur CPU (P9 : le garde-fou ne doit pas dépendre d'un fournisseur) (§13.1 et §14.4 de l'architecture).

### 13.2 Décision

| Besoin | Choix | Licence | Justification |
|---|---|---|---|
| Normalisation d'URL | `url-normalize` ou règles propres (suppression des paramètres de suivi, casse, barre finale) | MIT | Simple ; règles documentées et testées |
| Empreinte exacte | SHA-256 du texte normalisé (Unicode NFC, espaces, ponctuation) | — | Bibliothèque standard |
| Quasi-doublons à l'échelle | **MinHash + LSH** sur bardeaux de 5 mots (`datasketch`) ; signatures stockées en base | MIT | Méthode de référence pour les reprises de dépêches ; coût constant par élément |
| Recherche approximative de titres | **`pg_trgm`** | PostgreSQL | Déjà dans la base |
| Similarité lexicale du garde-fou | **Recouvrement de n-grammes** (n = 5 à 8 mots) entre l'article et chaque source : taux de couverture et passages communs ; **plus longue séquence commune** par `rapidfuzz` | MIT | Déterministe, explicable (passages exacts surlignés), non manipulable par injection |
| Similarité sémantique du garde-fou | Découpage en passages (≈ 2 à 3 phrases), embeddings, appariement des passages les plus proches au-delà d'un seuil | — | Détecte la paraphrase proche (CJ-01) |
| Embeddings locaux | **`fastembed`** (exécution ONNX sur CPU, sans PyTorch : image plus légère) | Apache-2.0 | Tient dans le budget mémoire solo (§3.2) |
| Modèle par défaut | Modèle **multilingue compact** (dimension 384, licence Apache-2.0 ou MIT), par exemple de la famille `multilingual-e5-small` ou `paraphrase-multilingual-MiniLM` ; choix final par S5 | Selon modèle | FR et EN au minimum (D10) |
| Repli | `sentence-transformers` (Apache-2.0) si un modèle utile n'existe pas en ONNX | Apache-2.0 | Plus lourd (PyTorch) |
| Segmentation en phrases | `pysbd` (MIT) ou règles par langue | MIT | |

**Débit estimé sur 2 vCPU** (à mesurer dans S5) : un modèle compact traite de l'ordre de quelques dizaines de passages courts par seconde sur CPU. Le profil solo maximal (5 000 éléments par jour, soit environ 0,06 élément par seconde en moyenne) et le contrôle de quelques articles par jour sont largement absorbés par la file `ia`.

**Calibration (S5)** : corpus FR et EN de paires (source, article) annotées : reprises quasi littérales, paraphrases proches, synthèses légitimes. Les seuils par défaut du garde-fou sont fixés pour que **toute reprise quasi littérale** soit bloquée (rappel visé ≥ 95 %) en acceptant des faux positifs, que la revue humaine tranche (R-T10).

---

## 14. Collecte et extraction

| Besoin | Choix | Licence | Justification |
|---|---|---|---|
| Client HTTP commun avec protection SSRF | **`httpx`** avec transport personnalisé : résolution DNS contrôlée, refus des plages privées, de bouclage, de liaison locale et de métadonnées après chaque résolution et chaque redirection (§13.2 de l'architecture) | BSD | Synchrone et asynchrone, HTTP/2, délais et tailles bornés ; la protection SSRF est une **brique du projet**, testée indépendamment |
| Flux RSS / Atom / JSON Feed | **`feedparser`** | BSD | Référence depuis 2002, tolérant aux flux malformés |
| OPML | Analyse XML standard (`defusedxml` contre les attaques XML) | PSF | |
| Extraction du contenu principal | **`trafilatura`** | Apache-2.0 | Parmi les meilleurs résultats publiés en extraction générique ; extrait aussi auteur, date, langue, licence ; maintenu |
| Repli d'extraction | `readability-lxml` | Apache-2.0 | Algorithme de type « lecture » |
| robots.txt | **`protego`** (issu de Scrapy) | BSD | Prend en charge la spécification moderne (RFC 9309) |
| Réserve de fouille (TDMRep, balises et en-têtes) | **Module propre** : lecture de `/.well-known/tdmrep.json`, des en-têtes HTTP et des métadonnées de page | — | Aucune bibliothèque mûre ; le protocole est simple |
| Assainissement HTML | **`nh3`** (liaison Python d'`ammonia`, en Rust) | MIT | Rapide, liste blanche stricte ; remplace `bleach`, abandonné |
| Texte invisible, normalisation Unicode | Règles propres sur l'arbre HTML (`lxml`) + `unicodedata` | BSD | Spécifique au risque d'injection de prompt (§10.5 de l'architecture) |
| Détection de langue | **`py3langid`** | BSD | Léger et rapide ; `lingua-py` (Apache-2.0) en option plus précise mais plus gourmande en mémoire |
| Dates | `dateparser` (BSD) pour les dates libres ; `zoneinfo` | BSD | Multilingue |
| Sites autorisés à extraction spécifique (lot 4) | Règles déclaratives (sélecteurs CSS) par site ; **pas de navigateur sans tête** par défaut | — | Un navigateur sans tête (Playwright) consomme 300 Mo à 1 Go : il serait un module facultatif, dans un conteneur séparé, si un besoin réel apparaît |

---

## 15. Générateur de site

### 15.1 Exigences

Site 100 % statique, **constructions incrémentales** (seules les pages touchées), thèmes dérivés de l'identité de marque, fichiers SEO (sitemaps, flux, robots, données structurées, canoniques, OpenGraph), redirections adaptées à la cible, recherche statique, déploiement différentiel (SFTP, FTP, Git, dossier, stockage objet) (§16.5 de l'architecture).

### 15.2 Évaluation

| Critère | Intégré (Python + Jinja2) | Hugo | Astro / Eleventy | Zola | Pelican |
|---|---|---|---|---|---|
| Licence | BSD (Jinja2) | Apache-2.0 | MIT | MIT | AGPL-3.0 |
| Environnement d'exécution supplémentaire | **Aucun** | Binaire Go (un fichier) | **Node.js** | Binaire Rust | Aucun (Python) |
| Incrémental selon le graphe du produit (article → listes, tags, flux, sitemaps) | **Oui, par construction** : la plateforme sait ce qui a changé | Reconstruction complète (très rapide) puis différence | Partiel | Reconstruction complète | Partiel |
| Source des contenus | Instantanés en base, directement | Fichiers Markdown à exporter à chaque construction | Idem ou chargeurs de données | Fichiers | Fichiers |
| Thèmes contribuables | Jinja2 : connu des développeurs Python | Gabarits Go : syntaxe moins accessible | Composants JS : vivier large | Tera (proche de Jinja2) | Jinja2 |
| Fichiers SEO, données structurées, redirections par cible | À écrire | Largement intégrés | Intégrations | Intégrés | Greffons |

### 15.3 Décision

**Générateur intégré** au module Site, en Python, avec **Jinja2** pour les gabarits de thème, et **Pagefind** pour la recherche statique.

- La plateforme dispose déjà de tout ce qu'un générateur externe demande : les contenus (instantanés), le rendu HTML (moteur de rendu central, §14.5 de l'architecture), le graphe des dépendances entre pages. Un générateur externe obligerait à **exporter** les contenus sous forme de fichiers à chaque construction, puis à **réimporter** le résultat : un aller-retour sans valeur, et une seconde syntaxe de thèmes.
- Le travail réellement à écrire (sitemaps, flux, robots, données structurées, fichiers de redirection par serveur cible) est **de taille modeste et bien spécifié** (F-SEO-05 à 13) ; il doit de toute façon être piloté par les données de la plateforme.
- **Pagefind** (MIT) produit un index de recherche statique interrogé dans le navigateur ; il est distribué en binaire et via un paquet Python qui l'embarque : pas de Node.js à l'exécution.
- **Déploiement** : SFTP avec `paramiko` (LGPL-2.1) ou `asyncssh` (EPL-2.0 ou GPL-2.0+, à confirmer compatible ; `paramiko` préféré) ; FTP/FTPS avec `ftplib` (bibliothèque standard) ; Git avec l'exécutable `git` en sous-processus ; stockage objet via l'adaptateur S3 (§16). Différence calculée par empreinte de fichier.
- **Repli** : Hugo, si l'effort de maintenance du générateur intégré s'avérait trop élevé ; le module Site exporterait alors les instantanés en fichiers Markdown et données.

---

## 16. Stockage de fichiers

| Besoin | Choix | Licence |
|---|---|---|
| Interface | **Port interne `Stockage`** : écrire par empreinte, lire, flux, URL signée, supprimer, lister par préfixe d'espace | — |
| Adaptateur disque local (défaut) | Système de fichiers, arborescence `espace/type/empreinte`, écriture atomique (fichier temporaire puis renommage) | — |
| Adaptateur compatible S3 | **`boto3`** (ou `aioboto3` pour l'asynchrone) ; testé contre au moins deux implémentations libres (Garage, SeaweedFS) et un fournisseur cloud | Apache-2.0 |
| URL signées publiques (Instagram, TikTok, lot 3) | Signature HMAC propre servie par l'application, ou URL présignée S3 | — |

Pas de couche d'abstraction générique supplémentaire (`fsspec`, `obstore`) : l'interface du projet est petite et deux adaptateurs suffisent ; une telle bibliothèque pourra servir à écrire d'autres adaptateurs plus tard.

---

## 17. Médias

| Besoin | Choix | Licence | Remarque |
|---|---|---|---|
| Traitement d'images (recadrages, rendus par format, recompression des imports) | **Pillow** | HPND (permissive) | Protection contre les « bombes de décompression » activée ; **ré-encodage systématique** des images importées (supprime les charges malveillantes) |
| Repli pour gros volumes | `pyvips` (LGPL-2.1) | LGPL | Plus rapide et plus économe ; ajoute une bibliothèque native |
| Détection du type réel | `python-magic` (MIT) / `libmagic` | MIT / BSD | |
| Métadonnées IPTC « source numérique : IA » | **ExifTool** en sous-processus | GPL / Artistic | Outil de référence pour écrire IPTC et XMP ; appelé comme programme séparé |
| Manifestes de provenance **C2PA** | **`c2pa-python`** (Content Authenticity Initiative) | MIT ou Apache-2.0 | Signature avec un certificat de l'instance ; à confirmer dans le lot 2 (maturité, coût de la gestion des certificats) |
| Vidéo (lot 4) | **FFmpeg** (construction LGPL) en sous-processus, dans la file `medias` ; synthèse vocale par la passerelle IA ou un moteur local (ex. Piper, MIT) | LGPL | Coût CPU élevé : documenté comme incompatible avec le profil solo minimal |

---

## 18. Authentification

### 18.1 Évaluation

| Option | Atouts | Écarts |
|---|---|---|
| **Fournisseur d'identité séparé** (Keycloak, Authentik, Zitadel, Ory Kratos) | Fonctions complètes (2FA, WebAuthn, OIDC, fédération) | **Un composant de plus**, souvent lourd (Keycloak : JVM, ≥ 512 Mo) ; contraire à P7 et au budget solo ; dépendance de toute l'instance à un second produit |
| **Greffons d'authentification pour FastAPI** | Démarrage rapide | Projets de petite taille, à la maintenance incertaine, sur la fonction la plus sensible |
| **Implémentation propre sur bibliothèques éprouvées** | Pas de composant supplémentaire ; règles propres au produit (ré-authentification pour les actions sensibles, R2) faciles à intégrer | Code de sécurité à écrire et à faire relire |

### 18.2 Décision

**Module Identité et accès propre**, construit **exclusivement** sur des bibliothèques spécialisées et éprouvées, sans cryptographie écrite par le projet :

| Fonction | Bibliothèque | Licence | Lot |
|---|---|---|---|
| Hachage des mots de passe | **`argon2-cffi`** (Argon2id, paramètres OWASP) | MIT | 1 |
| Sessions | Sessions **côté serveur** en base, cookie opaque `HttpOnly`, `Secure`, `SameSite=Lax` ; rotation à la connexion | — | 1 |
| Protection CSRF | Jeton synchronisé par session + vérification de l'origine | — | 1 |
| Jetons d'API | Jetons aléatoires (`secrets`), stockés **hachés**, à portée limitée (§18.2 de l'architecture) | — | 1 |
| Limitation des tentatives | Compteurs en base (pas de Redis requis) | — | 1 |
| TOTP | **`pyotp`** | MIT | 2 |
| Clés de sécurité, clés d'accès (WebAuthn / passkeys) | **`webauthn`** (py_webauthn, Duo Labs) | BSD | 2 (option) |
| OpenID Connect (organisations) | **`Authlib`** (client OIDC) | BSD | 4 |
| Chiffrement des secrets par enveloppe (ADR-11) | **`cryptography`** (AES-GCM, clés de données par espace) | Apache-2.0 / BSD | 1 |

Une **revue de sécurité externe** du module Identité et accès et du chiffrement des secrets est inscrite comme jalon avant la première version publique (à reprendre dans `ROADMAP.md`). Les organisations qui veulent un fournisseur d'identité séparé le branchent via OIDC au lot 4 : le choix leur reste ouvert sans être imposé à tous.

---

## 19. Conteneurisation, proxy et livraison

### 19.1 Conteneurs

| Option | Constat |
|---|---|
| **Images OCI + fichier Compose** | Standard ouvert (OCI, spécification Compose) ; fonctionne avec **Docker Engine** (Apache-2.0) et **Podman** (Apache-2.0) ; documenté par tous les hébergeurs de VPS ; c'est la forme la plus simple d'installation reproductible |
| Kubernetes / Helm | Utile pour l'instance partagée ; disproportionné pour solo et petite rédaction. Un graphique Helm pourra être **contribué** plus tard, à partir de la même image |
| Paquets système (deb, rpm), installation manuelle | Matrice de distributions à maintenir ; mises à jour plus risquées ; contraire à R-O05 |

**Décision** : **image OCI unique multirôle** (`api`, `worker`, `scheduler`, `all-in-one` choisis par une variable ou un argument au démarrage) et **fichier Compose** pour les topologies solo et petite rédaction. La piste « Docker » est donc retenue, formulée de manière **neutre** : Docker Engine et Podman sont supportés tous deux, Docker Desktop (propriétaire) n'est jamais requis sur un serveur Linux. **L'installation sans conteneurs n'est pas supportée officiellement** (documentation communautaire possible) : c'est un arbitrage de pérennité, à confirmer (DT4).

| Élément de l'image | Choix |
|---|---|
| Base | `python:3.x-slim` (Debian) : compatibilité des roues binaires (ONNX, `cryptography`, Pillow) ; image « distroless » évaluée plus tard |
| Construction | Multi-étapes : étape Node.js pour construire l'interface (fichiers statiques copiés dans l'image finale, **sans Node.js**), étape `uv` pour les dépendances Python |
| Utilisateur | Non-root, système de fichiers en lecture seule hors volumes de données |
| Architectures | `amd64` et `arm64` (VPS ARM et Raspberry Pi 5 en serveur domestique) |
| Signature et nomenclature | Images signées (**cosign**, Sigstore, Apache-2.0) et nomenclature logicielle SBOM publiée (§19.5 de l'architecture) |
| Registre | Registre public de la forge du projet ; miroir sur un second registre pour ne pas dépendre d'un seul service |

### 19.2 Proxy inverse

| Critère | Caddy | Traefik | nginx |
|---|---|---|---|
| Licence | Apache-2.0 | MIT | BSD |
| TLS automatique (Let's Encrypt, renouvellement) | **Natif, par défaut** | Natif | Possible (module ACME récent ou outil externe) |
| Simplicité de configuration | **Très simple** (quelques lignes) | Moyenne (étiquettes de conteneurs) | Moyenne |
| Mémoire | Faible | Faible | Très faible |

**Décision** : **Caddy** dans le fichier Compose par défaut. Les installateurs qui ont déjà un proxy (nginx, Traefik, Apache) le gardent : la documentation fournit les configurations équivalentes et l'application ne dépend d'aucune fonction propre à Caddy.

---

## 20. Observabilité

| Signal | Choix | Licence | Remarque |
|---|---|---|---|
| Journaux structurés | **`structlog`** (sortie JSON), identifiants de corrélation propagés par variables de contexte | MIT / Apache-2.0 | Filtre systématique des secrets et du contenu des prompts |
| Métriques | **`prometheus-client`** : point d'accès `/metrics` facultatif | Apache-2.0 | Le **tableau de santé intégré** lit les mêmes métriques en base : aucun Prometheus requis en solo |
| Traces | **OpenTelemetry** (SDK Python et instrumentations FastAPI, SQLAlchemy, httpx), export **désactivé par défaut** | Apache-2.0 | Pour les installations avancées |
| Erreurs | Journaux + tableau de santé ; intégration facultative avec un service compatible Sentry (auto-hébergeable, ex. GlitchTip) | — | Jamais activée par défaut (aucune télémétrie sans consentement, §21 de l'architecture) |

---

## 21. Qualité, tests et chaîne d'approvisionnement

| Besoin | Choix | Licence |
|---|---|---|
| Tests du back-end | **`pytest`** ; tests de base de données contre un vrai PostgreSQL éphémère (conteneur) | MIT |
| Tests de propriétés (PDP, machine à états de publication, résolution des politiques) | **`hypothesis`** : génération de cas pour démontrer les promesses R1 à R5 | MPL-2.0 |
| Tests de concurrence et de pannes de la file | Scénarios dédiés (workers tués, baux expirés, coupures réseau simulées) | — |
| Tests d'isolation entre espaces | Suite générée sur chaque point d'API (§8.1 de l'architecture) | — |
| Tests de conformité des contrats d'extension | Suites `pytest` publiées pour les contributeurs (§9.7 de l'architecture) | — |
| Tests de bout en bout de l'interface | **Playwright** | Apache-2.0 |
| Accessibilité | **`axe-core`** dans les tests Playwright | MPL-2.0 |
| Analyse statique | `ruff` (MIT), `mypy` ou `pyright` (MIT), ESLint et TypeScript strict pour l'interface | MIT |
| Sécurité du code | `bandit` (Apache-2.0) ou règles de sécurité de `ruff` ; analyse de dépendances (`pip-audit`, Apache-2.0 ; `npm audit`) | — |
| Licences des dépendances | Vérification automatique des licences Python et npm à chaque intégration (filtre du §1.1) | — |
| Évaluations IA (garde-fous, contrôle factuel, agents) | **Jeux d'évaluation versionnés** exécutés par `pytest` ; outil dédié (**Inspect**, MIT, ou **promptfoo**, MIT) à évaluer au lot 2 | MIT |
| Chaîne d'approvisionnement | Dépendances **verrouillées avec empreintes** (`uv.lock`, fichier de verrouillage npm) ; mises à jour par robot avec délai de quarantaine de quelques jours avant adoption d'une nouvelle version (leçon de l'incident LiteLLM de mars 2026) ; publications d'images signées | — |

La forge (GitHub, Codeberg / Forgejo, GitLab) et le service d'intégration continue sont des choix de **gouvernance du projet**, hors du §26 de l'architecture ; ils seront traités dans `ROADMAP.md`. Aucun choix de ce document n'en dépend.

---

## 22. Point de vigilance 3 — Simplification UX de la Marque en mode solo

### 22.1 Problème

La Marque (D11) est nécessaire au modèle : elle porte la ligne éditoriale, l'identité, les canaux, les politiques et les articles. Mais pour la cible prioritaire (D4 : solo), **espace + marque + site** forme trois notions là où l'utilisateur n'en perçoit qu'une : « mon blog ». Le risque R-P05 (complexité perçue) est réel, et la règle RM1 (« sélecteur masqué tant qu'il n'y a qu'une marque ») ne suffit pas : les **réglages** restent répartis entre deux niveaux (sources et budget dans l'espace, ligne éditoriale et politiques dans la marque), et l'héritage entre niveaux est difficile à comprendre.

### 22.2 Principe

**La Marque existe toujours dans les données et dans l'API ; elle n'existe pas dans l'interface solo tant qu'elle n'apporte rien.** L'utilisateur solo voit **une seule chose** : sa publication, désignée par **son propre nom** (« Le Carnet Tech »), jamais par le mot « marque ».

### 22.3 Règles d'interface

| ID | Règle | Détail |
|---|---|---|
| **UXM1** | **Un réglage, un seul endroit** | En mode solo, un écran **Paramètres** unique, organisé par sujet et non par niveau : *Identité éditoriale* (marque), *Sources et veille* (espace), *IA et budget* (espace), *Site et canaux* (marque), *Automatisation* (marque). L'utilisateur ne voit jamais deux versions d'un même réglage |
| **UXM2** | **Pas d'héritage visible** | Quand un réglage existe à deux niveaux (budget, profils IA, politiques), l'interface solo écrit à **un seul** niveau, fixé par le produit (budget et profils IA : espace ; politiques : marque). Aucun indicateur « hérité de » n'est affiché |
| **UXM3** | **Vocabulaire neutre** | Le mot « marque » n'apparaît pas ; « espace » non plus. Les libellés parlent de « votre publication », « votre site », « vos sources » |
| **UXM4** | **Création implicite à partir du site** | À la connexion du site principal (WordPress ou Ghost, lot 1), la plateforme **pré-remplit** nom, description, langue, fuseau et icône à partir des informations publiques du site (racine de l'API REST WordPress, réglages du site Ghost). L'utilisateur confirme en un écran |
| **UXM5** | **Ligne éditoriale facultative au démarrage** | Seuls le nom et la langue sont obligatoires. La ligne éditoriale a des valeurs par défaut ; une **suggestion** peut être proposée plus tard à partir de 3 à 5 articles existants du site (étape d'IA au niveau 2 : proposition à accepter ou modifier) |
| **UXM6** | **Révélation progressive** | Le niveau Marque apparaît seulement quand l'utilisateur **choisit** d'« ajouter une autre publication ». À ce moment : une explication unique (« vos sources et votre veille sont partagées ; chaque publication a son ton, son site et ses réseaux »), le sélecteur de publication, et les réglages réorganisés par niveau. Archiver la seconde publication ramène l'interface solo |
| **UXM7** | **Équipe sans marques multiples** | Inviter un membre fait apparaître les rôles, **pas** les marques ; les deux révélations sont indépendantes |
| **UXM8** | **Ce qui reste visible** | Le nom de la publication apparaît là où il a un effet : mention IA, bloc Sources, aperçu de publication, signature |

### 22.4 Traduction technique

| Élément | Choix |
|---|---|
| **Profil d'interface** | Calculé par le serveur et renvoyé au démarrage de session : nombre de marques actives, de membres, de canaux, présence d'un site principal. L'interface conditionne ses composants à ce profil, jamais à un réglage manuel « mode solo » qui pourrait diverger des données |
| **API** | Toujours explicite : chaque ressource d'article, de canal ou de politique est sous `/marques/{id}/…` ; l'interface solo résout la marque par défaut silencieusement. Les intégrations tierces n'ont donc jamais à changer quand une seconde marque apparaît |
| **Écran Paramètres** | Assemblé par l'interface à partir des ressources d'espace et de marque ; chaque champ sait où il s'enregistre (UXM2) |
| **Internationalisation** | Clés de libellés distinctes pour le mode solo et le mode multi-marques (pas de substitution de mot dans une même phrase, qui casserait les traductions) |
| **Tests** | Parcours de bout en bout Playwright **dans les deux modes**, et test de la transition solo → deux marques → solo |

### 22.5 Mesures de réussite (proposées)

| Mesure | Cible au lot 1 |
|---|---|
| Écrans entre la fin de l'installation et le premier brouillon | ≤ 6 (parcours du §7.7 de l'analyse) |
| Champs obligatoires sur ce parcours | ≤ 10, clé d'API IA comprise |
| Temps jusqu'au premier brouillon sourcé, pour un nouvel utilisateur | ≤ 15 minutes |
| Test d'utilisabilité | 5 utilisateurs solo en fin de lot 1 : aucun ne doit devoir comprendre la notion de marque pour publier son premier article |

---

## 23. Point de vigilance 4 — Stratégie long terme du contrôle factuel

### 23.1 Ce qui est réaliste, et ce qui ne l'est pas

- Un système automatique **ne peut pas établir qu'une affirmation est vraie**. Il peut établir, avec une fiabilité mesurable, qu'une affirmation **est ou n'est pas étayée par les sources fournies**. C'est la seule promesse que le produit fera (H6 : il ne certifie jamais la véracité).
- Le risque principal (R-T02, hallucinations, criticité 9) vient du **rédacteur IA lui-même** : chiffres déformés, dates inventées, citations recomposées, attributions erronées. C'est précisément ce que la vérification « contre les sources fournies » détecte le mieux.
- Les erreurs **des sources elles-mêmes** (une source fiable qui se trompe) relèvent de la **corroboration** entre sources et, au bout du compte, du jugement humain.

### 23.2 Stratégie en quatre couches, déployée par lots

| Couche | Question | Méthode | Nature | Lot |
|---|---|---|---|---|
| **C1. Citations et chiffres** | « Ce nombre, cette date, cette citation figurent-ils dans les sources ? » | **Déterministe** : citations comparées mot pour mot (déjà prévu) ; **extraction des nombres, dates, pourcentages et montants** de l'article par règles localisées (FR, EN), normalisation (« 3,5 millions » = 3 500 000), recherche dans les textes archivés des sources | Reproductible, non manipulable par injection, explicable | **1** (proposé : avancé du lot 2 au lot 1 pour la partie chiffres et dates) |
| **C2. Affirmations étayées** | « Chaque affirmation de l'article est-elle soutenue par un passage d'une source ? » | **Décomposition** de l'article en affirmations atomiques par un modèle ; pour chacune, **recherche** des passages candidats dans les sources archivées (embeddings, §13) ; **jugement d'implication** (étayée / contredite / non étayée) par un modèle **différent du rédacteur**, ou par un modèle local d'inférence textuelle (NLI) si l'évaluation le montre suffisant | Indicatif ; passages affichés côte à côte | **2** (prévu par l'architecture) |
| **C3. Corroboration et contradictions** | « Ce fait est-il rapporté par plusieurs sources indépendantes ? Des sources se contredisent-elles ? » | Comparaison des affirmations entre les éléments d'un **regroupement** ; indépendance estimée (éditeurs distincts, pas de reprise de dépêche détectée par MinHash) ; signalement des contradictions entre sources | Indicatif ; aide à la décision | **3** |
| **C4. Références externes** (facultatif) | « Ce fait sur une entité est-il cohérent avec une base de connaissances ouverte ? » | Connecteurs **facultatifs** : **Wikidata** (données CC0) pour les faits stables sur les entités (dates de naissance, fonctions, lieux) ; bases de vérifications publiées au format **ClaimReview** (via des API tierces, désactivées par défaut car souvent propriétaires) | Indicatif ; jamais obligatoire (CT-02) | **4** |

**Un agent** (§12.3) peut rendre C2 et C3 plus complets au lot 3 ou 4, en allant chercher le passage qui manque ; il reste une étape de proposition.

### 23.3 Règles permanentes

| ID | Règle |
|---|---|
| **CF1** | Un contrôle factuel ne peut **que bloquer ou alerter**, jamais rendre une action plus permissive (§14.4 de l'architecture) |
| **CF2** | Le vocabulaire affiché est « **non étayé par les sources fournies** » ou « **contredit par telle source** », jamais « faux » ou « vrai » |
| **CF3** | Le vérificateur est, par défaut, **un modèle différent** du rédacteur (§10.3 de l'architecture) ; l'interface signale quand ce n'est pas le cas |
| **CF4** | Un contrôle ne peut devenir **bloquant par défaut** que si son évaluation (§23.5) atteint le seuil fixé **pour la langue et le modèle utilisés** ; sinon il reste une alerte, que l'utilisateur peut rendre bloquante en connaissance de cause |
| **CF5** | Chaque verdict est **attaché à la version** contrôlée et repris dans l'instantané publié (§15.2 de l'architecture) |
| **CF6** | Les corrections humaines (« cette alerte était fausse », « cette erreur n'a pas été vue ») sont **enregistrées** et alimentent le jeu d'évaluation |

### 23.4 Modèle de données

Une entité **Affirmation** est ajoutée au module Garde-fous (lot 2), sans toucher aux autres modules :

| Champ | Contenu |
|---|---|
| Version, bloc, position | Où se trouve l'affirmation dans le document structuré |
| Texte et type | Nombre, date, citation, attribution, fait général |
| Passages candidats | Références d'archives et positions dans le texte de la source |
| Verdict | Étayée, contredite, non étayée, non vérifiable |
| Méthode et modèle | Règle déterministe, NLI local, modèle IA (fournisseur, version du prompt) |
| Confiance | Score fourni par la méthode |
| Décision humaine | Confirmée, infirmée, ignorée (avec auteur et date) |

Ce modèle permet de faire évoluer les méthodes (meilleur modèle, NLI local, agent) **sans changer** l'interface ni l'instantané : seule la méthode change.

### 23.5 Évaluation continue (ce qui rend la stratégie durable)

La qualité d'un contrôle factuel **se dégrade ou s'améliore** à chaque changement de modèle, de prompt ou de langue. La stratégie long terme repose donc moins sur un algorithme que sur une **boucle de mesure** :

1. **Jeu d'évaluation de référence** constitué au lot 2 : articles générés à partir de sources réelles, avec erreurs **injectées** (chiffres modifiés, dates décalées, citations altérées, attributions inversées) et erreurs **réelles** relevées par les utilisateurs (CF6) ; FR et EN au minimum.
2. **Mesures** par contrôle, langue et modèle : **rappel** (part des erreurs détectées) et **précision** (part des alertes justifiées).
3. **Seuils de passage en bloquant** (proposés, à confirmer avec les premières mesures) : rappel ≥ 90 % et précision ≥ 80 % pour C1 ; C2 reste indicatif tant que la précision mesurée est sous 80 %.
4. **Non-régression** : tout changement de modèle par défaut, de prompt de contrôle ou de méthode rejoue le jeu d'évaluation dans l'intégration continue ; une baisse au-delà d'une tolérance bloque la modification.
5. **Transparence** : les résultats d'évaluation des méthodes par défaut sont publiés dans la documentation du projet (qualité annoncée = qualité mesurée).

### 23.6 Choix techniques associés

| Besoin | Choix | Lot |
|---|---|---|
| Extraction des nombres et dates (C1) | Règles par langue + `dateparser` ; formats numériques par `Babel` (BSD) | 1 |
| Décomposition en affirmations (C2) | Usage IA « contrôle factuel » de la passerelle, sortie structurée | 2 |
| Jugement d'implication local (C2, option) | Modèle NLI multilingue en ONNX, exécuté par le worker si l'évaluation le justifie ; sinon modèle génératif via la passerelle | 2 |
| Outillage d'évaluation | Jeux versionnés + `pytest` ; Inspect ou promptfoo à évaluer (§21) | 2 |
| Wikidata (C4) | Connecteur facultatif par l'API publique (SPARQL) | 4 |

---

## 24. Dépendances critiques et plans de sortie

Une dépendance est dite **critique** si son abandon ou un changement de licence bloquerait le produit. Pour chacune, le plan de sortie est connu dès maintenant.

| Dépendance | Gouvernance | Risque principal | Plan de sortie | Coût de sortie |
|---|---|---|---|---|
| **PostgreSQL** | Communautaire, sans éditeur dominant, depuis 1996 | Très faible | — | — |
| **`pgvector`** | Projet communautaire, très adopté, licence PostgreSQL | Faible | Base vectorielle dédiée derrière le port (§8.4) | Moyen |
| **Python** | PSF | Très faible | — | — |
| **FastAPI** | Mainteneur principal, entreprise associée | Moyen (gouvernance concentrée) | Litestar ou Starlette seul ; le domaine n'en dépend pas (§5.2) | Faible à moyen |
| **SQLAlchemy / Alembic** | Communautaire, depuis 2006 | Faible | — | Élevé, mais risque faible |
| **Pydantic** | Entreprise (Pydantic Services) et communauté | Faible | — | Élevé, mais risque faible |
| **React** | Fondation React (Linux Foundation) | Faible | Vue ; l'API et le format de document sont indépendants | Moyen (interface seule) |
| **ProseMirror** | Mainteneur principal (Marijn Haverbeke), financement participatif et entreprises | Moyen (mainteneur principal) | Format JSON documenté et propre au projet ; éditeur remplaçable | Moyen |
| **Tiptap** | Entreprise (modèle ouvert + offre commerciale) | Moyen (changement de cap commercial) | ProseMirror nu, même format | Faible à moyen |
| **`trafilatura`** | Mainteneur principal, origine académique | Moyen | `readability-lxml` en repli déjà prévu ; extraction derrière le port Connecteur de source | Faible |
| **SDK `openai` / `anthropic`** | Fournisseurs | Faible (le protocole compatible est un standard de fait) | Client HTTP direct sur le protocole | Faible |
| **Pydantic AI** (lot 3) | Entreprise Pydantic | Moyen (jeune) | Boucle d'outils maison | Faible |
| **Caddy** | Communautaire et entreprise | Faible | Tout autre proxy | Très faible |
| **Docker Engine / Compose** | Docker Inc. et communauté ; standards OCI et Compose | Faible | Podman, déjà supporté | Très faible |

---

## 25. Preuves de concept au démarrage du lot 1

Conformément à la phase actuelle, **aucune de ces preuves de concept n'est réalisée maintenant**. Elles sont proposées comme **première étape du lot 1**, une fois le code autorisé ; chaque choix marqué « confiance moyenne » pourra être révisé à leur issue, et la révision sera soumise à Joël.

| ID | Objet | Question à trancher | Choix concernés |
|---|---|---|---|
| **S1** | Charge PostgreSQL sur 2 vCPU / 4 Go | Les seuils du §8 tiennent-ils ? Coût réel de la RLS ? Mémoire réelle de la pile solo (§3.2) ? | TC-04, TC-05, §8 |
| **S2** | File de tâches | Module interne contre Procrastinate et DBOS : écriture transactionnelle, concurrence par clé, annulation ciblée, pannes de worker | TC-06 |
| **S3** | Format de document et éditeur | Aller-retour JSON ↔ HTML ↔ WordPress / Ghost ; collage depuis Word et Google Docs ; part d'IA ; comparaison de versions ; BlockNote contre Tiptap | TC-07 |
| **S4** | Passerelle IA | Usage « rédaction » sur 4 fournisseurs dont un local ; taux de sorties valides ; appels de Pydantic AI routés par la passerelle | TC-08, TC-09 |
| **S5** | Similarité et embeddings | Modèle d'embeddings par défaut (qualité FR / EN, mémoire, débit sur CPU) ; calibration des seuils du garde-fou | TC-10 |
| **S6** | Squelette de livraison | Image unique multirôle, Compose solo, Caddy, interface statique, installation sur un VPS vierge en moins de 15 minutes | TC-03, TC-13 |

---

## 26. Registre des décisions techniques

Format court, sur le modèle des ADR. Chaque décision pourra devenir un fichier séparé (`docs/adr/`) lors du passage en dépôt.

| ID | Décision | Alternatives écartées | Confiance | Révision possible après |
|---|---|---|---|---|
| **TC-01** | Python 3.12+ pour tout le back-end, typage strict vérifié | TypeScript, Go, Java, PHP | Élevée | — |
| **TC-02** | FastAPI limité à la couche d'entrée ; domaine indépendant du cadre ; SQLAlchemy 2, Alembic, psycopg 3, Pydantic v2 | Django, Litestar, Flask | Moyenne | Lot 2 (bilan de maintenance) |
| **TC-03** | Interface en SPA React + TypeScript + Vite, servie en fichiers statiques ; client d'API généré depuis OpenAPI ; React Aria ; i18next ; SSE | Next.js, Vue, SvelteKit, Jinja2 + htmx | Moyenne | S6 |
| **TC-04** | PostgreSQL 18+ seule base supportée, avec `pgvector`, `pg_trgm`, `unaccent`, RLS par espace | MariaDB, MySQL, SQLite | Élevée | S1 |
| **TC-05** | ADR-02 maintenu avec seuils de sortie mesurés (§8.5), leviers ordonnés (§8.4), ports stricts (§8.6) ; version majeure de PostgreSQL fixée par version majeure du produit | Composants dédiés dès le départ | Élevée | S1, puis tableau de santé |
| **TC-06** | Module Tâches interne sur PostgreSQL (file, baux, planificateur, verrou de leader) | Celery, Dramatiq, Temporal, Hatchet ; Procrastinate et DBOS en comparaison | Moyenne | S2 |
| **TC-07** | Format « Document plateforme v1 » au schéma ProseMirror publié ; éditeur Tiptap (extensions libres) ; moteur de rendu Python faisant foi | Lexical, Editor.js, BlockNote, Portable Text, HTML, Markdown | Moyenne | S3 |
| **TC-08** | Passerelle IA sur SDK officiels (`openai` générique, `anthropic` natif), tableau des capacités et prix en données ; pas de LiteLLM embarqué | LiteLLM, LangChain, Pydantic AI comme base | Élevée | S4 |
| **TC-09** | Aucun agent avant le lot 3 ; au lot 3, Pydantic AI à l'intérieur des étapes d'agent, appels routés par la passerelle ; critère d'entrée mesuré | LangGraph, CrewAI, OpenAI Agents SDK, smolagents | Moyenne | Lot 3 |
| **TC-10** | Similarité : n-grammes, MinHash / LSH (`datasketch`), `rapidfuzz`, `pg_trgm` ; embeddings locaux `fastembed` avec modèle multilingue compact | `simhash` seul, `sentence-transformers` par défaut | Moyenne | S5 |
| **TC-11** | Collecte : `httpx` avec protection SSRF propre, `feedparser`, `trafilatura`, `protego`, `nh3`, `py3langid`, module TDMRep propre | Scrapy, navigateur sans tête | Élevée | — |
| **TC-12** | Générateur de site intégré (Jinja2), recherche Pagefind, déploiement par `paramiko`, `ftplib`, `git`, S3 | Hugo, Astro, Eleventy, Zola, Pelican | Moyenne | Lot 2 |
| **TC-13** | Image OCI unique multirôle, Compose, Docker Engine ou Podman, Caddy ; images signées et SBOM ; pas d'installation hors conteneurs supportée officiellement | Kubernetes par défaut, paquets système | Élevée | S6 |
| **TC-14** | Authentification propre sur `argon2-cffi`, `pyotp`, `webauthn`, `Authlib`, `cryptography` ; sessions serveur en base ; revue de sécurité externe avant la première version publique | Keycloak, Authentik, Ory, greffons FastAPI | Moyenne | Revue de sécurité |
| **TC-15** | Médias : Pillow, ExifTool (IPTC), `c2pa-python` (à confirmer au lot 2), FFmpeg (lot 4) | `pyvips` par défaut | Moyenne | Lot 2 |
| **TC-16** | Observabilité : `structlog`, `prometheus-client`, OpenTelemetry facultatif, tableau de santé intégré | Pile de supervision obligatoire | Élevée | — |
| **TC-17** | Règles UX de la Marque en mode solo UXM1 à UXM8, profil d'interface calculé par le serveur, API toujours explicite | Mode solo réglable manuellement | Moyenne | Test d'utilisabilité fin de lot 1 |
| **TC-18** | Contrôle factuel en quatre couches (C1 déterministe au lot 1, C2 au lot 2, C3 au lot 3, C4 facultatif au lot 4), règles CF1 à CF6, évaluation continue | Contrôle par IA seul ; aucun contrôle avant le lot 2 | Moyenne | Lot 2 (premières mesures) |

---

## 27. Points à valider

Une recommandation est donnée pour chacun. Les points DT1 à DT4 et DT11 s'écartent des pistes initiales ou de l'architecture approuvée et méritent une attention particulière.

| ID | Question | Options | Recommandation |
|---|---|---|---|
| **DT1** | Back-end | Python + FastAPI / Python + Django / TypeScript | **Python + FastAPI**, avec les trois conditions du §5.2 (TC-01, TC-02) |
| **DT2** | Interface | Next.js / SPA React + Vite / autre cadre | **SPA React + Vite** ; Next.js non retenu pour l'application (§6.3) : son rendu serveur ne sert pas une application authentifiée et ajoute un environnement d'exécution, un conteneur et une surface d'attaque (TC-03) |
| **DT3** | Base et validité d'ADR-02 | PostgreSQL seul / composants dédiés dès le départ | **PostgreSQL 18+ seul**, ADR-02 maintenu avec les seuils et indicateurs du §8.5 ; premier plafond attendu : la recherche vectorielle (TC-04, TC-05) |
| **DT4** | Installation hors conteneurs | Supportée officiellement / documentation communautaire seulement | **Documentation communautaire seulement**, pour limiter la charge de maintenance (TC-13) |
| **DT5** | File de tâches | Module interne / Procrastinate / DBOS | **Module interne**, sous réserve de la comparaison S2 (TC-06) |
| **DT6** | Format de document | Schéma ProseMirror + Tiptap / autre | **Schéma ProseMirror publié + Tiptap**, sous réserve de S3 (TC-07) |
| **DT7** | Passerelle IA | Adaptateurs maison / LiteLLM / Pydantic AI | **Adaptateurs maison sur SDK officiels** ; LiteLLM seulement comme proxy externe facultatif (TC-08) |
| **DT8** | Place des agents | Dès le lot 1 / lot 3 / plus tard | **Aucun agent avant le lot 3** ; premiers agents au niveau 2 seulement, entrée conditionnée à l'évaluation ; Pydantic AI à l'intérieur des étapes (§12.4, TC-09) |
| **DT9** | Générateur de site | Intégré / Hugo / autre | **Intégré** (Jinja2 + Pagefind), Hugo en repli (TC-12) |
| **DT10** | Authentification | Module propre sur bibliothèques / fournisseur d'identité séparé | **Module propre**, revue de sécurité externe avant la première version publique ; fournisseur externe possible via OIDC au lot 4 (TC-14) |
| **DT11** | Contrôle factuel : vérification des chiffres et dates | Lot 2 (architecture actuelle) / **lot 1** | **Lot 1** pour la couche C1 (déterministe, peu coûteuse, cible directe de R-T02) ; C2 reste au lot 2 (TC-18) |
| **DT12** | Marque en mode solo | RM1 seule / règles UXM1 à UXM8 | **Règles UXM1 à UXM8**, avec les mesures de réussite du §22.5 (TC-17) |
| **DT13** | Preuves de concept | Avant la roadmap / première étape du lot 1 | **Première étape du lot 1**, une fois le code autorisé ; toute révision de choix qui en résulte est soumise à validation (§25) |

---

*Fin du document. Après validation (ou corrections) de ces choix et des points DT1 à DT13, l'étape suivante est `ROADMAP.md`, accompagnée du registre détaillé `RISKS.md`.*

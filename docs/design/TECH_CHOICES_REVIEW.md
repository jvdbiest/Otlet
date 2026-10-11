# Revue critique de cinq choix techniques

| Champ | Valeur |
|---|---|
| Document | `TECH_CHOICES_REVIEW.md` |
| Version | 1.0 |
| Date | 2026-10-11 |
| Objet | Revue volontairement sévère de TC-06, TC-12, TC-14, TC-07 et TC-02 (`TECH_CHOICES.md` v0.1), demandée par Joël avant `RISKS.md` et `ROADMAP.md` |
| Effet | Deux recommandations changent (TC-06, TC-12) ; deux sont renforcées (TC-07, TC-14) ; une décision liée est ouverte (TC-02 et TC-14 ensemble). `TECH_CHOICES.md` passe en v0.2 |

> Règle de lecture : pour chaque décision, on cherche d'abord **comment elle échoue**, pas pourquoi elle a été prise. Les coûts de changement sont des **ordres de grandeur en semaines de travail d'un développeur expérimenté** (s-d), estimés et non mesurés ; ils supposent que les ports internes prévus par l'architecture ont été respectés. Si cette discipline n'a pas été tenue, tous les coûts sont à multiplier par deux ou trois.

---

## Synthèse

| Décision | Risque | Coût d'un changement après le lot 1 | Verdict de la revue |
|---|---|---|---|
| **TC-06** Module Tâches interne | **Élevé** | Faible à moyen (2 à 4 s-d) | **Recommandation inversée** : bibliothèque existante par défaut, module interne seulement si S2 l'exige |
| **TC-12** Générateur de site intégré | Moyen | **Quasi nul** si décidé au lot 2 (rien n'est construit au lot 1) | **Décision reportée** au démarrage du lot 2 ; à ne pas valider maintenant |
| **TC-14** Authentification propre | **Élevé** (impact) | Moyen à élevé (4 à 8 s-d) | Maintenue **sous conditions** ; liée à TC-02 (question ouverte Q1) |
| **TC-07** ProseMirror + Tiptap | Moyen à élevé | **Élevé pour le format** (8 à 15 s-d et migration de tout le stock), moyen pour l'éditeur | Maintenue, **renforcée** : format propre au projet, instantanés rendus figés |
| **TC-02** FastAPI | Faible à moyen | Faible à moyen (2 à 5 s-d) | Maintenue ; son vrai coût est ce qu'il oblige à écrire (TC-14) |

**La plus fragile : TC-06.** C'est celle que j'abandonnerais aujourd'hui (§6).

---

## 1. TC-06 — Module Tâches interne sur PostgreSQL

### 1.1 Pourquoi elle pourrait échouer

1. **Son argument principal ne tient pas.** `TECH_CHOICES.md` §9.3 justifie le module interne par le couplage entre la file et la machine à états de publication (états « inconnu », « à vérifier », « suspendue »). À la relecture, c'est une **confusion de responsabilités** : ces états appartiennent à l'agrégat **Publication** (§8.3 et §12.4 de l'architecture), pas à la tâche. Une tâche de publication n'a besoin que de « réussie / à reprendre / abandonnée » ; c'est la Publication qui sait qu'un résultat est inconnu et qui programme un rapprochement. Une fois cette séparation faite, une file générique suffit.
2. **Les quotas par canal n'exigent pas une file à concurrence par clé.** Ils relèvent des compteurs lus par le PDP (§16.4 de l'architecture) : une tâche refusée pour quota est reprogrammée. Le second argument tombe aussi.
3. **Les bogues de file sont les pires bogues possibles ici.** Un bail qui expire pendant qu'un worker lent travaille encore produit une **double exécution**. Pour une publication, la clé d'idempotence et le rapprochement limitent les dégâts ; pour un appel IA payant, une génération d'image ou un déploiement de site, rien ne les limite. Ces bogues n'apparaissent qu'en charge, sur des pannes réelles, chez des utilisateurs : exactement là où un petit projet ne les voit pas.
4. **Pièges d'exploitation discrets** : les verrous consultatifs de session et `LISTEN` cessent de fonctionner derrière un regroupeur de connexions en mode transaction (PgBouncer), que des installateurs ajouteront tôt ou tard ; un horloge système décalée fausse les baux ; une transaction longue ailleurs dans l'application bloque le nettoyage de la table des tâches.
5. **Coût d'opportunité** : chaque semaine passée sur la file est une semaine retirée à ce qui différencie le produit (garde-fous, traçabilité, PDP). Une file n'apporte aucune valeur visible à l'utilisateur.

### 1.2 Signaux précoces

| Signal | Où le voir |
|---|---|
| S2 montre que l'écriture transactionnelle est réalisable avec Procrastinate ou DBOS : le module interne n'a plus de justification | Preuve de concept S2 |
| Le module dépasse le périmètre « réserver, exécuter, reprendre, planifier » (apparition d'états métier dans la table des tâches) | Revue de code |
| Tests de concurrence intermittents (« flaky ») dans l'intégration continue | Intégration continue |
| Toute double exécution observée en production, même une seule | Journal des tâches, coûts IA en double |
| Tâches bloquées « en cours » signalées par des utilisateurs | Tableau de santé, tickets |

### 1.3 Coût d'un changement après le lot 1

**Faible à moyen : 2 à 4 s-d**, à condition que l'interface du module Tâches soit respectée : remplacer l'adaptateur, vider la file avant la migration, réécrire les tests d'intégration. Le coût monte nettement si des états métier ont fui dans la table des tâches (risque réel avec le module interne, puisqu'il « peut tout faire »).

### 1.4 Estimation du risque

**Élevé**, non pas parce que la technique est difficile, mais parce que la décision **combine une probabilité réelle de bogues graves et une justification qui ne résiste pas à l'examen**.

### 1.5 Nouvelle recommandation

- **Par défaut : Procrastinate** (bibliothèque Python, MIT, sur PostgreSQL), déjà aligné sur ADR-02. **DBOS Transact** est l'alternative comparée dans S2.
- **Séparation stricte** : la file ne connaît que des tâches ; les états de publication, le rapprochement et les quotas restent dans les modules Publication et Automatisation.
- **Module interne seulement si S2 démontre un manque bloquant** (écriture dans la transaction applicative impossible, annulation ciblée impossible), avec la liste exacte de ce qui manque.
- **Durée maximale d'une tâche** déclarée par type, bail toujours supérieur à cette durée, et **effets externes toujours protégés par une clé d'idempotence**, quelle que soit la file.

---

## 2. TC-12 — Générateur de site intégré (contre Hugo)

### 2.1 Pourquoi elle pourrait échouer

1. **Sous-estimation du périmètre.** « Un peu de Jinja2 » devient : pagination, archives par date, catégories, tags, auteurs, flux par catégorie, images adaptatives (`srcset`), données structurées par type de page, `hreflang` (lot 4), pages d'erreur, fichiers de redirection pour Apache, Netlify, Cloudflare et pages HTML de repli, prévisualisation locale. Hugo a mis dix ans à couvrir ces cas ; le projet les rejoue seul.
2. **L'incrémental est une source de bogues silencieux.** Un article corrigé dont la page de tag n'est pas régénérée : aucune erreur, juste un site faux. Comme le site est le **pivot** de chaque marque (D12), un site incohérent touche directement le référencement et la crédibilité.
3. **Pas d'écosystème de thèmes.** Les contributeurs de thèmes connaissent Hugo, Astro ou WordPress ; personne ne connaît « les thèmes Jinja2 de la plateforme ». Le site généré risque de rester avec un ou deux thèmes, ce qui le rend peu attractif face à un WordPress existant.
4. **Concurrence avec le cœur.** Le générateur arrive au lot 2, en même temps que l'équipe, les médias et le contrôle factuel : il est très exposé à être bâclé.

### 2.2 Signaux précoces

| Signal | Où le voir |
|---|---|
| Une page obsolète détectée (contenu différent d'une reconstruction complète) | Test de comparaison incrémental / complet |
| Plus de 30 % du temps du lot 2 consommé par le générateur | Suivi du lot |
| Demandes répétées de thèmes ou de fonctions présentes « de base » dans Hugo | Tickets |
| Problèmes SEO remontés par la Search Console des premiers utilisateurs | Retours utilisateurs |

### 2.3 Coût d'un changement après le lot 1

**Quasi nul**, et c'est l'enseignement principal : **rien du générateur n'est construit au lot 1** (D13 : CMS externe au lot 1). Le choix peut donc être pris au début du lot 2 avec plus d'informations, sans rien perdre. Après le lot 2, le coût deviendrait moyen (4 à 6 s-d, plus la réécriture des thèmes).

### 2.4 Estimation du risque

**Moyen** si le choix est fait au lot 2 sur une preuve de concept ; il n'y a aucune raison de le prendre maintenant.

### 2.5 Nouvelle recommandation

- **Reporter la décision au démarrage du lot 2**, avec une preuve de concept comparative : générateur intégré contre Hugo alimenté par un export des instantanés (Markdown + données).
- Quel que soit le choix : **la reconstruction complète est la référence**, l'incrémental n'est qu'une optimisation, et un test compare régulièrement les deux sorties.
- Le lot 1 doit seulement garantir que les **instantanés** contiennent tout ce qu'un générateur, intégré ou externe, demandera (déjà prévu au §15.2 de l'architecture).

---

## 3. TC-14 — Authentification propre

### 3.1 Pourquoi elle pourrait échouer

1. **C'est la surface la plus attaquée, écrite par une équipe qui n'en est pas spécialiste.** Les bibliothèques retenues règlent la cryptographie, pas les **parcours** : réinitialisation de mot de passe (jetons réutilisables, énumération de comptes par les messages d'erreur), changement d'adresse e-mail, fixation de session, invalidation des sessions après changement de mot de passe, codes de secours du 2FA, limitation de débit contournable par rotation d'adresses IP, ré-authentification pour les actions sensibles (R2). Chaque parcours est un endroit où une faille passe.
2. **L'enjeu est supérieur à la moyenne.** Un compte compromis donne accès à des **jetons de publication** sur les sites et réseaux de l'utilisateur, et la possibilité d'activer la publication automatique. La promesse de rang 1 du produit (contrôle) dépend de l'authentification.
3. **La revue de sécurité externe n'est pas financée.** `TECH_CHOICES.md` la prévoit avant la première version publique, mais un projet open source naissant n'a souvent ni budget ni sponsor pour un audit. Sans elle, la condition qui rend TC-14 acceptable disparaît.
4. **Effet de cumul avec TC-02.** FastAPI ne fournit ni sessions, ni CSRF, ni réinitialisation de mot de passe. Choisir FastAPI, c'est choisir d'écrire tout cela. Django le fournit, éprouvé depuis 2005. Le score presque égal entre les deux (119 contre 118) a été tranché sans compter ce coût.
5. **OIDC au lot 4 bouleverse le modèle** : comptes liés à un fournisseur externe, provisionnement, déconnexion fédérée. Un modèle de comptes pensé uniquement pour les mots de passe se plie mal.

### 3.2 Signaux précoces

| Signal | Où le voir |
|---|---|
| Aucun financement ou sponsor identifié pour l'audit à la fin du lot 1 | Gouvernance du projet |
| Plus de 15 % du temps du lot 1 passé sur les parcours de compte | Suivi du lot |
| Premier signalement de vulnérabilité sur l'authentification | Politique de divulgation |
| Une auto-évaluation selon l'**OWASP ASVS niveau 2** laisse des exigences non couvertes | Liste de contrôle |

### 3.3 Coût d'un changement après le lot 1

**Moyen à élevé : 4 à 8 s-d.** Passer à un fournisseur d'identité externe (Keycloak, Authentik, Zitadel) impose : migration des empreintes de mots de passe (Argon2id est importable dans la plupart, mais à vérifier produit par produit), refonte des sessions et des jetons d'API, des écrans de compte, de la ré-authentification ; et surtout un **composant de plus** pour chaque installation, ce qui remet en cause le budget solo. Passer à Django pour l'authentification reviendrait à changer TC-02 : plus cher encore après le lot 1.

### 3.4 Estimation du risque

**Élevé**, par l'impact. La probabilité d'une faille est moyenne ; ses conséquences touchent la promesse centrale du produit.

### 3.5 Recommandation renforcée

TC-14 est maintenue, car un fournisseur d'identité séparé obligatoire coûte plus qu'il ne protège pour la cible solo. Mais elle devient **conditionnelle** :

- **Périmètre minimal au lot 1** : mot de passe, sessions serveur, jetons d'API, réinitialisation par e-mail, ré-authentification. TOTP au lot 2, WebAuthn et OIDC plus tard (déjà prévu).
- **Conformité OWASP ASVS niveau 2** sur ces parcours, vérifiée par une liste de contrôle versionnée et des tests dédiés.
- **Le modèle de comptes prévoit dès le lot 1 des identités externes** (un utilisateur, plusieurs moyens de connexion), pour que l'arrivée d'OIDC ne soit pas une refonte.
- **Question ouverte Q1** (§7) : si aucun audit externe n'est finançable, faut-il reconsidérer Django ?

---

## 4. TC-07 — ProseMirror + Tiptap

### 4.1 Pourquoi elle pourrait échouer

1. **C'est la décision la plus difficile à défaire, et ce n'est pas l'éditeur qui coûte, c'est le format.** Chaque version d'article est immuable, chaque instantané publié est figé (P5). Un format stocké dans des milliers de versions **ne disparaît jamais** : il faudra savoir le lire et le rendre pendant toute la vie du produit.
2. **Deux implémentations du même schéma** : l'éditeur (JavaScript) et le moteur de rendu (Python). Elles divergeront : l'aperçu dans l'éditeur ne correspondra plus exactement à ce qui est publié. C'est un bogue que les utilisateurs remarquent immédiatement et qui sape la confiance (« ce que je valide n'est pas ce qui part »).
3. **Les modèles écrivent du Markdown, pas du JSON ProseMirror.** Produire directement un arbre JSON valide, avec références de sources et origine des blocs, est fragile sur les petits modèles et les modèles locaux (CT-11). Il faudra un format intermédiaire et une conversion, donc une troisième implémentation.
4. **L'origine par bloc est mal définie.** Que vaut l'origine d'un paragraphe IA coupé en deux, fusionné avec un paragraphe humain, puis déplacé ? Si la règle est floue, le calcul de la part d'IA (D8, mention non désactivable) devient contestable, alors qu'il a des conséquences juridiques (transparence IA).
5. **Tiptap est une entreprise.** Elle a déjà déplacé des fonctions vers son offre payante et publié une version majeure en 2025 (v2 vers v3) qui a demandé des migrations. Le cap commercial peut se durcir.
6. **ProseMirror est exigeant.** Courbe d'apprentissage forte, mainteneur principal unique (bus factor), peu de contributeurs occasionnels capables d'écrire une extension correcte.

### 4.2 Signaux précoces

| Signal | Où le voir |
|---|---|
| Différences entre l'aperçu de l'éditeur et le rendu Python sur la suite de tests de référence | Intégration continue (test de concordance) |
| Pertes à l'aller-retour JSON → HTML → WordPress / Ghost | Preuve de concept S3 |
| Taux de sorties IA invalides au format cible supérieur à 5 % sur un modèle supporté | Preuve de concept S4 |
| Scénarios d'édition où la part d'IA calculée surprend l'utilisateur | Tests S3, retours utilisateurs |
| Fonction utile annoncée par Tiptap uniquement en offre payante | Notes de version de Tiptap |

### 4.3 Coût d'un changement après le lot 1

- **Changer d'éditeur** (Tiptap vers ProseMirror nu, ou vers un autre éditeur capable de produire le même schéma) : **moyen, 3 à 6 s-d**, si le format est bien celui du projet et non celui de Tiptap.
- **Changer de format** : **élevé, 8 à 15 s-d**, plus une migration de toutes les versions de tous les articles de toutes les installations, avec le risque de modifier rétroactivement des contenus validés. En pratique, on ne changera jamais de format ; on le fera **évoluer** par versions de schéma.

### 4.4 Estimation du risque

**Moyen à élevé** : probabilité moyenne de difficultés, coût de changement le plus élevé des cinq.

### 4.5 Recommandation renforcée

- Le format de référence est **le format du projet**, défini par son propre schéma JSON (compatible avec ProseMirror, mais spécifié et documenté indépendamment de Tiptap). Tiptap n'est qu'un adaptateur d'édition.
- **Les instantanés publiés conservent leurs rendus figés** (HTML et texte par canal, déjà produits au moment de la publication) : un ancien instantané n'a jamais besoin d'être re-rendu par un moteur plus récent. Seules les versions **non publiées** dépendent des migrations de schéma.
- **Format intermédiaire pour l'IA** : les modèles produisent un **Markdown balisé restreint** (références de sources sous forme de marqueurs simples), converti de façon déterministe vers le format du projet par le serveur. Testé dans S4.
- **Règles d'origine écrites et testées** avant le code de l'éditeur : division, fusion, déplacement, collage, réécriture assistée. Elles font partie des tests de propriétés (§21 de `TECH_CHOICES.md`).
- **Test de concordance** dans l'intégration continue : un corpus de documents rendu par l'éditeur et par le moteur Python, comparé après normalisation.

---

## 5. TC-02 — FastAPI

### 5.1 Pourquoi elle pourrait échouer

1. **Gouvernance concentrée.** FastAPI dépend d'un mainteneur principal ; des milliers de demandes de contributions restent longtemps en attente. Un ralentissement ou un changement de licence de l'entreprise associée est possible, même s'il n'est pas probable.
2. **Le minimalisme a un prix caché** : sessions, CSRF, réinitialisation de mot de passe, limitation de débit, et une partie de ce que Django donne d'office, sont à écrire (voir TC-14). Le coût réel de FastAPI se paie dans d'autres décisions.
3. **Pièges de l'asynchrone.** Les bibliothèques clés (`trafilatura`, Pillow, `feedparser`, ONNX) sont synchrones. Un appel bloquant dans un gestionnaire asynchrone fige toutes les requêtes du processus, sans erreur. La session asynchrone de SQLAlchemy ajoute des pièges (chargements paresseux interdits).
4. **L'injection de dépendances de FastAPI attire le domaine.** Il est très tentant d'utiliser `Depends` dans les services métier ; la frontière hexagonale s'érode sans que personne le décide.
5. **Pydantic est la vraie dépendance structurante.** La migration de Pydantic v1 vers v2 (2023) a coûté cher à tout l'écosystème ; les contrats d'extension exprimés en modèles Pydantic héritent de ce risque.

### 5.2 Signaux précoces

| Signal | Où le voir |
|---|---|
| Latence de l'API qui grimpe pendant les collectes ou les traitements d'images | Métriques (95ᵉ centile), détecteur de boucle bloquée |
| `import-linter` signale des imports FastAPI hors de la couche d'entrée | Intégration continue |
| Plus de 20 % du temps du lot 1 passé sur des fonctions « d'infrastructure Web » | Suivi du lot |
| Ralentissement net des versions de FastAPI ou de Starlette | Suivi des dépendances |

### 5.3 Coût d'un changement après le lot 1

**Faible à moyen : 2 à 5 s-d** vers Litestar ou Starlette seul, si le domaine est resté indépendant ; essentiellement la couche de routes, les dépendances d'authentification et la génération OpenAPI. Vers Django : 8 s-d ou plus, car l'accès aux données changerait aussi.

### 5.4 Estimation du risque

**Faible à moyen.** C'est la décision la plus réversible des cinq, à deux conditions : discipline hexagonale vérifiée automatiquement, et choix explicite du modèle d'exécution.

### 5.5 Précision ajoutée

- **Workers synchrones par défaut** ; asynchrone seulement dans l'API et dans le client HTTP de collecte. Les traitements lourds ne s'exécutent jamais dans le processus API.
- Les contrats d'extension publics sont décrits par des **schémas JSON** générés à partir des modèles Pydantic : un module communautaire dépend du schéma publié, pas de la version de Pydantic.

---

## 6. Si je devais en abandonner une aujourd'hui

**TC-06, le module Tâches interne.** C'est la plus fragile pour trois raisons cumulées :

1. **Sa justification ne résiste pas à l'examen** (§1.1) : les états qui la motivaient appartiennent au module Publication, pas à la file.
2. **Elle concentre des bogues graves et invisibles** (double exécution, tâches bloquées) dans un composant qui n'apporte rien de visible à l'utilisateur.
3. **Une alternative mûre existe, déjà compatible avec ADR-02** : Procrastinate, sur la même base, sans composant supplémentaire.

Ce n'est pas la décision la plus **risquée** : TC-14 a un impact potentiel plus grave et TC-07 coûte bien plus cher à défaire. Mais pour ces deux-là, il n'existe pas aujourd'hui d'alternative clairement meilleure dans les contraintes du projet ; la réponse est de les encadrer (§3.5, §4.5). Pour TC-06, l'alternative existe : c'est la seule qu'il faut abandonner.

---

## 7. Question ouverte

| ID | Question | Options | Recommandation |
|---|---|---|---|
| **Q1** | Si aucun audit de sécurité externe n'est finançable avant la première version publique, faut-il reconsidérer Django (TC-02) pour bénéficier de son authentification éprouvée ? | (a) FastAPI + authentification propre, audit recherché (sponsor, programme d'aide aux projets libres) ; (b) Django + Django Ninja, authentification intégrée | **(a)**, à condition qu'un financement ou un programme d'audit soit identifié avant la fin du lot 1 ; sinon **(b)** devient préférable. Le choix doit être fait **avant** le premier code, car il est coûteux après |

---

## 8. Modifications apportées à `TECH_CHOICES.md` (v0.2)

| Section | Modification |
|---|---|
| §2, §9.3, §26 (TC-06), §27 (DT5) | Procrastinate par défaut, DBOS en comparaison, module interne seulement sur manque bloquant démontré par S2 ; séparation file / états de publication |
| §2, §15.3, §26 (TC-12), §27 (DT9) | Décision du générateur reportée au démarrage du lot 2, sur preuve de concept intégré contre Hugo |
| §10.3 (TC-07) | Format propre au projet ; rendus figés dans les instantanés ; Markdown balisé restreint pour les sorties IA ; règles d'origine et test de concordance |
| §18.2 (TC-14) | Périmètre minimal, OWASP ASVS niveau 2, identités externes prévues ; renvoi à Q1 |
| §5.2 (TC-02) | Workers synchrones par défaut ; contrats publiés en schémas JSON |
| §27 | Ajout de DT14 (= Q1) |

# Registre des risques — Plateforme Open Source de Veille et de Diffusion IA

| Champ | Valeur |
|---|---|
| Document | `RISKS.md` |
| Version | 1.0 |
| Date | 2026-10-11 |
| Statut | **Validé par Joël le 2026-10-11** (DR1 à DR9 ; Q-R1 répondue) |
| Phase | Conception — aucun code |
| Documents d'entrée | `FUNCTIONAL_ANALYSIS.md` v0.2 (validée), `ARCHITECTURE.md` v0.1 (approuvée, DA1 à DA10), `TECH_CHOICES.md` v1.0 (validé, DT1 à DT14, DT14 option a), `TECH_CHOICES_REVIEW.md` v1.0 |
| Document suivant | `ROADMAP.md` |

**Historique**

| Version | Date | Changements |
|---|---|---|
| 0.1 | 2026-10-11 | Première version : registre détaillé annoncé au §13 de l'analyse fonctionnelle, réévaluation des 30 risques existants (dont un reclassé) à la lumière de l'architecture et des choix techniques validés, 37 risques nouveaux, nouvelle catégorie Sécurité, mitigations complémentaires et décisions à valider |
| 1.0 | 2026-10-11 | Validation par Joël : DR1 à DR9 adoptés ; réponse à Q-R1 (un développeur, 15 à 20 h par semaine, sans contributeur ni financement supposés) ; R-O09 relevé à 16 (aucun financement supposé), d'où 8 risques critiques résiduels |

> Ce document recense ce qui peut faire **échouer** le projet ou **nuire** à ses utilisateurs, mesure ce que les décisions déjà validées couvrent réellement, et dit franchement ce qu'elles ne couvrent pas. Il ne remet pas en cause les décisions validées (D1 à D13, DA1 à DA10, DT1 à DT14) ; quand une décision laisse un risque élevé, il propose une **mitigation complémentaire** ou une **décision à valider** (§9), jamais un retour en arrière silencieux.
>
> Le volet juridique **ne constitue pas un avis juridique**. Il identifie les questions à soumettre à un juriste (droit d'auteur et droits voisins, données personnelles, réglementation européenne du numérique), dans le contexte retenu : Union européenne et Belgique.

---

## Sommaire

1. [Méthode](#1-méthode)
2. [Synthèse : les risques qui peuvent faire échouer le projet](#2-synthèse--les-risques-qui-peuvent-faire-échouer-le-projet)
3. [Ce que les documents validés sous-estiment](#3-ce-que-les-documents-validés-sous-estiment)
4. [Fiches détaillées des risques majeurs](#4-fiches-détaillées-des-risques-majeurs)
5. [Registre complet](#5-registre-complet)
6. [Concentration des mitigations : points de défaillance uniques](#6-concentration-des-mitigations--points-de-défaillance-uniques)
7. [Mitigations complémentaires proposées](#7-mitigations-complémentaires-proposées)
8. [Exigences transmises à `ROADMAP.md`](#8-exigences-transmises-à-roadmapmd)
9. [Décisions à valider](#9-décisions-à-valider)
10. [Suivi du registre](#10-suivi-du-registre)
11. [Annexes](#11-annexes)

---

## 1. Méthode

### 1.1 Échelles

L'analyse fonctionnelle (§13) utilisait des échelles de 1 à 3, suffisantes pour un premier tri mais trop grossières pour arbitrer entre risques élevés. Ce registre passe à des échelles de **1 à 5**. La correspondance avec les anciennes cotations est donnée en annexe (§11.1).

| Note | Probabilité (P) sur la durée de vie du produit | Impact (I) |
|---|---|---|
| 1 | Rare : ne se produira probablement jamais | Négligeable : gêne passagère, aucun utilisateur lésé |
| 2 | Peu probable : possible dans des circonstances particulières | Limité : fonction dégradée, contournement simple, quelques jours de travail |
| 3 | Possible : s'est déjà produit dans des projets comparables | Sérieux : fonction majeure cassée, plusieurs semaines de reprise, utilisateurs gênés |
| 4 | Probable : se produira sauf action spécifique | Grave : préjudice pour un utilisateur ou un tiers (fuite, publication fautive, action en justice), ou plusieurs mois de reprise |
| 5 | Quasi certain : se produira, la seule question est quand | Critique : promesse centrale du produit rompue, responsabilité juridique engagée, ou fin du projet |

**Criticité** C = P × I, de 1 à 25.

| Criticité | Niveau | Traitement attendu |
|---|---|---|
| 15 à 25 | **Critique** | Mitigation obligatoire avant le lot concerné ; suivi à chaque revue ; plan de repli écrit |
| 9 à 14 | **Élevé** | Mitigation planifiée dans la roadmap ; indicateur suivi |
| 5 à 8 | **Modéré** | Mitigation dans le cours normal du travail |
| 1 à 4 | **Faible** | Accepté, revu à chaque fin de lot |

### 1.2 Deux cotations par risque

- **Cotation brute** : le risque si l'on construisait le produit décrit par le cahier des charges **sans** les protections spécifiques prévues.
- **Cotation résiduelle** : le risque **après** les mitigations déjà décidées dans les documents validés, **en supposant qu'elles sont livrées comme prévu**. C'est une hypothèse optimiste ; le §6 dit ce qui se passe si elle ne tient pas.

Un risque dont la cotation résiduelle reste critique signifie que **les décisions actuelles ne suffisent pas** : il appelle une mitigation complémentaire (§7) ou une décision (§9).

### 1.3 Identifiants et catégories

| Préfixe | Catégorie | Contenu |
|---|---|---|
| **R-T** | Technique | Conception, fiabilité, qualité, dépendances |
| **R-S** | Sécurité | Catégorie **nouvelle** : la sécurité était dispersée dans les risques techniques ; l'authentification propre (TC-14) et le multi-espaces justifient un suivi séparé |
| **R-J** | Juridique | Droit d'auteur, droits voisins, données personnelles, réglementation de l'IA et du numérique, licences |
| **R-O** | Opérationnel | Exploitation des instances, gouvernance et capacité du projet, comportement des utilisateurs |
| **R-P** | Produit et réputation | Valeur, adoption, image |

Les identifiants de l'analyse fonctionnelle sont **conservés** (R-T01 à R-T10, R-J01 à R-J08, R-O01 à R-O07, R-P01 à R-P05). Un seul est reclassé : R-T07 (fuite de secrets) est absorbé par **R-S03**, plus précis. Les nouveaux risques prennent les numéros suivants.

### 1.4 Responsables

Le projet n'a pas encore d'équipe. Les responsables sont donc des **rôles**, qui peuvent être tenus par la même personne au début :

| Rôle | Responsabilité |
|---|---|
| **Mainteneur principal** | Arbitrages de périmètre, gouvernance, publication des versions |
| **Responsable sécurité** | Authentification, isolation, secrets, chaîne d'approvisionnement, divulgation des vulnérabilités |
| **Responsable qualité IA** | Garde-fous, évaluations, passerelle IA, contrôle factuel |
| **Responsable connecteurs** | Connecteurs de publication et de collecte, suivi des API tierces |
| **Conseil juridique** (externe) | Revue juridique ponctuelle (§8.3) |

Tant que ces rôles sont tenus par une seule personne, R-O05 et R-O08 s'appliquent à chacun d'eux.

---

## 2. Synthèse : les risques qui peuvent faire échouer le projet

### 2.1 Vue d'ensemble

| Catégorie | Nombre | Critiques (brut) | Critiques (résiduel) | Élevés (résiduel) |
|---|---|---|---|---|
| Technique (R-T) | 20 | 6 | 1 | 9 |
| Sécurité (R-S) | 9 | 4 | 1 | 4 |
| Juridique (R-J) | 14 | 3 | 2 | 3 |
| Opérationnel (R-O) | 15 | 8 | 4 | 6 |
| Produit (R-P) | 8 | 2 | 0 | 4 |
| **Total** | **66** | **23** | **8** | **26** |

Lecture : les décisions validées font passer **23 risques critiques à 8**. C'est un bon résultat pour une architecture, mais les 8 qui restent ne sont pas des détails techniques : ce sont la **capacité du projet**, la **fiabilité de la validation humaine**, la **disponibilité légale des sources** et la **sécurité de l'authentification**. Aucune décision d'architecture ne les règle ; elles relèvent du périmètre, de la gouvernance, de l'interface et du droit.

### 2.2 Les dix risques prioritaires (cotation résiduelle)

À criticité résiduelle égale (12), le classement retient d'abord les risques du lot 1 dont l'impact est le plus élevé.

| Rang | ID | Risque | C brut | C résiduel | Pourquoi il reste haut |
|---|---|---|---|---|---|
| 1 | **R-O08** | Périmètre disproportionné par rapport à la capacité de développement | 25 | **20** | Le lot 1 seul contient une plateforme complète ; aucune hypothèse d'équipe ni de temps n'est encore posée |
| 2 | **R-T02** | Hallucinations publiées (faits, chiffres, citations, attributions) | 25 | **16** | Le contrôle factuel le plus utile (C2) n'arrive qu'au lot 2 ; tout repose sur la validation humaine |
| 3 | **R-O10** | Fatigue de validation : l'humain approuve sans relire | 20 | **16** | C'est la mitigation principale de six autres risques, et rien ne la protège dans les documents validés |
| 4 | **R-J09** | Assèchement des sources : réserves de fouille (TDM) généralisées dans la presse | 20 | **16** | Le respect strict du droit, choisi à raison, prive le produit d'une grande partie de sa matière première |
| 5 | **R-J04** | Diffamation ou fausse information publiée par un utilisateur | 20 | **15** | Conséquence directe de R-T02 et R-O10 ; l'utilisateur en porte la responsabilité, le projet en porte la réputation |
| 6 | **R-O05** | Épuisement ou départ du mainteneur ; abandon du projet | 20 | **15** | Les mitigations prévues sont architecturales ; la gouvernance et le financement ne sont pas traités |
| 7 | **R-S01** | Faille dans l'authentification propre | 15 | **15** (10 avec audit) | DT14 a écarté Django : l'audit externe devient la seule protection forte, et il n'est pas financé |
| 8 | **R-S09** | Instances auto-hébergées non mises à jour, porteuses de jetons de publication | 20 | **12** | Hors du contrôle du projet ; une faille connue reste exploitable des mois sur les instances oubliées |
| 9 | **R-J01** | Contrefaçon, y compris par **traduction** d'une source | 16 | **12** | Le garde-fou lexical ne voit pas une traduction ; seul le contrôle sémantique multilingue peut la voir |
| 10 | **R-T18** | Connecteurs WordPress et Ghost : idempotence et rapprochement non vérifiés | 16 | **12** | La machine à états de publication suppose une capacité (« vérifier l'existence ») que les deux CMS n'offrent pas nativement |

Depuis la réponse à Q-R1 (v1.0), **R-O09** (audit externe non financé, 16) rejoint les risques critiques résiduels : aucun financement n'étant supposé, la préversion sans audit (DR2) est le scénario de référence.

### 2.3 Verdict

Le projet est **techniquement bien défendu** : la sûreté de l'automatisation (PDP, niveaux, arrêt d'urgence, revérification de dernier moment), la fiabilité de la publication et la traçabilité sont parmi les parties les plus solides des documents. Le risque technique résiduel est modéré.

Le projet est **mal défendu là où l'architecture ne peut rien** :

1. **Faisabilité** : le périmètre du lot 1 est celui d'un produit mature, pas d'une première version (R-O08).
2. **Facteur humain** : six risques graves ont la même mitigation finale, « validation humaine par défaut », dont l'efficacité n'est ni mesurée ni protégée (R-O10).
3. **Matière première** : la valeur du produit dépend de sources que le droit européen permet de plus en plus de fermer à ce type de traitement (R-J09).
4. **Sécurité de l'identité** : avec FastAPI conservé, la sécurité des comptes repose sur du code écrit par le projet et sur un audit que personne ne finance encore (R-S01, R-O09).

Aucun de ces quatre points n'impose de revenir sur une décision validée. Tous imposent des **choix de roadmap** (§8) et quelques **décisions nouvelles** (§9).

---

## 3. Ce que les documents validés sous-estiment

Cette section est volontairement sévère. Elle ne dit pas que les documents sont faux ; elle dit où leur optimisme n'est pas encore justifié.

### 3.1 La validation humaine est traitée comme une garantie, alors que c'est une hypothèse

Dans l'analyse fonctionnelle (§13) et l'architecture (§23.3), « validation humaine par défaut » apparaît comme mitigation de **R-T02, R-T04, R-J01, R-J04, R-O03 et R-P01**. Or la littérature sur le **biais d'automatisation** est constante : un humain qui valide des propositions d'une machine globalement fiable finit par valider sans lire, d'autant plus vite que le volume augmente et que les erreurs sont rares. L'utilisateur solo, cible prioritaire (D4), est précisément celui qui veut gagner du temps et n'a personne pour relire derrière lui.

Rien dans les documents validés ne **mesure** la qualité de la validation (temps passé, passages signalés réellement consultés) ni ne **module** l'effort demandé selon le risque de l'article (personnes nommées, chiffres non étayés, source unique). La validation est une case à cocher. → **R-O10**, mitigations M-03 et M-04.

### 3.2 Le lot 1 n'est pas un produit minimal

Le lot 1 cumule : comptes et sessions conformes à l'**ASVS niveau 2**, multi-espaces avec **sécurité au niveau des lignes**, marques, **PDP**, file de tâches et planificateur, collecte RSS avec **protection SSRF**, robots.txt et **TDMRep**, veille à scores explicables avec embeddings locaux, passerelle IA multi-fournisseurs avec **budgets à réservation**, éditeur structuré avec **origine par bloc** et moteur de rendu Python **concordant**, garde-fous de similarité lexicale et sémantique, **contrôle factuel C1** (avancé par DT11), traçabilité avec archives et instantanés, **journal d'audit chaîné**, connecteurs WordPress et Ghost avec idempotence et rapprochement, SEO de base, interface FR et EN, API publique v1 documentée, sauvegarde et restauration, tableau de santé, six preuves de concept.

Chacun de ces éléments est justifié. Ensemble, ils représentent un volume de travail qui se compte en **dizaines de semaines-développeur** (ordre de grandeur non mesuré, à chiffrer dans `ROADMAP.md`). Pour une équipe d'une ou deux personnes, la première valeur utilisable arrive tard, et le risque d'abandon (R-O05) augmente avec chaque mois sans utilisateur. → **R-O08**, décision DR1.

### 3.3 La matière première est juridiquement plus fragile que le produit ne le suppose

Le produit transforme une veille en contenus. L'analyse fonctionnelle traite la réserve de fouille (art. 4 de la directive 2019/790) comme une règle de conformité à respecter à la collecte (CJ-03, F-CNF-06). C'est juste, mais incomplet : depuis 2023, une part croissante des éditeurs de presse européens **déclarent une réserve** (robots.txt visant les robots d'IA, protocole TDMRep, mentions dans les conditions d'utilisation). Un produit qui respecte ces réserves pourra collecter les titres et résumés des flux RSS, mais souvent **pas le texte intégral** des articles de presse les plus utiles.

Deux conséquences que les documents ne tirent pas :

1. La **qualité des synthèses** du lot 1 dépendra de flux souvent tronqués (résumé de quelques lignes), ce qui pousse vers la réécriture mono-source d'un résumé, exactement le cas que H5 voulait éviter.
2. La **tentation de contournement** par l'utilisateur sera forte (copier-coller du texte intégral dans la saisie manuelle). Le produit ne peut pas l'empêcher ; il doit au moins ne pas l'encourager. → **R-J09**, **R-J03**, mitigation M-08.

### 3.4 Le garde-fou de similarité ne voit pas les traductions

Le garde-fou repose sur un recouvrement de **n-grammes de mots** (déterministe, base des décisions automatiques) et sur une similarité **sémantique** par passages (indicative). Un article français rédigé à partir d'une source anglaise a un recouvrement lexical **nul**, même s'il en est une traduction quasi littérale, ce qui reste une œuvre dérivée au sens du droit d'auteur. Or la veille multilingue est un usage naturel du produit (D10 : contenus multilingues). Le garde-fou déterministe, présenté comme non manipulable, est ici simplement **aveugle**. → **R-J01**, **R-T10**, décision DR4.

### 3.5 La publication « sans doublon » suppose une capacité que les CMS du lot 1 n'ont pas nativement

L'architecture (§12.4) traite un résultat « inconnu » en **retrouvant** la publication côté canal (« Vérifier l'existence ») grâce à un marqueur d'idempotence enregistré dans une métadonnée de l'article (WordPress) ou un « champ dédié » (Ghost, §16.3). À vérifier, mais deux points sont probables :

- l'API REST de WordPress ne permet pas, sans code côté serveur (extension ou métadonnée déclarée), de **rechercher** un article par une métadonnée arbitraire ; elle permet d'écrire et de lire, pas de filtrer ;
- Ghost ne propose pas de **champs personnalisés** sur les articles ; un marqueur passerait par une étiquette interne, l'URL canonique ou l'injection de code, chacun avec des effets de bord.

Si ces points se confirment, le rapprochement sur les deux canaux du lot 1 sera **heuristique** (titre, date, auteur) ou exigera une **extension WordPress** fournie par le projet : un composant de plus, en PHP, à maintenir. → **R-T18**, preuve de concept S7 (§8.1).

### 3.6 Le chiffrement des secrets protège les sauvegardes, pas l'instance

Le chiffrement par enveloppe (ADR-11) protège les secrets contre une **fuite de la base ou d'une sauvegarde**. Il ne protège pas contre une **compromission du serveur** ou du processus applicatif, puisque la clé maîtresse est fournie au même processus par une variable d'environnement ou un fichier. Ce n'est pas un défaut de conception, c'est la limite normale d'une installation sur un seul serveur ; mais les documents ne le disent pas, et la conséquence est lourde : un mot de passe d'application WordPress hérite de **tous les droits** de l'utilisateur WordPress qui l'a créé, et une clé d'intégration Ghost donne des droits étendus sur le contenu du site. Une instance compromise donne donc la main sur les **sites principaux** de toutes les marques qu'elle gère. → **R-S03**, mitigation M-06.

### 3.7 Le projet est un fournisseur de système d'IA au sens du règlement européen

L'analyse fonctionnelle (CJ-05) situe les obligations de transparence du règlement sur l'IA chez l'**utilisateur qui publie**. C'est vrai pour l'obligation d'information du public (art. 50, §4). Mais l'art. 50, §2 impose aux **fournisseurs** de systèmes d'IA générant du texte ou des images un **marquage lisible par machine** des contenus produits, et l'exemption accordée aux logiciels libres (art. 2, §12) **ne couvre pas** les systèmes relevant de l'art. 50 (lecture à confirmer par le conseil juridique). Ces obligations s'appliquent depuis **août 2026** : le projet est conçu sous un régime déjà en vigueur. Le marquage lisible par machine d'un **texte** (par opposition à une image) n'a pas de solution technique mûre ; il faudra le définir avec les codes de pratique en cours d'élaboration. → **R-J05**.

### 3.8 Les évaluations continues supposent des données et un budget qui n'existent pas

La stratégie de contrôle factuel (TECH_CHOICES §23.5) et le critère d'entrée des agents (§12.4) reposent sur des **jeux d'évaluation** constitués « à partir de l'usage réel » au lot 2, rejoués dans l'intégration continue. Deux difficultés :

1. Un projet auto-hébergé **sans télémétrie** (§21 de l'architecture) ne voit pas l'usage réel de ses utilisateurs. Les corrections humaines (CF6) restent dans chaque instance. Le jeu d'évaluation devra être **construit par le projet** et alimenté par des contributions volontaires.
2. Rejouer des évaluations sur des **modèles payants** à chaque modification coûte de l'argent, à chaque exécution de l'intégration continue. Qui paie ? → **R-O11**.

### 3.9 Les instances auto-hébergées vieilliront

Le modèle auto-hébergé transfère la sécurité à l'installateur, non expert par hypothèse (CO-01). L'expérience des logiciels auto-hébergés (CMS, forums, outils de collaboration) est constante : une part importante des instances tourne avec des versions anciennes et vulnérables pendant des mois. Ici, chaque instance oubliée contient des **jetons de publication** vers des sites et des réseaux réels. Une faille connue du projet devient une faille exploitable **chez ses utilisateurs**, et donc un problème de réputation pour le projet. → **R-S09**.

### 3.10 La documentation de conception est volumineuse et non éprouvée

Les quatre documents validés totalisent environ 320 Ko. C'est une force pour la cohérence ; c'est aussi un risque : **aucune** des hypothèses chiffrées (mémoire du profil solo, débit des embeddings sur CPU, taux de sorties IA valides, seuils de similarité) n'a encore été vérifiée, et un document de cette taille diverge vite du code. Les preuves de concept S1 à S6 sont la bonne réponse ; elles doivent arriver **vite** et avoir le droit de **contredire** les documents. → **R-O15**.

---
## 4. Fiches détaillées des risques majeurs

Chaque fiche suit le même plan : description (cause, événement, conséquence), cotation, ce qui est déjà décidé, **ce qui manque**, mitigations complémentaires (renvoi au §7), signaux précoces, plan de repli. Les risques modérés et faibles sont traités directement dans le registre (§5).

### 4.1 R-O08 — Périmètre disproportionné par rapport à la capacité de développement

| | P | I | C |
|---|---|---|---|
| Brut | 5 | 5 | **25** |
| Résiduel | 4 | 5 | **20** |

**Description.** Le périmètre validé (quatre lots, environ 70 exigences fonctionnelles, 11 ADR, 18 décisions techniques, 6 preuves de concept) est dimensionné pour une équipe, alors que rien n'indique aujourd'hui qu'il y en aura une. Le lot 1 à lui seul est un produit complet (§3.2). Conséquences : première valeur utilisable tardive ; fatigue et abandon (R-O05) ; ou, pire, livraison dans les délais au prix des parties invisibles (tests d'isolation, ASVS, concordance du rendu, rapprochement), c'est-à-dire précisément des protections sur lesquelles reposent les cotations résiduelles de ce registre.

**Déjà décidé.** Découpage en lots (analyse §14) ; cœur réduit (P4) ; décisions qui retirent du travail : Procrastinate plutôt qu'une file maison (TC-06), générateur de site reporté (TC-12), aucun agent avant le lot 3 (TC-09), pas d'installation hors conteneurs (DT4).

**Ce qui manque.**
- Aucune **hypothèse de capacité** (nombre de personnes, temps disponible) : sans elle, la roadmap ne peut ni dater ni arbitrer.
- Aucune **distinction** dans le lot 1 entre ce qui est coûteux à ajouter plus tard (isolation, PDP, idempotence, format de document, instantanés) et ce qui ne l'est pas (seconde langue d'interface, second CMS, API publique stabilisée).
- Aucun **critère d'arrêt** : à quel signal le projet réduit-il son ambition plutôt que de glisser ?

**Mitigations complémentaires.** M-01 (lot 1 découpé en 1a et 1b), M-02 (hypothèse de capacité et critères d'arrêt dans `ROADMAP.md`). Décision DR1.

**Signaux précoces.** Preuves de concept S1 à S7 qui dépassent ensemble 15 % du temps prévu du lot 1 ; une fonction « invisible » (tests d'isolation, concordance, ASVS) repoussée « à plus tard » ; aucun utilisateur réel six mois après le début du code.

**Plan de repli.** Livrer le lot 1a seul comme première version publique (préversion), même si le lot 1b glisse ; geler les lots 3 et 4 tant que le lot 2 n'est pas utilisé.

**Lot / responsable.** Tous / mainteneur principal.

---

### 4.2 R-T02 — Hallucinations publiées

| | P | I | C |
|---|---|---|---|
| Brut | 5 | 5 | **25** |
| Résiduel | 4 | 4 | **16** |

**Description.** Le modèle invente ou déforme un chiffre, une date, une citation, une attribution (« selon le ministre… »), un lien de causalité. Le texte est fluide et plausible ; l'erreur n'est pas visible sans comparer aux sources. Publiée sous le nom de l'utilisateur, elle engage sa responsabilité (R-J04) et la crédibilité de sa publication.

**Déjà décidé.** Références de sources structurées par passage (TC-07) ; citations comparées mot pour mot (garde-fou bloquant, lot 1) ; **C1 avancé au lot 1** (nombres, dates, montants comparés aux sources archivées, DT11) ; C2 (affirmations étayées) au lot 2 ; sources affichées côte à côte ; validation humaine par défaut ; contrôles factuels « ne peuvent que bloquer ou alerter » (CF1).

**Ce qui manque.**
- **C1 ne voit que ce qui est chiffré.** Une attribution inventée, un fait sans nombre (« l'entreprise a été condamnée »), une personne confondue avec une autre passent C1 sans alerte. Ce sont les erreurs les plus diffamatoires.
- **C1 produira des faux positifs** sur des chiffres légitimement dérivés (« trois fois plus », arrondis, conversions de devises, pourcentages calculés). Si l'alerte sonne trop souvent, elle sera ignorée (R-O10). Le seuil « rappel ≥ 90 %, précision ≥ 80 % » (TECH_CHOICES §23.5) n'est atteignable qu'avec un jeu d'évaluation qui n'existe pas encore (R-O11).
- **Les personnes nommées** ne font l'objet d'aucun contrôle spécifique au lot 1, alors qu'elles concentrent le risque juridique.
- Entre le lot 1 et le lot 2, **la seule défense contre les affirmations non chiffrées est l'humain**, et l'humain fatigue (R-O10).

**Mitigations complémentaires.** M-03 (validation proportionnée au risque), M-04 (mesure locale de la qualité de validation), M-05 (garde-fou « liens et personnes » : toute personne nommée absente des sources est signalée dès le lot 1). Décisions DR5 et DR7.

**Signaux précoces.** Taux d'alertes C1 ignorées supérieur à 50 % ; corrections publiées (UC-15) dont la cause est une erreur factuelle ; signalement par un tiers d'une attribution erronée.

**Plan de repli.** Rendre C1 et le garde-fou « personnes » **bloquants par défaut pour les articles mentionnant une personne physique**, au prix de faux positifs ; avancer C2 si les mesures du lot 1 montrent qu'il est fiable sur un modèle local.

**Lot / responsable.** 1 et 2 / responsable qualité IA.

---

### 4.3 R-O10 — Fatigue de validation (biais d'automatisation)

| | P | I | C |
|---|---|---|---|
| Brut | 5 | 4 | **20** |
| Résiduel | 4 | 4 | **16** |

**Description.** La validation humaine est la mitigation finale de R-T02, R-T04, R-J01, R-J04, R-O03 et R-P01 (§3.1). Avec le temps, le volume, la fiabilité apparente des brouillons et l'absence de relecteur en mode solo, l'utilisateur valide **sans relire**. La validation existe dans le journal d'audit ; elle n'a pas eu lieu dans les faits. Toutes les cotations résiduelles qui la supposent sont alors fausses.

**Déjà décidé.** Validation par défaut (R1) ; passages signalés surlignés ; sources côte à côte ; niveaux 3 et 4 de publication encadrés (R2, lot 3) ; plafonds de publication qui limitent le volume (H10).

**Ce qui manque.** Toute **mesure** de la réalité de la validation, et toute **modulation** de l'effort selon le risque. Un article mono-source, nommant trois personnes, avec deux chiffres non retrouvés, se valide aujourd'hui avec le même bouton qu'une brève sans risque.

**Mitigations complémentaires.**
- **M-03 — Validation proportionnée au risque.** Chaque article reçoit un **niveau de risque calculé** (déterministe : personnes nommées, chiffres non étayés, source unique, similarité proche du seuil, sujet sensible déclaré par la marque). Au-delà d'un niveau, chaque signalement doit être **traité individuellement** (accepter, corriger, ignorer avec raison) avant que le bouton de validation ne s'active. Pas de validation groupée des brouillons IA à risque.
- **M-04 — Mesure locale.** Temps de relecture rapporté à la longueur, part des signalements ouverts, part des validations en moins de N secondes. Affichage **à l'utilisateur seul** (pas de télémétrie), sous forme de rappel bienveillant. Inscrit dans l'instantané (« validé après X min, Y signalements traités »), ce qui renforce aussi la valeur probante (R-J04).

**Signaux précoces.** Durée médiane de validation qui décroît mois après mois à volume constant ; signalements jamais ouverts ; corrections après publication.

**Plan de repli.** Pour les marques dont la mesure montre une validation superficielle, proposer un **délai de refroidissement** (publication au plus tôt N minutes après la fin de la rédaction) et une seconde lecture différée.

**Lot / responsable.** 1 / mainteneur principal (interface) et responsable qualité IA (calcul du risque).

---

### 4.4 R-J09 — Assèchement des sources par les réserves de fouille

| | P | I | C |
|---|---|---|---|
| Brut | 5 | 4 | **20** |
| Résiduel | 4 | 4 | **16** |

**Description.** Le droit européen permet aux titulaires de s'opposer à la fouille de textes et de données de leurs contenus par des moyens lisibles par machine (art. 4 de la directive 2019/790). Les éditeurs de presse utilisent de plus en plus ce droit (robots.txt visant les robots d'IA, TDMRep, conditions d'utilisation). La plateforme, qui respecte ces réserves (choix juste, F-CNF-06), ne pourra traiter pour beaucoup de sources de presse que les **titres et résumés** du flux RSS. Conséquences : synthèses pauvres, réécriture d'un résumé (H5), valeur perçue faible (R-P06), et contournement par l'utilisateur (copier-coller du texte intégral en saisie manuelle).

Une question de fond reste ouverte et relève du conseil juridique : même lorsqu'aucune réserve n'est exprimée, l'exception de fouille couvre-t-elle la **génération** d'un texte nouveau à partir des contenus fouillés, ou seulement leur **analyse** ? La réponse conditionne le discours du projet sur la légalité de son usage principal.

**Déjà décidé.** Respect automatique des réserves et journal de conformité par source ; type « site autorisé » avec autorisation consignée ; synthèse multi-sources par défaut ; aucune republication des archives.

**Ce qui manque.** La **visibilité** du problème pour l'utilisateur, et une **stratégie de sources** qui ne repose pas sur la presse sous réserve.

**Mitigations complémentaires.**
- **M-08 — Statut juridique visible par source** : « texte intégral utilisable », « résumé du flux seulement », « refusé », avec la raison. Quand un brouillon repose uniquement sur des résumés, il le dit.
- **Saisie manuelle encadrée** : champ « origine et droit d'usage du texte » obligatoire, avertissement explicite, et marqueur dans l'instantané. Le produit ne peut pas empêcher le contournement ; il refuse d'en être complice silencieux.
- **Catalogue de sources ouvertes** proposé à l'installation : sources institutionnelles et publiques (communiqués officiels, données publiques, publications sous licence libre), agences et éditeurs qui autorisent la réutilisation, flux de recherche en accès ouvert.
- Question inscrite à la **revue juridique** (M-15).

**Signaux précoces.** Part des sources configurées en « résumé seulement » supérieure à 50 % chez les premiers utilisateurs ; demandes répétées d'un mode « ignorer robots.txt » ; part croissante de saisies manuelles longues.

**Plan de repli.** Recentrer explicitement le positionnement sur la **veille et la curation commentée** (résumé court, lien, apport propre) plutôt que sur la réécriture, ce que H10 recommandait déjà ; explorer des connecteurs vers des sources **sous licence** (API d'agences ou d'éditeurs avec contrat), à la charge de l'utilisateur.

**Lot / responsable.** 1 / mainteneur principal et conseil juridique.

---

### 4.5 R-J04 — Diffamation ou fausse information publiée

| | P | I | C |
|---|---|---|---|
| Brut | 4 | 5 | **20** |
| Résiduel | 3 | 5 | **15** |

**Description.** Un article publié attribue à une personne identifiable un fait inexact et préjudiciable, par hallucination (R-T02), par injection dans une source (R-T04) ou par une source elle-même erronée. L'utilisateur, éditeur du contenu, en est responsable. Le projet n'est pas juridiquement responsable d'un usage qu'il ne contrôle pas, mais un cas médiatisé (« un logiciel libre d'IA a publié une fausse accusation ») atteint directement sa réputation (R-P01).

**Déjà décidé.** Validation par défaut ; contrôle factuel C1 (lot 1) puis C2 (lot 2) ; retrait en une action sur tous les canaux (UC-15) ; instantanés probants (ce qui a été diffusé, validé par qui) ; mention IA.

**Ce qui manque.** Le traitement spécifique des **personnes physiques** (§4.2) et la **qualité réelle de la validation** (§4.3). Le retrait rapide limite le préjudice, il ne le prévient pas.

**Mitigations complémentaires.** M-03, M-04, M-05. Documentation « usage responsable » expliquant la responsabilité d'éditeur et le droit de réponse (en Belgique comme ailleurs, la personne mise en cause dispose de recours ; le produit doit faciliter la correction et la publication d'un droit de réponse via UC-15).

**Signaux précoces.** Première demande de retrait ou de droit de réponse reçue par un utilisateur ; article retiré pour inexactitude.

**Plan de repli.** Rendre bloquant par défaut le contrôle des personnes nommées (§4.2, plan de repli).

**Lot / responsable.** 1 / responsable qualité IA.

---

### 4.6 R-O05 — Épuisement ou départ du mainteneur ; abandon du projet

| | P | I | C |
|---|---|---|---|
| Brut | 4 | 5 | **20** |
| Résiduel | 3 | 5 | **15** |

**Description.** Le projet repose sur une personne. La charge (R-O08), la maintenance continue imposée par des tiers (API de CMS et de réseaux, modèles IA, R-O14), le support des installations (R-O12) et la sécurité (R-S09) s'additionnent. Un départ laisse des instances en production, porteuses de secrets, sans correctifs.

**Déjà décidé.** Architecture qui permet de déléguer (contrats d'extension versionnés, tests de conformité, connecteurs isolés) ; un seul environnement d'exécution ; dépendances choisies pour leur pérennité.

**Ce qui manque.** Tout le volet **non technique** : gouvernance, recherche d'un second mainteneur, financement, continuité (qui détient le nom de domaine, le registre d'images, les clés de signature ?), politique de fin de vie.

**Mitigations complémentaires.** M-13 : contributions sous **DCO** (DR8) ; comptes du projet (forge, registre, domaine, clés de signature cosign) détenus par une **organisation** avec au moins deux administrateurs dès qu'un second contributeur régulier existe ; recherche de financement (programmes européens et nationaux de soutien aux logiciels libres, à vérifier au moment de la demande) ; **politique de fin de vie** publiée (annonce, dernière version de sécurité, export garanti des données).

**Signaux précoces.** Délai de réponse aux signalements de sécurité supérieur à 14 jours ; aucune contribution externe fusionnée en six mois ; mainteneur unique sur tous les rôles du §1.4 un an après la première version.

**Plan de repli.** Mode maintenance déclaré : plus de nouvelles fonctions, correctifs de sécurité seulement, export et migration documentés.

**Lot / responsable.** Tous / mainteneur principal.

---

### 4.7 R-S01 — Faille dans l'authentification propre (avec R-O09, audit non financé)

| | P | I | C |
|---|---|---|---|
| Brut | 3 | 5 | **15** |
| Résiduel sans audit externe | 3 | 5 | **15** |
| Résiduel avec audit externe | 2 | 5 | **10** |

**Description.** FastAPI ne fournit ni sessions, ni CSRF, ni réinitialisation de mot de passe, ni limitation de débit ; le module Identité et accès les écrit sur des bibliothèques éprouvées (TC-14). Les bibliothèques règlent la cryptographie, pas les **parcours** (réinitialisation, changement d'adresse, fixation de session, invalidation après changement de mot de passe, énumération de comptes, ré-authentification). Un compte compromis donne accès aux jetons de publication et à la configuration de l'automatisation : c'est la promesse de rang 1 du produit qui tombe.

DT14 a tranché pour FastAPI (option a). Le repli Django n'existe donc plus ; **l'audit externe devient la seule protection forte**, et il n'est pas financé (R-O09, cotation résiduelle 16 depuis la réponse à Q-R1 : aucun financement supposé).

**Déjà décidé.** Périmètre minimal au lot 1 ; conformité **OWASP ASVS niveau 2** vérifiée par liste de contrôle et tests ; modèle de comptes prévoyant plusieurs moyens de connexion (identités externes) dès le lot 1 ; ré-authentification pour les actions sensibles ; revue de sécurité externe **avant la première version publique** ; audit externe **activement recherché** (exigence ferme issue de DT14).

**Ce qui manque.**
- Une règle disant **ce qui se passe si l'audit n'a pas eu lieu** au moment de publier.
- Un **calendrier** de recherche de financement : un dossier de financement d'audit prend des mois entre la demande et la réalisation.
- Une **porte de sortie** pour les utilisateurs exigeants : l'OIDC est prévu au lot 4, ce qui laisse trois lots sans alternative à l'authentification maison.

**Mitigations complémentaires.** M-07 :
- Recherche de financement **dès le début du lot 1** (programmes européens de soutien aux logiciels libres d'intérêt général, fonds de souveraineté numérique, programmes d'audit dédiés aux projets libres ; disponibilité et conditions à vérifier au moment de la demande).
- **Auto-évaluation ASVS niveau 2 publiée** avec chaque version.
- **DR2** : aucune version qualifiée de « stable » sans audit externe du module Identité et accès et du chiffrement des secrets ; à défaut, publication en « préversion » avec avertissement explicite.
- **DR3** : avancer la **connexion OIDC** (client) au lot 2, en option, pour que les organisations puissent déléguer l'authentification à un fournisseur d'identité éprouvé.

**Signaux précoces.** Ceux de `TECH_CHOICES_REVIEW.md` §3.2 : aucun financement identifié à mi-lot 1 ; plus de 15 % du temps du lot 1 sur les parcours de compte ; exigences ASVS non couvertes.

**Plan de repli.** Préversion prolongée ; recommandation documentée de placer l'instance derrière un proxy d'authentification (accès restreint par réseau privé virtuel ou proxy d'authentification) pour les installations exposées.

**Lot / responsable.** 1 / responsable sécurité.

---

### 4.8 R-J01 et R-T10 — Contrefaçon et faiblesse du garde-fou de similarité

| | P | I | C |
|---|---|---|---|
| R-J01 brut | 4 | 4 | **16** |
| R-J01 résiduel | 3 | 4 | **12** |
| R-T10 brut | 4 | 4 | **16** |
| R-T10 résiduel | 3 | 4 | **12** |

**Description.** Un article reprend trop fidèlement l'expression d'une source : paraphrase proche, structure reprise paragraphe par paragraphe, ou **traduction** (§3.4). Le garde-fou de similarité ne le détecte pas, ou le détecte trop souvent à tort et l'utilisateur relève les seuils jusqu'à le rendre inutile.

**Déjà décidé.** Garde-fou bloquant par défaut combinant n-grammes (déterministe) et embeddings par passages ; calibration S5 visant un rappel ≥ 95 % sur les reprises quasi littérales ; synthèse multi-sources par défaut ; avertissement pour les articles mono-source (D7) ; archives jamais publiées.

**Ce qui manque.**
- **Inter-langues** : le recouvrement lexical est nul entre une source anglaise et un article français.
- **Structure** : une paraphrase qui suit l'ordre et le découpage de la source, phrase par phrase, peut passer sous les deux seuils.
- **Seuils modifiables** par espace sans garde-fou de second niveau : rien n'empêche un seuil absurde.

**Mitigations complémentaires.**
- **DR4 / M-09** : quand la langue de l'article diffère de celle d'une source, la mesure **sémantique multilingue** devient **bloquante** pour cette source (le modèle d'embeddings retenu est multilingue, TC-10) ; le corpus S5 inclut des paires de traductions.
- **Mesure d'alignement structurel** (ordre des passages appariés) ajoutée au rapport de similarité, en alerte au lot 1.
- **Bornes d'instance** sur les seuils : un espace peut durcir, pas assouplir au-delà d'une borne fixée par l'administrateur, et toute modification est tracée.

**Signaux précoces.** Taux de faux positifs mesuré par S5 supérieur à 20 % ; seuils relevés dans la majorité des espaces ; articles mono-source majoritaires.

**Plan de repli.** Rendre les articles mono-source **bloqués par défaut** (au lieu d'un avertissement), en contradiction partielle avec D7, sur décision de Joël.

**Lot / responsable.** 1 / responsable qualité IA.

---

### 4.9 R-S09 — Instances non mises à jour

| | P | I | C |
|---|---|---|---|
| Brut | 5 | 4 | **20** |
| Résiduel | 4 | 3 | **12** |

**Description.** Une faille est corrigée par le projet ; une part importante des instances ne se met pas à jour pendant des mois. Ces instances, exposées sur Internet, contiennent des jetons de publication vers des sites et réseaux réels. La faille, désormais publique, est exploitée.

**Déjà décidé.** Notification de nouvelle version dans l'interface (désactivable) ; versions de sécurité sans attendre une version fonctionnelle ; migrations automatiques avec sauvegarde préalable ; image unique, mise à jour en une commande.

**Ce qui manque.** La **gravité** dans la notification (une version de sécurité n'est pas une version fonctionnelle) ; une **politique de support** (quelles versions reçoivent des correctifs) ; une option de **mise à jour automatique des correctifs**.

**Mitigations complémentaires.** M-11 : flux d'avis de sécurité lu par la vérification de version (même appel sortant, aucune télémétrie supplémentaire) ; bandeau persistant pour l'administrateur quand la version installée a un avis critique ; **option** (désactivée par défaut, proposée dans l'assistant) d'application automatique des versions correctives ; politique de support publiée (dernière version mineure de la version majeure courante et de la précédente) ; option d'instance « suspendre l'automatisation de la publication tant qu'un avis critique n'est pas corrigé », proposée mais **jamais imposée** à distance.

**Signaux précoces.** Proportion d'instances signalant une version ancienne, si l'administrateur a accepté la vérification de version (le projet ne voit que des requêtes anonymes) ; signalements d'exploitation.

**Plan de repli.** Communication publique coordonnée (avis de sécurité, canaux du projet) ; documentation de révocation des jetons côté CMS et réseaux.

**Lot / responsable.** 1 / responsable sécurité.

---

### 4.10 R-T18 — Connecteurs WordPress et Ghost : idempotence, rapprochement, diversité des installations

| | P | I | C |
|---|---|---|---|
| Brut | 4 | 4 | **16** |
| Résiduel | 3 | 4 | **12** |

**Description.** Au lot 1, le site principal est un CMS externe (D13). La machine à états de publication (ADR-08) suppose de pouvoir **retrouver** une publication en cas de résultat inconnu ; les deux CMS n'offrent probablement pas de recherche par marqueur (§3.5). De plus, les installations WordPress sont très hétérogènes : extensions de sécurité qui bloquent l'API REST, extensions SEO multiples, hébergeurs qui filtrent les en-têtes d'authentification, versions anciennes. Conséquences : doublons d'articles sur le site principal après une coupure, ou publications bloquées en « à vérifier » ; échecs de connexion difficiles à diagnostiquer pour un utilisateur non expert, dès la première minute du parcours.

**Déjà décidé.** Contrat de connecteur avec « Vérifier l'existence » ; état « à vérifier » tranché par un humain ; diagnostic dédié pour les extensions de sécurité ; détection de Yoast et Rank Math.

**Ce qui manque.** Une **vérification** que ces hypothèses tiennent, avant de construire la machine à états autour.

**Mitigations complémentaires.** **M-10 / DR9 : preuve de concept S7** au début du lot 1 : rapprochement réel sur WordPress (avec et sans métadonnée déclarée) et sur Ghost (étiquette interne, autres options) ; matrice de compatibilité (versions, hébergeurs mutualisés courants, extensions de sécurité et de SEO les plus répandues) ; décision sur une éventuelle **extension WordPress compagnon** (facultative, qui expose la recherche par marqueur). Le rapprochement heuristique (titre, date, auteur, fenêtre de temps) est accepté comme repli, avec passage en « à vérifier » en cas d'ambiguïté.

**Signaux précoces.** Doublons constatés pendant S7 ; plus de 20 % d'échecs de connexion WordPress dans les tests d'utilisabilité.

**Plan de repli.** Publication en **brouillon** côté CMS par défaut (F-PUB-07) : un doublon en brouillon est inoffensif ; l'utilisateur publie depuis son CMS.

**Lot / responsable.** 1 / responsable connecteurs.

---

### 4.11 R-S02 — Fuite de données entre espaces

| | P | I | C |
|---|---|---|---|
| Brut | 3 | 5 | **15** |
| Résiduel | 2 | 5 | **10** |

**Description.** Un utilisateur voit des données d'un autre espace (articles, sources, secrets masqués, journaux) : requête sans filtre, tâche de fond exécutée sans contexte de tenance, recherche plein texte ou vectorielle qui ignore l'espace, fichier dont le chemin est devinable.

**Déjà décidé.** Contexte de tenance obligatoire ; sécurité au niveau des lignes (RLS) PostgreSQL positionnée par `SET LOCAL` ; tests d'isolation générés sur chaque point d'API ; chemins de fichiers préfixés et non devinables.

**Ce qui manque.** Les pièges connus de la RLS, qui la rendent **inopérante sans erreur visible** :
- le **propriétaire** des tables et les super-utilisateurs ne sont pas soumis à la RLS sauf configuration explicite ; si l'application se connecte avec le rôle qui a créé le schéma (cas le plus simple, donc le plus probable), la seconde barrière n'existe pas ;
- `SET LOCAL` n'a d'effet que dans une transaction ; une lecture hors transaction ou une connexion réutilisée par la file de tâches peut s'exécuter sans contexte ;
- les index vectoriels et plein texte doivent combiner le filtre d'espace et la recherche, sous peine de résultats incomplets ou de filtres appliqués après coup.

**Mitigations complémentaires.** M-12 : rôle applicatif **distinct** du propriétaire du schéma, RLS **forcée** sur les tables métier, migrations exécutées avec un rôle séparé ; test d'intégration qui vérifie qu'une requête **sans contexte renvoie zéro ligne** ; tests d'isolation étendus aux tâches de fond et à la recherche ; vérification dans S1 du coût réel de la RLS.

**Signaux précoces.** Un test d'isolation désactivé ou ignoré ; une requête d'administration « temporaire » sans contexte.

**Plan de repli.** Correctif de sécurité immédiat, notification des administrateurs, analyse des journaux d'accès.

**Lot / responsable.** 1 / responsable sécurité.

---

### 4.12 R-S03 — Compromission de l'instance et vol des jetons de publication

| | P | I | C |
|---|---|---|---|
| Brut | 2 | 5 | **10** |
| Résiduel | 2 | 5 | **10** |

**Description.** Un attaquant obtient l'exécution de code dans le processus API (faille d'une dépendance, du code du projet, d'un module intégré) ou un accès au serveur. Il lit la clé maîtresse et déchiffre tous les secrets : mots de passe d'application WordPress (droits complets de l'utilisateur WordPress), clés d'intégration Ghost, jetons des réseaux, clés des fournisseurs IA (usage frauduleux facturé à l'utilisateur). Le chiffrement par enveloppe ne protège ici rien (§3.6) : la cotation résiduelle est égale à la brute.

**Déjà décidé.** Chiffrement par enveloppe (protège les sauvegardes) ; secrets en écriture seule ; secrets jamais journalisés ; conteneur non-root à système de fichiers en lecture seule ; ré-authentification pour saisir un secret.

**Ce qui manque.** La **réduction des droits** des secrets eux-mêmes, et la **séparation** entre le processus le plus exposé (API, ouvert sur Internet) et celui qui a besoin des secrets (worker de publication).

**Mitigations complémentaires.** M-06 :
- **Moindre privilège côté canal** : guide et assistant recommandant un **utilisateur WordPress dédié** de rôle « Auteur » ou « Éditeur » (jamais administrateur) ; vérification du rôle à la connexion, avec avertissement si le compte est administrateur ; équivalent pour Ghost selon les possibilités de la plateforme.
- **DR6 — Secrets déchiffrables par le worker seul** : l'API **chiffre** les secrets saisis avec une clé publique ; seul le worker détient la clé privée et peut les déchiffrer. Une compromission du processus API ne donne plus accès aux secrets. Compatible avec ADR-11 (l'enveloppe reste) ; à évaluer dans S6 (impact sur le profil solo, où API et worker tournent sur la même machine mais dans des conteneurs séparés).
- **Plafonds de dépense** recommandés côté fournisseur IA (la plupart des fournisseurs permettent de plafonner une clé).

**Signaux précoces.** Avis de sécurité sur une dépendance de la couche API ; consommation IA anormale (R-O02).

**Plan de repli.** Procédure documentée de **révocation de tous les secrets** d'une instance (liste des secrets par canal, liens vers les pages de révocation des plateformes).

**Lot / responsable.** 1 / responsable sécurité.

---

### 4.13 R-T17 — Dérive et dépréciation des modèles IA

| | P | I | C |
|---|---|---|---|
| Brut | 5 | 3 | **15** |
| Résiduel | 4 | 3 | **12** |

**Description.** Les fournisseurs retirent ou modifient leurs modèles plusieurs fois par an, souvent sans changement de nom visible côté API. Les prompts, la conversion du Markdown balisé, les taux de sorties valides et les seuils des contrôles IA ont été calibrés sur des modèles qui changent. Le tableau des prix, tenu à la main, devient faux : les budgets à réservation se trompent (R-O02). Les dégradations sont **silencieuses** : le produit continue de fonctionner, moins bien.

**Déjà décidé.** Modèle de capacités ; validation des sorties structurées avec réparation bornée ; fournisseur factice et enregistrements pour les tests ; tableau des capacités et prix en données versionnées ; non-régression des contrôles sur jeu d'évaluation (lot 2).

**Ce qui manque.** Une **surveillance en production** de la qualité par profil de modèle, et une notion de **profil testé** par le projet.

**Mitigations complémentaires.** M-18 : taux de sorties invalides et de réparations suivi **par profil** dans le tableau de santé, avec alerte au-delà d'un seuil ; étiquette « profil testé par le projet » pour les modèles passés par la suite d'évaluation, les autres étant utilisables mais signalés ; mise à jour du tableau des prix livrée avec chaque version, et coût réel toujours lu dans la réponse du fournisseur quand elle le donne.

**Signaux précoces.** Hausse du taux de réparation sur un profil ; écart entre coût estimé et coût réel supérieur à 30 %.

**Plan de repli.** Basculement sur le profil de repli (F-IA-03) déjà prévu.

**Lot / responsable.** 1 / responsable qualité IA.

---

### 4.14 R-J05 — Obligations de transparence du règlement européen sur l'IA

| | P | I | C |
|---|---|---|---|
| Brut | 4 | 3 | **12** |
| Résiduel | 3 | 3 | **9** |

**Description.** Le règlement sur l'IA (art. 50) impose, depuis août 2026 : aux **fournisseurs** de systèmes générant du texte ou des images, un marquage **lisible par machine** et détectable des contenus générés ; aux **déployeurs** publiant des textes d'intérêt public générés par IA, une information du public, **sauf** relecture humaine et responsabilité éditoriale. La plateforme est probablement un « système d'IA » au sens du règlement et le projet, son fournisseur ; l'exemption des logiciels libres ne couvre pas l'art. 50 (§3.7, à confirmer). Des propositions de simplification et de report ont été discutées au niveau européen fin 2025 ; leur issue est à vérifier au moment de la revue juridique.

**Déjà décidé.** Mention IA non désactivable pour les contenus majoritairement générés (D8), insérée par le moteur de rendu ; métadonnées IPTC « source numérique : IA » et manifestes C2PA pour les images (à confirmer au lot 2) ; étiquetage natif des plateformes sociales ; validation humaine qui, si elle est réelle, peut exonérer le déployeur de l'obligation d'information pour les textes.

**Ce qui manque.** Un **marquage lisible par machine des textes** (la mention visible n'est pas lisible par machine au sens du règlement), et une lecture juridique de la qualité de fournisseur.

**Mitigations complémentaires.** M-16 : marqueur structuré dans le HTML publié (métadonnée dédiée et données structurées indiquant la part d'IA), dans les flux RSS sortants et dans l'export ; suivi des codes de pratique européens sur le marquage ; question inscrite à la revue juridique (M-15). Note : l'exonération du déployeur par la relecture humaine renforce l'importance de R-O10 ; une validation superficielle la fragilise.

**Signaux précoces.** Publication des codes de pratique ou de lignes directrices de la Commission ; premières décisions d'autorités nationales.

**Plan de repli.** Mise à jour du moteur de rendu (point central : un changement, tous les canaux).

**Lot / responsable.** 1 (textes), 2 (images) / mainteneur principal et conseil juridique.

---

### 4.15 R-T06 et R-T14 — Complexité excessive et érosion de l'architecture

| | P | I | C |
|---|---|---|---|
| R-T06 brut | 4 | 4 | **16** |
| R-T06 résiduel | 3 | 4 | **12** |
| R-T14 brut | 4 | 3 | **12** |
| R-T14 résiduel | 3 | 3 | **9** |

**Description.** L'architecture hexagonale, les ports stricts, les modules à dépendances contrôlées et les contrats versionnés sont la condition de presque toutes les sorties prévues (changer de file, de moteur de recherche, de cadre Web, d'éditeur). Ils ont un coût quotidien : couches d'adaptation, tests d'architecture, discipline. Sous pression (R-O08), la discipline cède : un import direct « pour aller vite », un appel SQL hors de l'adaptateur, `Depends` de FastAPI dans un service métier. Chaque écart est bénin ; leur somme rend les plans de sortie fictifs et multiplie par deux ou trois tous les coûts de changement estimés par la revue.

**Déjà décidé.** `import-linter` en intégration continue ; domaine indépendant de FastAPI (condition de DT14) ; schémas JSON publiés pour les contrats d'extension.

**Ce qui manque.** Le contraire du risque : **trop** d'abstraction trop tôt. Onze modules dès le lot 1, pour une ou deux personnes, c'est beaucoup de frontières à maintenir.

**Mitigations complémentaires.** Les contrats d'`import-linter` sont **bloquants** dès le premier commit (pas d'exceptions accumulées) ; regroupement possible de modules du lot 1 dans un nombre réduit de paquets tant que les frontières **logiques** sont tenues par les contrats d'import ; revue d'architecture à chaque fin de lot, avec la liste des exceptions accordées.

**Signaux précoces.** Exceptions `import-linter` en hausse ; ports à une seule implémentation dont l'interface change à chaque fonction.

**Plan de repli.** Simplifier les ports dont la sortie n'est plus envisagée, en le documentant (une sortie abandonnée doit être une décision, pas un oubli).

**Lot / responsable.** Tous / mainteneur principal.

---

### 4.16 R-P06 et R-P07 — Valeur du premier lot et érosion de l'audience des sites

| | P | I | C |
|---|---|---|---|
| R-P06 brut | 4 | 4 | **16** |
| R-P06 résiduel | 3 | 4 | **12** |
| R-P07 brut | 4 | 3 | **12** |
| R-P07 résiduel | 4 | 3 | **12** |

**Description.**
- **R-P06** : au lot 1, l'utilisateur obtient une veille, des brouillons sourcés et une publication vers son CMS, sans images (lot 2), sans réseaux (lot 3), sans automatisation au-delà du niveau 2. Face à un flux de travail improvisé (lecteur RSS + assistant conversationnel + copier-coller), la différence tient à la **traçabilité** et aux **garde-fous**, des qualités que l'utilisateur apprécie après un incident, rarement avant. Le risque est une adoption faible, donc pas de retours, pas de contributeurs, pas de jeu d'évaluation.
- **R-P07** : le choix du site comme pivot (D12) suppose que les sites reçoivent du trafic. Les moteurs de recherche affichent de plus en plus des réponses générées qui réduisent les clics vers les sites, en particulier pour l'actualité et les synthèses, exactement le type de contenus que produit la plateforme. Ce risque est **externe** et la mitigation est faible : la cotation résiduelle reste égale à la brute.

**Déjà décidé.** Positionnement qualité et curation (H10) ; SEO de base au lot 1 ; site pivot et audience possédée (RSS sortant au lot 2) ; test d'utilisabilité en fin de lot 1 (TECH_CHOICES §22.5).

**Mitigations complémentaires.** M-19 : définir dans `ROADMAP.md` un **critère d'adoption** de fin de lot 1 (par exemple, nombre d'utilisateurs réguliers externes au projet) en plus du test d'utilisabilité ; mettre en avant dès le lot 1 l'**apport propre** de l'utilisateur (angle, commentaire) dans le brief, qui est aussi ce qui distingue ses contenus des réponses générées des moteurs ; prévoir au lot 2 la **lettre d'information** (RSS vers courriel via le CMS) comme canal d'audience possédée, à évaluer.

**Signaux précoces.** Moins de 5 utilisateurs réguliers externes six mois après la préversion ; trafic des sites des premiers utilisateurs en baisse.

**Plan de repli.** Recentrer le produit sur la **veille** (lot 1 sans publication) si c'est la partie utilisée, et considérer la publication comme secondaire.

**Lot / responsable.** 1 et 2 / mainteneur principal.

---

### 4.17 R-T04 — Injection de prompt via les contenus collectés

| | P | I | C |
|---|---|---|---|
| Brut | 3 | 4 | **12** |
| Résiduel | 3 | 3 | **9** |

**Description.** Un contenu collecté contient des instructions destinées au modèle. L'architecture garantit qu'une injection réussie ne peut **pas publier** ni appeler d'outil à effet externe (P1, agents sans effet externe, garde-fous déterministes). Elle ne garantit pas qu'elle ne peut pas **modifier le contenu** du brouillon : insérer un lien vers un site tiers (référencement abusif, hameçonnage), ajouter une affirmation favorable ou défavorable à une entreprise ou une personne, orienter la conclusion. Si le brouillon est validé sans relecture attentive (R-O10), l'injection est publiée sous le nom de l'utilisateur.

**Déjà décidé.** Séparation instructions / données ; assainissement (texte invisible, Unicode) ; détection des motifs d'instruction avec indicateur dans la veille ; agents sans effet externe ; sorties jamais exécutées.

**Ce qui manque.** Un contrôle déterministe sur les **liens** et les **entités** introduits par le modèle.

**Mitigations complémentaires.** **M-05 / DR7** : garde-fou « liens » bloquant dès le lot 1 : tout lien présent dans un texte généré doit pointer vers une source de l'article ou vers une liste autorisée de la marque ; tout lien humain est accepté (origine `humain`). Garde-fou « personnes et organisations » : toute entité nommée absente de toutes les sources est signalée (heuristique au lot 1, reconnaissance d'entités au lot 2).

**Signaux précoces.** Indicateurs d'injection sur des sources jusqu'ici fiables ; liens externes inconnus dans les brouillons.

**Plan de repli.** Mise en quarantaine d'une source (exclusion des briefs) en un clic depuis l'indicateur.

**Lot / responsable.** 1 / responsable sécurité et responsable qualité IA.

---

### 4.18 R-O04 et R-O07 — Exploitation par un non-expert : installation, sauvegarde, perte de données

| | P | I | C |
|---|---|---|---|
| R-O04 brut | 4 | 4 | **16** |
| R-O04 résiduel | 3 | 4 | **12** |
| R-O07 brut | 3 | 5 | **15** |
| R-O07 résiduel | 2 | 5 | **10** |

**Description.** L'installateur type n'est pas administrateur système (CO-01). Les difficultés réelles ne sont pas la commande d'installation mais ce qui l'entoure : nom de domaine et DNS, ports, pare-feu, certificat qui ne s'obtient pas, courriel sortant non délivré (réinitialisation de mot de passe impossible), disque plein, montée de version majeure de PostgreSQL (R-T16), sauvegardes faites **sur le même disque** que la base, jamais testées, clé maîtresse non sauvegardée (R-O13). La perte de données (R-O07) survient le jour où le VPS disparaît.

**Déjà décidé.** Image unique et Compose ; Caddy avec TLS automatique ; assistant Web ; sauvegarde planifiée, destination distante optionnelle, test de restauration guidé ; état de la dernière sauvegarde dans le tableau de santé ; rappel de la clé maîtresse ; export d'espace ; preuve de concept S6 (installation sur VPS vierge en moins de 15 minutes).

**Ce qui manque.** Le caractère **facultatif** de la destination distante : une sauvegarde locale ne protège pas de la perte du serveur.

**Mitigations complémentaires.** Alerte persistante tant qu'**aucune destination distante** n'est configurée ou qu'**aucun test de restauration** n'a réussi depuis 90 jours ; **diagnostic d'installation** intégré (DNS, ports, certificat, envoi d'un courriel de test, espace disque) affiché avant l'assistant ; documentation de **mise à jour** et de **restauration** testée à chaque version dans l'intégration continue.

**Signaux précoces.** Questions de support majoritairement liées à l'installation ; instances sans destination distante (visible seulement localement).

**Plan de repli.** Liste de prestataires ou bénévoles d'installation référencés par la communauté ; instructions spécifiques pour quelques fournisseurs de VPS courants.

**Lot / responsable.** 1 / mainteneur principal.

---
## 5. Registre complet

Notation : **P×I=C**. « Brut » et « Résiduel » au sens du §1.2. Les risques en **gras** ont une fiche au §4. Les références renvoient aux documents validés : **FA** (analyse fonctionnelle), **AR** (architecture), **TC** (choix technologiques), **REV** (revue critique). « M-xx » renvoie aux mitigations complémentaires du §7.

### 5.1 Risques techniques (R-T)

| ID | Risque | Brut | Mitigations principales | Résiduel | Lot | Signal précoce |
|---|---|---|---|---|---|---|
| R-T01 | Changement ou fermeture d'une API sociale cassant un connecteur | 5×3=15 | Connecteurs isolés et désactivables, contrats versionnés, « préparer et copier », site pivot (AR §9, §16.4) | 4×2=8 | 3 | Erreurs d'un connecteur en hausse ; annonce de changement de conditions d'accès |
| **R-T02** | Hallucinations publiées | 5×5=25 | Références structurées, citations exactes, C1 au lot 1, C2 au lot 2, validation (TC §23) ; M-03, M-04, M-05 | 4×4=16 | 1-2 | §4.2 |
| R-T03 | Extraction Web fragile (structure changeante, protections anti-robots) | 4×2=8 | Priorité au RSS, `trafilatura` + repli, santé des sources (TC §14) | 3×2=6 | 1 | Chute de la longueur extraite sur une source |
| **R-T04** | Injection de prompt via les contenus collectés | 3×4=12 | Séparation instructions/données, assainissement, aucun outil à effet externe (AR §10.5) ; M-05 | 3×3=9 | 1 | §4.17 |
| R-T05 | Hétérogénéité des fournisseurs IA (formats, qualité) | 4×3=12 | Capacités, sortie validée, Markdown balisé restreint, S4 (TC §11) | 3×2=6 | 1 | Taux de réparation > 5 % sur un profil supporté |
| **R-T06** | Complexité technique excessive (trop de modules, trop tôt) | 4×4=16 | Lots, cœur réduit, monolithe modulaire (AR ADR-01) ; M-01 | 3×4=12 | Tous | §4.15 |
| R-T08 | Publication en double ou perdue après une panne | 3×4=12 | Machine à états, clés d'idempotence, rapprochement, jamais de relance aveugle (AR §12.4) ; dépend de R-T18 | 2×3=6 | 1 | Publication « à vérifier » non résolue > 24 h |
| R-T09 | Coût matériel des modèles locaux (GPU) | 2×2=4 | Modèles locaux optionnels, sur une autre machine (TC §3.2) | 2×2=4 | 1 | — (accepté) |
| **R-T10** | Garde-fou de similarité trop faible ou trop bruyant | 4×4=16 | Lexical + sémantique, calibration S5 (TC §13) ; M-09 | 3×4=12 | 1 | §4.8 |
| R-T11 | Format de document : divergence éditeur / rendu Python, part d'IA contestable | 3×4=12 | Format propre au projet, rendus figés dans les instantanés, règles d'origine testées, test de concordance, S3 (TC §10.3, REV §4) | 3×3=9 | 1 | Écarts au test de concordance ; part d'IA qui surprend en test utilisateur |
| R-T12 | File de tâches : double exécution à l'expiration d'un bail, tâches bloquées | 3×4=12 | Procrastinate, durée maximale par type, bail supérieur, idempotence des effets externes, S2 (TC §9.3) | 2×4=8 | 1 | Toute double exécution observée ; tâches « en cours » orphelines |
| R-T13 | Appel bloquant dans la boucle asynchrone de l'API, pièges de la session SQLAlchemy asynchrone | 3×3=9 | Workers synchrones, traitements lourds hors API (TC §5.2) ; détecteur de boucle bloquée | 2×3=6 | 1 | Latence API (95ᵉ centile) qui monte pendant les collectes |
| **R-T14** | Érosion des frontières hexagonales sous la pression des délais | 4×3=12 | `import-linter` bloquant, domaine indépendant de FastAPI (TC §5.4) | 3×3=9 | Tous | §4.15 |
| R-T15 | Budget mémoire du profil solo dépassé (index vectoriel, modèle d'embeddings, extraction) | 3×3=9 | Partitionnement, embeddings sélectifs, quantification, S1 (TC §8.4) | 2×3=6 | 1 | Index vectoriel > 35 % de la mémoire de la base ; arrêts pour manque de mémoire |
| R-T16 | Montée de version majeure de PostgreSQL ratée par un non-expert | 4×3=12 | Version fixée par version majeure du produit, commande assistée testée en CI (TC §8.7) | 3×3=9 | 2 | Échecs signalés lors de la première montée majeure |
| **R-T17** | Dérive, dépréciation des modèles et tableau des prix obsolète | 5×3=15 | Capacités, validation, données versionnées, non-régression (TC §11) ; M-18 | 4×3=12 | 1 | §4.13 |
| **R-T18** | Connecteurs WordPress et Ghost : rapprochement non vérifié, installations hétérogènes | 4×4=16 | Contrat avec « Vérifier l'existence », état « à vérifier », diagnostics (AR §16.3) ; M-10 (S7) | 3×4=12 | 1 | §4.10 |
| R-T19 | Contrôle factuel C1 : faux sentiment de sécurité (ne voit que les chiffres) et faux positifs (chiffres dérivés) | 4×3=12 | Vocabulaire « non étayé » (CF2), C2 au lot 2, évaluation (TC §23) ; M-03, M-05 | 3×3=9 | 1 | Taux d'alertes C1 ignorées > 50 % |
| R-T20 | Site généré incohérent (construction incrémentale qui oublie des pages) | 3×3=9 | Reconstruction complète de référence, comparaison régulière, décision au lot 2 (TC §15.3, REV §2) | 2×3=6 | 2 | Écart incrémental / complet |
| R-T21 | Migration de schéma automatique qui échoue au démarrage (instance indisponible, données incohérentes) | 3×4=12 | Sauvegarde automatique avant migration, migrations compatibles avec la version précédente (AR §20.4) ; M-17 | 2×4=8 | 1 | Échec de migration en CI sur une copie de base réaliste |

R-T07 (fuite de secrets) est reclassé en **R-S03**.

### 5.2 Risques de sécurité (R-S)

| ID | Risque | Brut | Mitigations principales | Résiduel | Lot | Signal précoce |
|---|---|---|---|---|---|---|
| **R-S01** | Faille dans l'authentification propre | 3×5=15 | Bibliothèques éprouvées, ASVS niveau 2, identités externes prévues, ré-authentification, audit recherché (TC §18) ; M-07 | 3×5=15 (2×5=10 avec audit) | 1 | §4.7 |
| **R-S02** | Fuite de données entre espaces | 3×5=15 | Contexte de tenance, RLS, tests d'isolation (AR §8.1) ; M-12 | 2×5=10 | 1 | §4.11 |
| **R-S03** | Compromission de l'instance et vol des jetons de publication (ex R-T07) | 2×5=10 | Enveloppe, écriture seule, non-root, journaux filtrés (AR §19.4) ; M-06 | 2×5=10 | 1 | §4.12 |
| R-S04 | Chaîne d'approvisionnement : paquet PyPI ou npm compromis | 3×5=15 | Verrouillage avec empreintes, quarantaine des nouvelles versions, SBOM, images signées, pas de LiteLLM embarqué (TC §21) | 2×5=10 | 1 | Avis de sécurité sur une dépendance directe |
| R-S05 | Contournement de la protection SSRF (rebinding DNS, redirections, IPv6, liste d'autorisation des fournisseurs locaux) | 3×4=12 | Client HTTP commun, contrôle après chaque résolution et redirection (AR §13.2, TC §14) ; tests dédiés | 2×4=8 | 1 | Requête sortante vers une plage interne dans les journaux |
| R-S06 | Contenu actif (XSS) via collecte, collage dans l'éditeur ou sortie IA | 3×4=12 | Assainissement `nh3`, document structuré, politique de sécurité de contenu stricte (AR §19.1) | 2×3=6 | 1 | Violation de la politique de sécurité de contenu signalée |
| R-S07 | Module intégré (chargé dans le processus) disposant de tous les droits avant le lot 4 | 2×4=8 | Modules officiels seulement, revue de code, permissions déclarées ; hors processus au lot 4 (AR §9.6) | 2×4=8 | 1-3 | Demande d'installation de modules tiers avant le lot 4 |
| R-S08 | Abus des points d'accès publics (médias signés, formulaire de contact, rappels OAuth) | 3×3=9 | URL signées à durée limitée, limitation de débit, défi anti-robot (AR §16.4, §19.1) | 2×3=6 | 2-3 | Volume anormal sur ces points d'accès |
| **R-S09** | Instances non mises à jour, porteuses de jetons | 5×4=20 | Notification de version, correctifs séparés (AR §20.4) ; M-11 | 4×3=12 | 1 | §4.9 |

### 5.3 Risques juridiques (R-J)

| ID | Risque | Brut | Mitigations principales | Résiduel | Lot | Signal précoce |
|---|---|---|---|---|---|---|
| **R-J01** | Contrefaçon : article trop proche d'une source, y compris par traduction | 4×4=16 | Similarité bloquante, multi-sources par défaut, archives privées (AR §14.4) ; M-09 | 3×4=12 | 1 | §4.8 |
| R-J02 | Atteinte au droit voisin des éditeurs de presse | 3×3=9 | Blocs Sources limités aux titres, éditeurs, dates et liens ; pas d'extraits longs (AR §14.5) | 2×3=6 | 1 | Citation longue d'une publication de presse dans un article |
| R-J03 | Collecte non autorisée (réserve de fouille, conditions d'utilisation) | 3×3=9 | Respect automatique de robots.txt et TDMRep, journal de conformité, autorisation consignée (AR §13.1) ; M-08 | 2×3=6 | 1 | Demande d'un mode « ignorer les réserves » |
| **R-J04** | Diffamation ou fausse information publiée | 4×5=20 | Validation, contrôles factuels, retrait en une action, instantanés probants ; M-03 à M-05 | 3×5=15 | 1 | §4.5 |
| **R-J05** | Obligations de transparence du règlement sur l'IA (art. 50), y compris en tant que fournisseur | 4×3=12 | Mention IA non désactivable, IPTC et C2PA, étiquetage natif (D8, AR §14.5, §17) ; M-16, M-15 | 3×3=9 | 1-2 | §4.14 |
| R-J06 | RGPD : données personnelles des articles collectés envoyées à des fournisseurs hors UE, archives, droits des personnes | 4×3=12 | Localisation déclarée des fournisseurs, mode « local uniquement », rétention, prompts non conservés (AR §10.6, §8.6) ; M-15 | 3×3=9 | 1 | Demande d'effacement visant une archive de source |
| R-J07 | Responsabilité du projet pour un usage abusif par des tiers | 2×3=6 | Licence sans garantie, valeurs par défaut prudentes, documentation d'usage responsable | 2×2=4 | 1 | — (accepté) |
| R-J08 | Obligations d'hébergeur (DSA, sous-traitance RGPD) en cas d'offre hébergée | 2×5=10 | Offre hébergée hors projet (D1) | 1×5=5 | — | Décision d'ouvrir une offre hébergée |
| **R-J09** | Assèchement des sources par les réserves de fouille ; doute sur la couverture de la génération par l'exception | 5×4=20 | Respect des réserves (choix assumé) ; M-08, M-15 | 4×4=16 | 1 | §4.4 |
| R-J10 | Conservation des archives de sources au-delà de ce que permet l'exception de fouille | 3×3=9 | Archives internes, jamais publiées, rétention par politique d'espace (AR §15.1) ; M-20, M-15 | 3×2=6 | 1 | Avis de la revue juridique |
| R-J11 | Règlement européen sur la cyber-résilience : le projet requalifié en « fabricant » s'il est monétisé | 3×3=9 | Projet non commercial ; offre hébergée séparée (D1) ; processus de vulnérabilités déjà prévu (AR §19.5) ; M-15 | 2×3=6 | Tous | Toute forme de monétisation (support payant, offre hébergée, double licence) |
| R-J12 | Licence AGPL : frontière « hors processus » juridiquement incertaine ; contributions sans cadre (DCO) ; rejet par certaines organisations | 3×3=9 | AGPL choisie (D2) ; deux modes d'extension (AR §9.6) ; M-13 (DCO) | 2×3=6 | 1 et 4 | Contribution importante sans certificat d'origine ; question d'un intégrateur sur la licence |
| R-J13 | Conditions des fournisseurs IA : usage des données envoyées (y compris offres gratuites), interdictions d'usage | 3×3=9 | Lien vers les conditions et localisation affichés au choix du profil (AR §10.6) | 2×3=6 | 1 | Changement de conditions d'un fournisseur par défaut |
| R-J14 | Images : personnes réelles, marques, licences et attributions des images importées | 3×3=9 | Non photoréaliste par défaut, refus des personnes réelles, provenance et attribution (D9, AR §17) | 2×3=6 | 2 | Image retirée à la demande d'un tiers |

### 5.4 Risques opérationnels (R-O)

| ID | Risque | Brut | Mitigations principales | Résiduel | Lot | Signal précoce |
|---|---|---|---|---|---|---|
| R-O01 | Suspension des comptes sociaux de l'utilisateur (automatisation, spam) | 3×4=12 | Plafonds par canal, étiquetage natif, pas de multi-comptes coordonnés, « préparer et copier » (AR §16.4) | 2×4=8 | 3 | Avertissement d'une plateforme sur un compte |
| R-O02 | Dérive des coûts IA en mode automatique | 3×3=9 | Budgets à réservation, plafonds, blocage et notification, désactivation sur anomalie (AR §10.7, §11.6) | 2×2=4 | 1 | Coût horaire anormal |
| R-O03 | Automatisation qui publie un contenu inapproprié hors présence humaine | 2×5=10 | PDP, R2 par construction, délai de grâce, revérification, plafonds, arrêt d'urgence, simulation (AR §11) | 1×5=5 | 3 | Publication automatique retirée par l'utilisateur |
| **R-O04** | Installation et exploitation trop difficiles pour la cible | 4×4=16 | Image unique, Compose, Caddy, assistant, S6 (TC §19) ; diagnostic d'installation (§4.18) | 3×4=12 | 1 | §4.18 |
| **R-O05** | Épuisement ou départ du mainteneur ; abandon | 4×5=20 | Cœur réduit, contrats délégables, un seul environnement d'exécution ; M-13 | 3×5=15 | Tous | §4.6 |
| R-O06 | Friction d'accès aux API sociales (applications développeur, revues) | 5×3=15 | Canaux ouverts d'abord, guides, « préparer et copier » (FA H1) | 4×3=12 | 3 | Temps de mise en service d'un canal Meta en test utilisateur |
| **R-O07** | Perte de données (sauvegarde absente, locale ou non testée) | 3×5=15 | Sauvegarde intégrée, test de restauration guidé, export (AR §20.5) ; alerte sans destination distante (§4.18) | 2×5=10 | 1 | §4.18 |
| **R-O08** | Périmètre disproportionné par rapport à la capacité | 5×5=25 | Lots, décisions de simplification (TC-06, TC-09, TC-12) ; M-01, M-02 | 4×5=20 | Tous | §4.1 |
| R-O09 | Audit de sécurité externe non financé | 4×4=16 | Exigence ferme de recherche (DT14) ; M-07 ; préversion tant que l'audit manque (DR2) | 4×4=16 | 1 | Aucun financement identifié à mi-lot 1 |
| **R-O10** | Fatigue de validation (biais d'automatisation) | 5×4=20 | Validation par défaut, passages surlignés ; M-03, M-04 | 4×4=16 | 1 | §4.3 |
| R-O11 | Évaluations continues infaisables (pas de données d'usage, coût des modèles payants en CI) | 4×3=12 | Jeux versionnés, fournisseur factice (TC §11, §21) ; M-14 | 3×3=9 | 2 | Jeu d'évaluation inférieur à 200 cas au début du lot 2 |
| R-O12 | Charge de support des installations auto-hébergées | 4×3=12 | Documentation, diagnostics, tableau de santé ; M-11 | 3×3=9 | 1 | Plus de la moitié du temps du mainteneur sur le support |
| R-O13 | Perte de la clé maîtresse (secrets illisibles après restauration) | 3×3=9 | Rappel dans l'assistant et le tableau de santé (AR §19.4) ; procédure de ressaisie des secrets | 2×3=6 | 1 | Restauration de test sans clé |
| R-O14 | Maintenance continue des connecteurs imposée par le rythme des tiers (CMS, réseaux, fournisseurs IA) | 5×3=15 | Connecteurs isolés, tests de conformité, désactivation individuelle (AR §9.7) ; délégation à des contributeurs (M-13) | 4×3=12 | 1-4 | Connecteur cassé plus de 30 jours |
| R-O15 | Documentation de conception non éprouvée et divergente du code | 3×3=9 | Preuves de concept S1 à S7 en tête du lot 1 ; ADR en fichiers séparés au passage en dépôt (AR §25) | 2×3=6 | 1 | Une preuve de concept contredit un document sans que celui-ci soit mis à jour |

### 5.5 Risques produit et réputation (R-P)

| ID | Risque | Brut | Mitigations principales | Résiduel | Lot | Signal précoce |
|---|---|---|---|---|---|---|
| R-P01 | Produit perçu ou utilisé comme « usine à contenus » ou à désinformation | 3×5=15 | Positionnement curation, traçabilité visible, mention IA non désactivable, plafonds par défaut (FA H10, D8) | 2×5=10 | Tous | Article de presse ou fil de discussion associant le projet à du spam |
| R-P02 | Valeur faible des contenus produits (référencement, engagement) | 4×3=12 | Apport humain encouragé, multi-sources, SEO de base (FA §5.13) | 3×3=9 | 1-2 | Retours d'utilisateurs sur la qualité ; trafic des sites |
| R-P03 | Concurrence d'outils existants | 3×2=6 | Différenciation : libre, traçable, contrôlable, multi-fournisseurs | 3×2=6 | — | — (accepté) |
| R-P04 | Dépendance de l'audience aux réseaux sociaux | 3×4=12 | Site principal pivot, RSS sortant, audience possédée (D12) | 2×3=6 | 2-3 | — |
| R-P05 | Complexité perçue par l'utilisateur solo (espace, marque, site) | 4×3=12 | Règles UXM1 à UXM8, profil d'interface calculé (TC §22) | 2×3=6 | 1 | Test d'utilisabilité de fin de lot 1 |
| **R-P06** | Valeur du lot 1 insuffisante pour retenir les premiers utilisateurs | 4×4=16 | Test d'utilisabilité ; M-01, M-19 | 3×4=12 | 1 | §4.16 |
| **R-P07** | Baisse du trafic vers les sites (réponses générées des moteurs, « zéro clic ») | 4×3=12 | Site pivot, audience possédée ; M-19 | 4×3=12 | 1-2 | §4.16 |
| R-P08 | Promesse d'indépendance perçue comme trompeuse (en pratique : API payante ou serveur GPU) | 3×3=9 | Parcours local complet garanti (FA H7) ; communication honnête : « aucun fournisseur **imposé** », pas « aucun coût » | 2×2=4 | 1 | Critiques publiques sur ce point |

---

## 6. Concentration des mitigations : points de défaillance uniques

Une mitigation qui protège plusieurs risques est efficace tant qu'elle tient, et dangereuse le jour où elle cède : toutes les cotations résiduelles qui en dépendent remontent ensemble. Le tableau ci-dessous identifie ces points.

| Mitigation pivot | Risques qui en dépendent | Si elle cède | Protection proposée |
|---|---|---|---|
| **Validation humaine par défaut** | R-T02, R-T04, R-J01, R-J04, R-J05 (exonération du déployeur), R-O03, R-P01 | R-T02 et R-J04 reviennent à leur cotation brute (25 et 20) | M-03, M-04 (DR5) |
| **PDP et revérification de dernier moment** | R-O03, R-O01, R-O02, R-S01 (en partie), promesses R1 à R5 | Une seule erreur de règle autorise une publication ; l'architecture n'a pas de seconde barrière | Tests de propriétés exhaustifs (TC §21, déjà décidé) ; **aucune** exception au chemin unique, même pour l'administration ; revue de toute modification du PDP par une seconde personne dès qu'elle existe |
| **Ports internes stricts** | Tous les plans de sortie (TC §24) : R-T12, R-T15, R-T11, TC-02 | Coûts de changement × 2 à × 3 (REV, règle de lecture) | `import-linter` bloquant dès le premier commit (§4.15) |
| **Authentification** | R-S01, R-O03 (activation des niveaux 3-4), R-S03 | Un compte compromis contourne toutes les promesses de contrôle | M-07 (DR2, DR3) |
| **Preuves de concept S1 à S7** | Cotations résiduelles de R-T11, R-T12, R-T15, R-T18, R-T10, R-O04 | Les cotations résiduelles sont des paris | Les preuves de concept sont des **jalons bloquants** de la roadmap, avec le droit de contredire les documents (§8.1) |
| **Jeux d'évaluation** | R-T19, R-T17, entrée des agents (TC-09), seuils CF4 | Contrôles IA jamais promus en bloquants, agents jamais validés, dérives non détectées | M-14 |

**Le cas le plus inquiétant est le premier.** Les cinq autres points sont des mécanismes techniques que le projet maîtrise et peut tester. La validation humaine dépend du comportement d'utilisateurs que le projet ne voit pas.

---
## 7. Mitigations complémentaires proposées

Ces mitigations **s'ajoutent** aux décisions validées sans en contredire aucune. Celles qui modifient le périmètre d'un lot ou un choix d'architecture passent par une décision du §9. Coût : **faible** (quelques jours), **moyen** (une à trois semaines-développeur), **élevé** (au-delà).

| ID | Mitigation | Risques traités | Lot | Coût | Décision |
|---|---|---|---|---|---|
| **M-01** | **Lot 1 découpé en deux jalons.** **1a « noyau sourcé »** : tout ce qui coûte cher à ajouter plus tard (isolation durcie, PDP, file et idempotence, format de document et instantanés, audit chaîné, garde-fous déterministes, sauvegarde) et le parcours de valeur minimal (RSS, brouillon sourcé, **un** CMS en brouillon par défaut, interface FR avec clés de traduction en place). **1b « complétude du lot 1 »** : second CMS, interface EN, API publique v1 déclarée stable (l'API existe dès 1a mais sans garantie de compatibilité), score sémantique de veille et retour de tri, OPML, tableau de santé complet. Rien n'est retiré du lot 1 ; l'ordre change | R-O08, R-O05, R-P06, R-T06 | 1 | Nul (réordonnancement) | DR1 |
| **M-02** | **Hypothèse de capacité et critères d'arrêt** inscrits dans `ROADMAP.md` : personnes, temps hebdomadaire, durée visée de chaque jalon ; critères qui déclenchent une réduction de périmètre plutôt qu'un glissement (§8.5) | R-O08, R-O05 | Tous | Faible | Question Q-R1 |
| **M-03** | **Validation proportionnée au risque** : niveau de risque déterministe par article (personnes nommées, chiffres non étayés, source unique, similarité proche du seuil, sujet sensible déclaré) ; au-delà d'un seuil, chaque signalement est traité individuellement avant que la validation ne soit possible ; pas de validation groupée des brouillons IA à risque | R-O10, R-T02, R-J04, R-T04, R-J01 | 1 | Moyen | DR5 |
| **M-04** | **Mesure locale de la qualité de validation** : temps de relecture rapporté à la longueur, signalements ouverts, validations éclair ; visible par l'utilisateur seul ; inscrite dans l'instantané | R-O10, R-J04, R-J05 | 1 | Faible | DR5 |
| **M-05** | **Garde-fous « liens » et « personnes et organisations »** : lien généré autorisé seulement vers une source de l'article ou une liste de la marque (bloquant) ; entité nommée absente de toutes les sources signalée (heuristique au lot 1, reconnaissance d'entités au lot 2) | R-T04, R-T02, R-J04 | 1 (2 pour la reconnaissance d'entités) | Faible à moyen | DR7 |
| **M-06** | **Moindre privilège des secrets** : assistant qui recommande un compte CMS dédié non administrateur et avertit sinon ; plafonds de dépense côté fournisseur IA recommandés ; **secrets chiffrés par l'API avec une clé publique, déchiffrables par le worker seul** | R-S03, R-O02 | 1 | Moyen | DR6 |
| **M-07** | **Plan d'audit de sécurité** : recherche de financement dès le début du lot 1 ; auto-évaluation ASVS niveau 2 publiée à chaque version ; pas de version « stable » sans audit ; connexion OIDC avancée au lot 2 en option | R-S01, R-O09 | 1-2 | Faible (recherche) ; moyen (OIDC) | DR2, DR3 |
| **M-08** | **Sources : statut juridique visible** par source (texte intégral, résumé seulement, refusé, avec raison) ; brouillon signalé quand il ne repose que sur des résumés ; **saisie manuelle encadrée** (origine et droit d'usage déclarés, marqueur dans l'instantané) ; **catalogue de sources ouvertes** proposé à l'installation | R-J09, R-J03, R-J01, R-P06 | 1 | Faible à moyen | — |
| **M-09** | **Similarité renforcée** : mesure sémantique multilingue **bloquante** quand la langue de l'article diffère de celle de la source ; paires de traductions dans le corpus S5 ; mesure d'alignement structurel en alerte ; **bornes d'instance** sur les seuils (un espace peut durcir, pas assouplir au-delà) | R-J01, R-T10 | 1 | Faible | DR4 |
| **M-10** | **Preuve de concept S7 « connecteurs CMS »** : rapprochement réel sur WordPress et Ghost, matrice de compatibilité (versions, hébergeurs, extensions de sécurité et de SEO), décision sur une extension WordPress compagnon facultative, droits effectifs des identifiants | R-T18, R-T08, R-S03 | Début du lot 1 | Moyen | DR9 |
| **M-11** | **Mises à jour de sécurité** : gravité dans la notification de version (même appel sortant), bandeau persistant en cas d'avis critique, politique de support publiée, application automatique facultative des versions correctives, option locale de suspension de l'automatisation tant qu'un avis critique est ouvert | R-S09, R-O12 | 1 | Faible à moyen | — |
| **M-12** | **Durcissement de la RLS** : rôle applicatif distinct du propriétaire du schéma, RLS forcée, rôle de migration séparé, test « requête sans contexte = zéro ligne », tests d'isolation étendus aux tâches de fond et à la recherche | R-S02 | 1 | Faible | — |
| **M-13** | **Gouvernance et continuité** : contributions sous **DCO** ; comptes du projet (forge, registre, domaine, clés de signature) détenus par une organisation à deux administrateurs dès que possible ; recherche de financement ; politique de fin de vie publiée | R-O05, R-J12, R-O14 | Avant la première version publique | Faible | DR8 |
| **M-14** | **Évaluations à coût maîtrisé** : corpus de référence construit par le projet à partir de sources sous licence libre ; non-régression courante sur réponses enregistrées et modèles locaux ; exécutions sur modèles payants réservées aux versions candidates, avec plafond de dépense ; contributions volontaires de cas anonymisés depuis les instances | R-O11, R-T17, R-T19 | 1-2 | Moyen | — |
| **M-15** | **Revue juridique ciblée** avant la première version publique, sur la liste de questions du §8.3 | R-J01, R-J03, R-J05, R-J06, R-J09, R-J10, R-J11, R-J12 | Avant la première version publique | Élevé (financier) | — |
| **M-16** | **Marquage lisible par machine des textes générés** : métadonnée dédiée et données structurées dans le HTML publié, dans les flux sortants et dans l'export ; suivi des codes de pratique européens | R-J05 | 1 | Faible | — |
| **M-17** | **Migrations sûres** : essai sur une copie de base réaliste en CI, refus de démarrer avec un message clair si la migration échoue, procédure de retour arrière documentée (restauration de la sauvegarde préalable) | R-T21, R-O07 | 1 | Faible | — |
| **M-18** | **Surveillance des profils de modèles** : taux de sorties invalides et de réparations par profil dans le tableau de santé ; étiquette « profil testé par le projet » ; tableau des prix mis à jour à chaque version | R-T17, R-O02 | 1 | Faible | — |
| **M-19** | **Critère d'adoption et apport propre** : critère d'adoption de fin de lot 1 dans `ROADMAP.md` ; champ « angle et apport propre » mis en avant dans le brief ; lettre d'information comme canal d'audience possédée à évaluer au lot 2 | R-P06, R-P07, R-P02 | 1-2 | Faible | — |
| **M-20** | **Archive réduite** configurable : possibilité de ne conserver, après un délai, que l'empreinte, les métadonnées et les passages réellement cités, selon la conclusion de la revue juridique | R-J10, R-J06 | 1 (prévoir), activation selon revue | Faible | — |

---

## 8. Exigences transmises à `ROADMAP.md`

### 8.1 Preuves de concept : jalons bloquants

- **S1 à S6** (TC §25) et **S7** (M-10) ouvrent le lot 1, **avant** le code des fonctions qui en dépendent.
- Chaque preuve de concept a une **question écrite**, un **critère de réussite chiffré** et une **durée maximale** ; à l'échéance, elle conclut, même négativement.
- Une preuve de concept **a le droit de contredire** un document validé ; la contradiction est soumise à Joël et le document est mis à jour (R-O15).
- S1 vérifie aussi la RLS durcie (M-12) ; S2 vérifie le comportement de la file avec les connexions soumises à la RLS ; S6 évalue la séparation des secrets entre API et worker (DR6).

### 8.2 Critères d'entrée et de sortie des lots

| Jalon | Critère de sortie (proposé) |
|---|---|
| **Lot 1a** | S1 à S7 conclues ; tests d'isolation (API, tâches, recherche) verts ; liste ASVS niveau 2 du périmètre lot 1 couverte ; restauration de sauvegarde testée en CI ; tests de propriétés du PDP verts ; parcours « installation → premier brouillon sourcé → brouillon WordPress » en moins de 15 minutes par un utilisateur non expert |
| **Lot 1b** | Second CMS au même niveau de tests ; interface EN complète ; API v1 publiée avec sa spécification ; test d'utilisabilité à 5 utilisateurs (TC §22.5) ; critère d'adoption fixé (M-19) |
| **Première version publique** | Revue juridique faite (M-15) ; politique de divulgation des vulnérabilités publiée ; gouvernance minimale (M-13) ; **« préversion » tant que l'audit externe n'a pas eu lieu** (DR2) |
| **Entrée du lot 2** | Décision sur le générateur de site (TC-12) ; jeu d'évaluation de référence amorcé (M-14) ; bilan du risque R-O10 à partir des mesures locales de volontaires |
| **Entrée du lot 3** | Arrêt d'urgence, plafonds, journal, simulation, désactivation sur anomalie **livrés et testés avant** les niveaux 3 et 4 (FA §14) ; critère d'entrée des agents mesuré (TC §12.4) |

### 8.3 Revue juridique : questions à poser

| ID | Question | Risques |
|---|---|---|
| Q-J1 | L'exception de fouille de textes et de données (art. 4 de la directive 2019/790, transposée en droit belge) couvre-t-elle la **génération** d'un article à partir de contenus fouillés, ou seulement leur analyse ? | R-J09, R-J01 |
| Q-J2 | Combien de temps peut-on conserver une **archive de source** au titre de la preuve, au regard de l'exception de fouille et du RGPD ? | R-J10, R-J06 |
| Q-J3 | Le projet est-il **fournisseur** d'un système d'IA au sens de l'art. 50 du règlement sur l'IA ? Que vaut un marquage lisible par machine pour un **texte** ? Quel est le calendrier applicable après les propositions de simplification européennes ? | R-J05 |
| Q-J4 | À quelles conditions le projet resterait-il hors du champ du **règlement sur la cyber-résilience** (ou sous le régime de « gestionnaire de logiciels libres ») ? Quelles formes de financement le feraient basculer ? | R-J11 |
| Q-J5 | La séparation **hors processus** des modules tiers suffit-elle à les soustraire aux obligations de l'**AGPL** ? | R-J12 |
| Q-J6 | La **pseudonymisation** des entrées d'audit à la suppression d'un utilisateur (DA10) est-elle conforme au RGPD ? | R-J06 |
| Q-J7 | Un utilisateur indépendant (blog, newsletter) bénéficie-t-il de l'**exemption journalistique** du RGPD en droit belge pour les données personnelles présentes dans ses articles et archives ? | R-J06, R-J04 |
| Q-J8 | Quelle **information** le projet doit-il fournir aux utilisateurs sur leur responsabilité d'éditeur (diffamation, droit de réponse) pour limiter sa propre exposition ? | R-J04, R-J07 |

### 8.4 Sécurité

- Recherche de financement de l'audit **lancée au début du lot 1** ; point d'étape à mi-lot 1 (signal précoce de R-O09).
- Liste de contrôle ASVS niveau 2 versionnée dans le dépôt dès le premier commit du module Identité et accès.
- Politique de divulgation, adresse de contact sécurité et processus de version corrective prêts **avant** la première version publique.
- Audit externe du module Identité et accès et du chiffrement des secrets avant toute version « stable » (DR2).

### 8.5 Capacité et critères d'arrêt (à chiffrer avec Q-R1)

| Critère | Réaction proposée |
|---|---|
| Lot 1a dépassant de plus de 50 % sa durée visée | Réduire le lot 1b (reporter l'API stable et le second CMS) plutôt que de raccourcir les tests ou les garde-fous |
| Moins de 5 utilisateurs réguliers externes six mois après la préversion | Revue du positionnement (§4.16) avant d'engager le lot 2 |
| Aucun financement d'audit identifié à la fin du lot 1 | Préversion prolongée (DR2) ; OIDC prioritaire au lot 2 (DR3) |
| Mainteneur seul sur tous les rôles un an après la préversion | Gel des lots 3 et 4 ; consolidation des lots 1 et 2 |

### 8.6 Revues du registre

Le calendrier des revues (§10) est inscrit dans la roadmap, à chaque fin de jalon.

---

## 9. Décisions à valider

> **Décision du 2026-10-11** : Joël valide **DR1 à DR9** tels que recommandés. Réponse à **Q-R1** : **un développeur principal, 15 à 20 heures par semaine, aucun contributeur régulier ni financement supposés** ; contributions et financements éventuels sont des **accélérateurs**, jamais des dépendances du planning. Conséquences sur ce registre : R-O08 et R-O05 sont confirmés à leur cotation résiduelle (la capacité réelle est celle qui avait été redoutée) ; R-O09 passe à 4×4=16, car aucun audit financé n'est supposé, ce qui fait de la préversion sans audit (DR2) le scénario de référence. Les critères d'arrêt adaptés à cette capacité sont fixés dans `ROADMAP.md`, qui remplace les valeurs indicatives du §8.5.

| ID | Question | Options | Recommandation |
|---|---|---|---|
| **DR1** | Ordonner le lot 1 en deux jalons 1a et 1b (M-01) ? | (a) Lot 1 d'un seul tenant (b) 1a « noyau sourcé » avec **WordPress seul** et interface FR, puis 1b (Ghost, EN, API stable, compléments) | **(b)**. Rien n'est retiré du lot 1 ni de D10 / D13 ; la première valeur arrive plus tôt. WordPress d'abord parce qu'il équipe la grande majorité des sites existants ; S7 peut inverser ce choix si Ghost s'avère nettement plus simple |
| **DR2** | Une version peut-elle être qualifiée de « stable » sans audit externe de l'authentification et du chiffrement ? | (a) Oui, si l'auto-évaluation ASVS est complète (b) Non : « préversion » avec avertissement tant que l'audit n'a pas eu lieu | **(b)**. C'est la contrepartie naturelle de DT14 option (a) |
| **DR3** | Avancer la connexion OIDC (client) du lot 4 au lot 2, en option ? | (a) Lot 4, comme prévu (b) Lot 2, facultative pour l'utilisateur | **(b)**. Le modèle de comptes la prépare dès le lot 1 ; elle offre une alternative éprouvée à l'authentification maison pour les organisations exigeantes |
| **DR4** | Rendre bloquante la similarité sémantique quand l'article et la source sont dans des langues différentes ? | (a) Non, alerte seulement (b) Oui | **(b)**. Sans cela, la traduction d'une source échappe à tout contrôle bloquant |
| **DR5** | Introduire au lot 1 la validation proportionnée au risque et sa mesure locale (M-03, M-04) ? | (a) Non, validation simple (b) Oui | **(b)**. C'est la seule protection de la mitigation dont dépendent six risques graves |
| **DR6** | Rendre les secrets déchiffrables par le worker seul (M-06) ? | (a) Non : clé maîtresse partagée par API et worker (ADR-11 tel quel) (b) Oui, sous réserve de S6 | **(b) sous réserve de S6**. Compatible avec ADR-11 ; protège les secrets contre la compromission du processus le plus exposé |
| **DR7** | Ajouter les garde-fous « liens » (bloquant) et « personnes et organisations » (alerte) au lot 1 (M-05) ? | (a) Non (b) Oui | **(b)**. Coût faible ; ferme la principale conséquence pratique d'une injection de prompt et réduit le risque de diffamation |
| **DR8** | Cadre des contributions ? | (a) DCO (certificat d'origine, simple) (b) CLA (cession ou licence au projet, permet une double licence) (c) Rien | **(a)**. Une double licence n'est utile que pour une exploitation commerciale qui ferait entrer le projet dans le champ du règlement sur la cyber-résilience (R-J11) et rebuterait des contributeurs ; à reconsidérer si D1 est un jour activée |
| **DR9** | Ajouter S7 « connecteurs CMS » aux preuves de concept du lot 1 (M-10) ? | (a) Non, couvert par S3 (b) Oui | **(b)**. S3 teste le format de document, pas l'idempotence ni le rapprochement, qui sont l'hypothèse la plus fragile du lot 1 |

**Question ouverte nécessaire à `ROADMAP.md`**

| ID | Question | Pourquoi |
|---|---|---|
| **Q-R1** | Quelle **capacité** prévoir pour le développement : combien de personnes, combien d'heures par semaine, et est-il envisagé de chercher des contributeurs ou un financement dès le lot 1 ? | Sans cette hypothèse, la roadmap ne peut ni dater les jalons ni fixer les critères d'arrêt (R-O08, M-02) |

---

## 10. Suivi du registre

### 10.1 Cadence

| Revue | Moment | Contenu |
|---|---|---|
| **Légère** | Mensuelle pendant le développement | Dix risques prioritaires, signaux précoces, nouveaux risques |
| **Complète** | Fin de chaque jalon (1a, 1b, lots 2 à 4) et fin des preuves de concept | Recotation de tout le registre, mise à jour des mitigations |
| **Exceptionnelle** | Après tout incident de sécurité, toute publication fautive signalée, tout changement réglementaire ou jurisprudentiel pertinent (règlement sur l'IA, cyber-résilience, fouille de textes) | Risques concernés et leurs voisins |

### 10.2 Règles

- **Pas de baisse de cotation sans preuve** : une cotation résiduelle ne baisse que sur résultat d'une preuve de concept, d'un test, d'une mesure ou d'un audit, cité dans l'historique.
- **Une mitigation repoussée remonte le risque** : si une mitigation prévue pour un lot n'est pas livrée, la cotation résiduelle revient à la brute pour ce lot.
- **Tout risque critique a un plan de repli écrit** (§4).
- Au passage en dépôt, chaque risque critique ou élevé devient un ticket étiqueté, lié à ce registre, qui reste la référence.

### 10.3 Sources des indicateurs

| Source | Indicateurs | Visibilité |
|---|---|---|
| **Tableau de santé de l'instance** (AR §21, TC §8.5) | Files, recherche, mémoire, coûts IA, taux de réparation par profil, sauvegardes, destination distante, avis de sécurité, mesures de validation (M-04) | Administrateur de l'instance seulement ; aucune télémétrie |
| **Intégration continue** | `import-linter`, tests d'isolation, concordance du rendu, propriétés du PDP, restauration, migrations, licences, évaluations | Projet |
| **Suivi des jalons** | Temps passé par domaine (parcours de compte, infrastructure Web, générateur), dépassements | Projet |
| **Retours des utilisateurs** | Tickets, tests d'utilisabilité, signalements de sécurité, demandes de retrait | Projet |
| **Veille réglementaire** | Règlement sur l'IA, cyber-résilience, droit d'auteur, conditions des plateformes et fournisseurs | Projet |

Limite assumée : l'absence de télémétrie (AR §21) prive le projet de toute mesure directe chez ses utilisateurs. Les signaux R-O10, R-S09 et R-P06 reposeront sur des **volontaires** et des retours explicites.

---

## 11. Annexes

### 11.1 Correspondance avec les cotations de l'analyse fonctionnelle

Ancienne cotation sur 3 × 3 (C sur 9) ; nouvelle sur 5 × 5 (C sur 25).

| ID | Ancien P×I=C | Nouveau brut | Nouveau résiduel | Commentaire |
|---|---|---|---|---|
| R-T01 | 3×2=6 | 15 | 8 | Inchangé sur le fond ; repoussé au lot 3 |
| R-T02 | 3×3=9 | 25 | 16 | Reste le premier risque technique ; C1 au lot 1 ne couvre que les chiffres |
| R-T03 | 3×1=3 | 8 | 6 | — |
| R-T04 | 2×3=6 | 12 | 9 | Précisé : l'injection ne peut pas publier mais peut modifier le contenu |
| R-T05 | 3×2=6 | 12 | 6 | — |
| R-T06 | 2×3=6 | 16 | 12 | Relevé : le lot 1 est très chargé |
| R-T07 | 1×3=3 | — | — | Reclassé en R-S03 (2×5=10), relevé : l'enveloppe ne protège pas l'instance |
| R-T08 | 2×2=4 | 12 | 6 | Dépend désormais de R-T18 |
| R-T09 | 2×1=2 | 4 | 4 | Accepté |
| R-T10 | 2×3=6 | 16 | 12 | Relevé : angle mort inter-langues |
| R-J01 | 2×3=6 | 16 | 12 | Relevé : traduction |
| R-J02 | 2×2=4 | 9 | 6 | — |
| R-J03 | 2×2=4 | 9 | 6 | Complété par R-J09 |
| R-J04 | 2×3=6 | 20 | 15 | Relevé : dépend de la qualité réelle de la validation |
| R-J05 | 2×2=4 | 12 | 9 | Précisé : obligations de fournisseur, déjà en vigueur |
| R-J06 | 2×2=4 | 12 | 9 | — |
| R-J07 | 1×2=2 | 6 | 4 | Accepté |
| R-J08 | 2×3=6 | 10 | 5 | Hors périmètre (D1) |
| R-O01 | 2×3=6 | 12 | 8 | Lot 3 |
| R-O02 | 2×2=4 | 9 | 4 | Bien couvert par les budgets à réservation |
| R-O03 | 2×3=6 | 10 | 5 | **Le mieux couvert du registre** (PDP, R2, revérification) |
| R-O04 | 2×2=4 | 16 | 12 | Relevé : l'installateur non expert est la cible |
| R-O05 | 2×3=6 | 20 | 15 | Relevé : volet non technique absent |
| R-O06 | 3×2=6 | 15 | 12 | Lot 3 |
| R-O07 | 2×3=6 | 15 | 10 | — |
| R-P01 | 2×3=6 | 15 | 10 | — |
| R-P02 | 2×2=4 | 12 | 9 | — |
| R-P03 | 2×1=2 | 6 | 6 | Accepté |
| R-P04 | 2×3=6 | 12 | 6 | Bien couvert par D12 |
| R-P05 | 2×2=4 | 12 | 6 | Bien couvert par UXM1 à UXM8 |

### 11.2 Points factuels à vérifier

Les affirmations suivantes fondent des cotations mais n'ont pas été vérifiées sur pièce. Elles sont à confirmer par la preuve de concept ou l'interlocuteur indiqué ; une infirmation entraîne une recotation.

| ID | Point | Vérification | Risques |
|---|---|---|---|
| V1 | L'API REST de WordPress ne permet pas de rechercher un article par métadonnée arbitraire sans code côté serveur | S7 | R-T18 |
| V2 | Ghost n'offre pas de champs personnalisés sur les articles ; un marqueur d'idempotence passe par une étiquette interne ou un autre champ | S7 | R-T18 |
| V3 | Droits effectifs d'un mot de passe d'application WordPress (ceux de l'utilisateur) et d'une clé d'intégration Ghost | S7 | R-S03 |
| V4 | L'exemption des logiciels libres du règlement sur l'IA (art. 2, §12) ne couvre pas l'art. 50 ; calendrier applicable après les propositions de simplification | Conseil juridique (Q-J3) | R-J05 |
| V5 | Règlement sur la cyber-résilience : obligations de signalement applicables depuis septembre 2026, obligations principales en décembre 2027 ; régime des gestionnaires de logiciels libres | Conseil juridique (Q-J4) | R-J11 |
| V6 | Portée de l'exception de fouille pour la génération | Conseil juridique (Q-J1) | R-J09 |
| V7 | Disponibilité actuelle de programmes finançant des audits de sécurité de logiciels libres | Recherche de financement (M-07) | R-O09, R-S01 |
| V8 | Comportement de la RLS avec le rôle applicatif, `SET LOCAL` et les connexions de Procrastinate | S1, S2 | R-S02 |

### 11.3 Risques explicitement acceptés

| ID | Raison |
|---|---|
| R-T09 | Les modèles locaux sont facultatifs et tournent hors du profil solo |
| R-J07 | La licence exclut toute garantie ; les valeurs par défaut prudentes et la documentation suffisent au regard de la probabilité |
| R-P03 | La concurrence est un fait de marché ; la différenciation est assumée par le positionnement |

---

*Fin du document. Registre validé le 2026-10-11 ; l'étape suivante est `ROADMAP.md`, qui reprend les exigences du §8.*

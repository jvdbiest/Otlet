# État du projet Otlet

Mis à jour le 2026-10-17. Une page : ce qu'il faut savoir pour reprendre le travail tout de suite. L'historique est dans Git, les décisions sont dans `docs/adr/`, les mesures dans `docs/spikes/`.

## Où on en est

Étape **É0** (preuves de concept et socle) **close le 2026-10-16** ; décision P1 dans `docs/projet/P1.md`. Étape en cours : **É1**, tranche verticale personnelle (`ROADMAP.md` §5.2). Plan **validé par Joël le 2026-10-16** : `docs/projet/plan-E1.md` (décisions au §7), backlog `docs/projet/backlog-E1.csv`. Cinq incréments, I0 Socle, I1 Lire, I2 Rédiger (avec la sauvegarde), I3 Contrôler et copier, I4 Fiabiliser.

| Bloc | État |
|---|---|
| Socle B02 à B10 | Fait. B01 (création du dépôt) n'est pas coché au backlog, mais il est réalisé |
| S6 Squelette de livraison | Conclue : partiel (mesurée sur VM, pas sur VPS). ADR-0019, ADR-0020 |
| S1 PostgreSQL et RLS | Conclue : partiel. La recherche plein texte, remesurée par P01 sur corpus réel, échoue faute d'index utilisable sous RLS : correction proposée (ADR-0033), remesure P01b à suivre. ADR-0021 |
| S2 File de tâches | Conclue : succès (Procrastinate). ADR-0022 |
| S3 Format et éditeur | Conclue : succès (Tiptap). ADR-0023 |
| S5 Similarité | Conclue : échec, de peu ; complément S5b conclu en échec sur la mémoire seule. Modèle retenu (ADR-0024) : potion-multilingual-128M par `model2vec` en int8, 870 Mio, qualité inchangée. Pile complète estimée à 2,4 Go en charge, sous 3,4 Go (déduction) |
| S4 Passerelle IA | Conclue : partiel. Ollama (qwen2.5 1,5B) « testé » à 96 % ; budget jamais dépassé ; replis 100 % ; fournisseurs payants et à compte externe bloqués sans accord de Joël. ADR-0027 accepté |
| S7 Connecteurs CMS | Conclue : partiel. 0 doublon et 100 % de rapprochement sur WordPress 7.1, 6.9 et Ghost ; Wordfence par défaut bloque les mots de passe d'application ; mutualisé non démontré. ADR-0026 accepté |
| B11 Clôture (rapport P1) | Faite. **É0 close le 2026-10-16** (décision P1 de Joël, `docs/projet/P1.md`) : É1 démarre recalibré |

## Prochaine action

1. **I0 close** le 2026-10-16 (X01 fusionnée). I1 Lire en cours.
2. Sur `main` (2026-10-16 et 17) : U01, U02, U02b, U02c (filtre des sources), X02 (flux de tri et parcours d'accueil), les boutons de tri dans la recherche, le filtre par sujets à choix multiple, le sujet principal en badge sur les cartes, la langue devinée des éléments (migration 0010) et les sujets définis par leurs sources (migration 0011). X02 sera « fait » après une semaine d'usage par Joël (critère du backlog).
3. Joël répond à l'ADR-0032 (règles du score).
4. **Recherche plein texte** : P01 (échec, index inutilisable sous RLS) puis ADR-0033 accepté et corrigé ; **P01b conclue le 2026-10-17 : échec partiel** (`docs/spikes/P01b.md`) : l'index sert, Q3 tient le seuil, Q1 reste à 8,8 s à cause de la fenêtre. `perf/fenetre-recherche` prend la fenêtre dans la fonction (migration 0013, complément de l'ADR-0033) et ouvre P01c. Après sa fusion par Joël, mesure P01c sur la VM du NAS (corpus et requêtes de P01 gardés dans `~/p01-corpus`). I1 se clôt avec la recherche sous le seuil et la semaine d'usage de X02.
5. Joël note son temps une fois par semaine dans `docs/projet/journal-temps.csv` (domaine `projet`).
6. Plus tard, avec l'accord de Joël pour chacun : mesurer les fournisseurs réels de S4 (50 briefs chacun, plafonds de dépense posés).

## Règles de travail

- **Protocole des preuves (ADR-0018)** : rapport avec ses seuils fusionné sur `main` **avant** toute mesure ; seuils jamais modifiés après ; durée maximale tenue ; conclusion obligatoire.
- **Isolation (F03, ADR-0028)** : toute nouvelle table métier appelle `rls.workspace_scoped` dans sa migration ; toute route d'un espace vit sous `/api/workspaces/{workspace_id}` et lit la base par `WorkspaceConnection`. Les tests d'isolation parcourent toutes les routes et échouent si une route oublie la session ou l'appartenance à l'espace.
- **Rôles de la base (M-12)** : la pile Compose se connecte avec `otlet_app` (contraint par la RLS) et migre avec `otlet_migrator` ; le superutilisateur ne sert qu'au service `provision` et à la sauvegarde. `deploy/ci/check-compose.sh` vérifie « sans contexte, zéro ligne » sur la pile.
- **Sorties réseau (U01, ADR-0031)** : toute requête sortante passe par `otlet.platform.http.SafeClient` (protection SSRF). Les échéances du domaine passent par le rôle `scheduler` (verrou consultatif), les tâches de maintenance par la cron des workers (ADR-0030).
- **Tâches de fond (F04, ADR-0022)** : un module déclare ses tâches avec `otlet.jobs.application.registry.job` et les enfile avec `procrastinate_queue.enqueue` sur la connexion de sa transaction. Une tâche reçoit des identifiants, jamais des objets, et pose elle-même son contexte d'espace. Le module doit figurer dans `JOB_MODULES` du worker.
- **Git** : une branche par tâche, commits signés DCO (`git commit -s`), messages en français, code en anglais. Jamais de poussée sur `main`, qui est protégée (12 vérifications de CI obligatoires).
- **Demandes de fusion** : Claude pousse et donne un lien de comparaison prérempli. Joël crée la demande et fusionne lui-même : le navigateur de l'app n'est pas connecté à GitHub, et les fusions par Claude sont bloquées.
- **Qualité d'abord (ADR-0025)** : la qualité du produit prime sur le profil solo à 4 Go, qui reste une cible. La mémoire de la pile complète, mesurée, fait foi ; les budgets par composant sont indicatifs.
- **NAS = référence basse (décision de Joël du 2026-10-15)** : la VM du NAS est la plateforme minimale de validation, pas l'environnement de travail recommandé. Une copie tourne sous VMware sur le PC de Joël (`192.168.129.252`, 8 vCPU, 16 Go, 79 Go) pour les traitements longs ; ses résultats sont rapportés à part.
- **ADR** : « Proposé » tant que Joël n'a pas répondu explicitement « oui ». Une fusion ne vaut pas acceptation.
- **Heures** : Claude ajoute une estimation grossière par tâche terminée dans `docs/projet/journal-temps.csv`.
- **Dépenses et logiciels système** : accord de Joël avant toute dépense, service externe ou installation sur son poste.

## Environnement

| Élément | Détail |
|---|---|
| Dépôt | https://github.com/jvdbiest/Otlet (AGPL-3.0-or-later, DCO) |
| Poste de Joël | Windows 11, PowerShell 5.1 (encodage cp1252, CRLF). Docker Desktop installé : prévenir avant de le démarrer, et ne pas toucher aux conteneurs `wyoming-*`. Pas de Node : `npm` tourne dans `node:24-slim` |
| VM de mesure | NAS de Joël, `192.168.129.249`, Ubuntu 24.04, 2 vCPU, 3,8 Go. SSH : `ssh -i ~/.ssh/otlet_nas otlet@192.168.129.249`, `sudo` sans mot de passe. Instantané restaurable par Joël |
| VM de travail | Copie de la VM du NAS sous VMware sur le PC de Joël (i7-14700K) : `192.168.129.252`, même compte et même clé SSH. Arrêtée quand le PC est éteint |
| VM vierge (P04) | Sur le PC de Joël : `192.168.129.253`, Ubuntu 26.04.1 Desktop, 2 vCPU, 4 Go (3,3 Go visibles), 40 Go ; même compte et même clé SSH. **Instantané vierge** pris par Joël le 2026-10-16 : ne rien y installer avant la mesure d'I4, qui repart de cet instantané |
| Sur la VM | Pile Otlet dans `/opt/otlet` (PostgreSQL de la pile réglé pour S1). CMS de test dans le projet Compose `otlet-cms` : WordPress 7.1 (port 8081), WordPress 6.9 (8082), Ghost 6.69 (2368) ; identifiants dans `~/otlet-cms.env` |
| Essais du code | Sur la VM de travail, dans des conteneurs jetables (`otlet-dev-pg`, PostgreSQL 18 et pgvector comme la CI), avec une copie du dossier `backend` dans `~/otlet-dev` |
| Mesures longues | Toujours détachées sur la VM (`nohup`), jamais liées à une session SSH depuis le poste |

## Points ouverts à garder en tête

- S6 : installation chronométrée sur un VPS vierge, reportée à É1 (D2 de P1), sans location pour l'instant.
- Remesurer la recherche plein texte (S1, L2) sur un corpus réaliste avant toute conclusion définitive (ADR-0021).
- Écrire un nettoyeur de collage Word et Google Docs pour Tiptap (ADR-0023).
- ASVS V12.3 : chiffrer ou non les liaisons internes de la pile Compose (`docs/security/asvs-l2.md`).
- Volet lexical du garde-fou : remplacer les 5-grammes par la plus longue séquence commune, seuil à fixer avant mesure (ADR-0024).
- S7 : test court de connexion et de publication sur un hébergement mutualisé réel, pendant É1 ou dès qu'il y en aura un ; aucune dépense d'ici là (ADR-0026).
- Mesurer la mémoire de la pile entière quand le worker chargera potion (S5b §5).
- Remesurer les seuils de similarité sur un corpus réel à la tranche verticale d'É1 (ADR-0024).
- **Piste pour É1** (demande de Joël, sans changer la roadmap) : évaluer un agent local consultatif pour enrichir la veille, chercher des sources complémentaires, proposer des sujets et aider à la rédaction. Il ne publie jamais et ne contourne aucune validation humaine.
- Plus tard : redirection du port 443 vers la VM pour un certificat Let's Encrypt. Joël aura besoin d'aide pour la marche à suivre.

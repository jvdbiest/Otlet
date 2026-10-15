# État du projet Otlet

Mis à jour le 2026-10-15. Une page : ce qu'il faut savoir pour reprendre le travail tout de suite. L'historique est dans Git, les décisions sont dans `docs/adr/`, les mesures dans `docs/spikes/`.

## Où on en est

Étape **É0** (preuves de concept et socle), plan : `docs/projet/plan-E0.md`, suivi : `docs/projet/backlog-E0.csv`.

| Bloc | État |
|---|---|
| Socle B02 à B10 | Fait. B01 (création du dépôt) n'est pas coché au backlog, mais il est réalisé |
| S6 Squelette de livraison | Conclue : partiel (mesurée sur VM, pas sur VPS). ADR-0019, ADR-0020 |
| S1 PostgreSQL et RLS | Conclue : partiel. La recherche plein texte reste un **échec ouvert** jusqu'à une remesure sur corpus réel. ADR-0021 |
| S2 File de tâches | Conclue : succès (Procrastinate). ADR-0022 |
| S3 Format et éditeur | Conclue : succès (Tiptap). ADR-0023 |
| S5 Similarité | Conclue : échec, de peu ; complément S5b conclu en échec sur la mémoire seule. Modèle retenu (ADR-0024) : potion-multilingual-128M par `model2vec` en int8, 870 Mio, qualité inchangée. Pile complète estimée à 2,4 Go en charge, sous 3,4 Go (déduction) |
| S4 Passerelle IA | À faire. Prérequis A3 : clés d'API plafonnées, **accord de Joël avant toute dépense** |
| S7 Connecteurs CMS | À faire. Réutilise WordPress et Ghost de la VM. Prérequis A2 : hébergement mutualisé, **accord de Joël** |
| B11 Clôture (rapport P1) | À faire, en dernier |

## Prochaine action

1. Joël fusionne la branche `spike/S5b-conclusion`.
2. Choisir la suite : S4 (passerelle IA) ou S7 (connecteurs CMS), chacun après l'accord de Joël sur ses prérequis (clés d'API plafonnées, hébergement mutualisé).
3. Puis B11, la clôture d'É0.

## Règles de travail

- **Protocole des preuves (ADR-0018)** : rapport avec ses seuils fusionné sur `main` **avant** toute mesure ; seuils jamais modifiés après ; durée maximale tenue ; conclusion obligatoire.
- **Git** : une branche par tâche, commits signés DCO (`git commit -s`), messages en français, code en anglais. Jamais de poussée sur `main`, qui est protégée (12 vérifications de CI obligatoires).
- **Demandes de fusion** : Claude pousse et donne un lien de comparaison prérempli. Joël crée la demande et fusionne lui-même : le navigateur de l'app n'est pas connecté à GitHub, et les fusions par Claude sont bloquées.
- **Qualité d'abord (ADR-0025)** : la qualité du produit prime sur le profil solo à 4 Go, qui reste une cible. La mémoire de la pile complète, mesurée, fait foi ; les budgets par composant sont indicatifs.
- **ADR** : « Proposé » tant que Joël n'a pas répondu explicitement « oui ». Une fusion ne vaut pas acceptation.
- **Heures** : Claude ajoute une estimation grossière par tâche terminée dans `docs/projet/journal-temps.csv`.
- **Dépenses et logiciels système** : accord de Joël avant toute dépense, service externe ou installation sur son poste.

## Environnement

| Élément | Détail |
|---|---|
| Dépôt | https://github.com/jvdbiest/Otlet (AGPL-3.0-or-later, DCO) |
| Poste de Joël | Windows 11, PowerShell 5.1 (encodage cp1252, CRLF). Docker Desktop installé : prévenir avant de le démarrer, et ne pas toucher aux conteneurs `wyoming-*`. Pas de Node : `npm` tourne dans `node:24-slim` |
| VM de mesure | NAS de Joël, `192.168.129.249`, Ubuntu 24.04, 2 vCPU, 3,8 Go. SSH : `ssh -i ~/.ssh/otlet_nas otlet@192.168.129.249`, `sudo` sans mot de passe. Instantané restaurable par Joël |
| Sur la VM | Pile Otlet dans `/opt/otlet` (PostgreSQL de la pile réglé pour S1). CMS de test dans le projet Compose `otlet-cms` : WordPress 7.1 (port 8081), WordPress 6.9 (8082), Ghost 6.69 (2368) ; identifiants dans `~/otlet-cms.env` |
| Mesures longues | Toujours détachées sur la VM (`nohup`), jamais liées à une session SSH depuis le poste |

## Points ouverts à garder en tête

- Remesurer la recherche plein texte (S1, L2) sur un corpus réaliste avant toute conclusion définitive (ADR-0021).
- Écrire un nettoyeur de collage Word et Google Docs pour Tiptap (ADR-0023).
- ASVS V12.3 : chiffrer ou non les liaisons internes de la pile Compose (`docs/security/asvs-l2.md`).
- Volet lexical du garde-fou : remplacer les 5-grammes par la plus longue séquence commune, seuil à fixer avant mesure (ADR-0024).
- Mesurer la mémoire de la pile entière quand le worker chargera potion (S5b §5).
- Remesurer les seuils de similarité sur un corpus réel à la tranche verticale d'É1 (ADR-0024).
- **Piste pour É1** (demande de Joël, sans changer la roadmap) : évaluer un agent local consultatif pour enrichir la veille, chercher des sources complémentaires, proposer des sujets et aider à la rédaction. Il ne publie jamais et ne contourne aucune validation humaine.
- Plus tard : redirection du port 443 vers la VM pour un certificat Let's Encrypt. Joël aura besoin d'aide pour la marche à suivre.

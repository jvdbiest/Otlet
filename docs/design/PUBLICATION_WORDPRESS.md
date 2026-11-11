# U07 — Envoyer et publier vers WordPress depuis Otlet

| | |
|---|---|
| Statut | Proposition, à valider par Joël |
| Ouverte le | 2026-11-11 |
| Origine | Joël, 2026-11-11 : « éviter le copier-coller manuel et gérer tout le cycle depuis Otlet » |
| Choix concernés | ADR-0026 (idempotence par marqueur natif, « WordPress d'abord »), ADR-0046 (garde-fou de proximité U05), règle « aucune publication automatique sans activation explicite », `ARCHITECTURE.md` §12.4 |

## 1. Le besoin

Joël veut faire tout le cycle depuis Otlet, sans ouvrir WordPress ni copier-coller. Deux usages :

1. **Envoyer en brouillon**, pour relire et valider dans WordPress.
2. **Publier**, quand l'article lui convient et qu'il ne veut pas ouvrir WordPress.

## 2. Ce qui est proposé

**Un site par connexion, dans Réglages > Publication.** L'utilisateur ajoute un site WordPress : nom, adresse, identifiant, mot de passe d'application (créé par lui dans WordPress, Profil > Mots de passe d'application). Le mot de passe est scellé comme les clés IA (lisible par le seul worker). Un bouton « Tester » vérifie la connexion et dit la cause probable d'un échec (ADR-0026 §4). Le parcours recommande un compte de rôle Auteur (ou Éditeur pour publier), et avertit si c'est un Administrateur.

**Deux actions dans la Bibliothèque, sur la version validée d'un article :**
- **« Envoyer en brouillon vers… »** : le bouton principal, le plus visible. L'article arrive dans WordPress au statut brouillon.
- **« Publier… »** : un bouton secondaire, séparé. Il ouvre une confirmation qui nomme le site, le titre et l'adresse publique à venir ; rien ne part sans le clic « Publier maintenant ».

**Un article Otlet, un article WordPress.** Otlet garde, pour chaque article et chaque site, l'identifiant WordPress, son statut (brouillon, publié), son lien et la version d'Otlet envoyée. Un nouvel envoi **met à jour** le même article WordPress au lieu d'en créer un autre :
- brouillon dans WordPress, « Envoyer en brouillon » : le brouillon est mis à jour ;
- brouillon dans WordPress, « Publier » : le même article passe en publié ;
- déjà publié, « Publier » : l'article publié est mis à jour, avec une confirmation qui le dit (« met à jour l'article en ligne ») ;
- déjà publié, « Envoyer en brouillon » : refusé, avec le choix de publier la mise à jour ou de dépublier dans WordPress. Otlet ne repasse jamais seul un article en ligne en brouillon.

**Ce qui part.** Le titre, le texte rendu en blocs WordPress (intertitres, paragraphes, listes, citations, liens), le bloc Sources, la mention IA, et le marqueur d'idempotence d'ADR-0026 (slug `otlet-<clé>` et commentaire `<!-- otlet:<clé> -->`). Les images suivront dans un second temps (téléversement dans la médiathèque WordPress).

**Garde-fous.**
- Le garde-fou de proximité (U05) s'applique comme pour les exports : une version trop proche d'une source ne part pas sans justification.
- Aucun envoi automatique : chaque envoi et chaque publication viennent d'un clic de l'utilisateur. L'automatisation viendra en I4, activable séparément.
- Après une panne, Otlet cherche le marqueur avant de renvoyer (ADR-0026 §2) : pas de doublon. Si l'article WordPress a été supprimé, Otlet le dit et propose d'en recréer un.
- Chaque envoi est journalisé (qui, quand, quelle version, quel statut, réponse du site).

**Ce que voit l'auteur.** Dans la Bibliothèque, l'article montre « Brouillon sur Mon site » ou « Publié sur Mon site », avec le lien, la date et la version envoyée. Si la version validée a changé depuis, il le signale (« la version en ligne est plus ancienne »).

## 3. Ce qui n'est pas proposé ici

- Ghost et les réseaux sociaux : même schéma plus tard, un connecteur par canal.
- Dépublier ou supprimer un article WordPress depuis Otlet.
- La planification d'une publication à une date.

## 4. Essai

Sur le WordPress local du NAS (http://192.168.129.249:8080), avec un compte Auteur ou Éditeur créé par Joël : un envoi en brouillon, une mise à jour du brouillon, une publication confirmée, une mise à jour de l'article publié, et une coupure réseau pendant un envoi (aucun doublon attendu).

## 5. Questions à trancher

1. Le rôle du compte WordPress : Éditeur (il peut publier) ou Auteur (il peut publier ses propres articles, suffisant ici) ?
2. Catégories et étiquettes : faut-il les choisir dans Otlet dès cette version, ou les laisser à WordPress ?
3. Images : dans cette version ou dans la suivante ?

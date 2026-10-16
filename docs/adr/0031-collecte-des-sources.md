# ADR-0031 — Collecte des sources : client protégé, règles des sites et statut juridique

| | |
|---|---|
| Statut | Accepté (2026-10-16) |
| Date | 2026-10-16 |
| Décideur | Joël |
| Documents touchés | `ARCHITECTURE.md` §12.5, §13.1, §13.2 ; `TECH_CHOICES.md` §14 ; `RISKS.md` M-08 ; ADR-0030 |
| Origine | Tâche U01 du plan d'É1 (`docs/projet/plan-E1.md`) |

## Contexte

U01 fait entrer dans Otlet les premiers contenus venus de l'extérieur. Trois questions se posent dès la première source : comment empêcher qu'une adresse saisie atteigne le réseau interne du serveur (SSRF), comment lire les règles que les sites expriment, et comment montrer à l'utilisateur ce qu'il peut faire des textes collectés (M-08). La bibliothèque d'extraction prévue (`trafilatura`) tire aussi une dépendance dont la licence pose question.

## Décision

1. **Un seul client HTTP sortant**, `otlet.platform.http.SafeClient`, pour toute la plateforme. Il n'accepte que HTTP et HTTPS sur les ports 80 et 443. Il résout lui-même les noms, refuse la connexion dès qu'une des adresses obtenues n'est pas publique (privée, bouclage, liaison locale, métadonnées cloud, partagée, réservée, multidiffusion, et leurs formes IPv6), puis se connecte à l'adresse vérifiée. Ce contrôle se fait sous la couche HTTP, à chaque connexion, donc à chaque redirection (cinq au plus). Durée et taille sont bornées. Des exceptions par réseau restent possibles pour l'administrateur (moteur IA local, §13.2) ; U01 n'en déclare aucune.
2. **Règles des sites.** robots.txt suit la RFC 9309 : un 4xx vaut « pas de règle », un 5xx, un 429 ou une erreur réseau vaut « tout est interdit ». Otlet cherche le groupe `Otlet`, puis `*`. La réserve de fouille suit le protocole TDMRep : fichier `/.well-known/tdmrep.json` (première règle qui correspond), en-têtes `tdm-reservation` et `tdm-policy`, balises `meta` de la page. Une réserve, d'où qu'elle vienne, l'emporte. Les règles d'une origine sont gardées un jour.
3. **Statut juridique visible par source** (M-08) :
   - `refused` : robots.txt ferme le flux, rien n'est collecté ;
   - `summary_only` : une réserve de fouille, ou robots.txt qui ferme les pages : seuls le titre, le lien et le résumé fournis par le flux sont gardés, et la page n'est jamais demandée ;
   - `full_text` : les pages sont lues et leur texte principal est gardé.
   Chaque élément porte aussi le statut de son texte et sa raison. Le journal de conformité d'une source enregistre chaque changement de décision, avec sa raison et la politique annoncée par le site.
4. **Saisie manuelle encadrée** : une adresse donnée à la main est lue sous les mêmes règles qu'un flux. Un texte collé exige une origine et un droit d'usage déclarés, et reste marqué `manual`. La base refuse un texte collé sans ces deux champs.
5. **La collecte planifiée revient au planificateur** (ADR-0030) : il prend le verrou consultatif PostgreSQL, puis toutes les 30 secondes il enfile la collecte des sources dues. Une collecte manquée pendant un arrêt est faite une fois, puis replanifiée un intervalle plus tard. Les workers font les collectes et les lectures de pages. Une source en échec est retentée de plus en plus tard (intervalle doublé à chaque échec, plafonné à une semaine), puis passe « dégradée » après 3 échecs et « morte » après 10. Elle n'est jamais abandonnée. Le service `scheduler` rejoint la pile Compose solo.
6. **Extraction par `readability-lxml`** (Apache-2.0) au lieu de `trafilatura`. `trafilatura` tire `dateparser`, qui dépend de `regex`, publié sous « Apache-2.0 AND CNRI-Python ». La licence CNRI de Python 1.6 est jugée incompatible avec la GPL par la FSF, et `tools/check_licenses.py` la refuse. `readability-lxml` était le repli prévu au §14 de TECH_CHOICES ; elle n'extrait ni l'auteur ni la date, qui viennent alors du flux.

## Validation de Joël (2026-10-16)

Aux deux questions posées :

1. Accepter `regex` (licence CNRI-Python) pour passer à `trafilatura`, ou garder `readability-lxml` ? Réponse : « Garder ». L'extraction reste à `readability-lxml` ; la question pourra être reprise à U06 si l'extraction se montre insuffisante.
2. Un avertissement à l'ajout d'une source, qui rappelle que l'utilisateur reste responsable des conditions d'utilisation non lisibles par une machine (CJ-04), suffit-il pour É1 ? Réponse : « Oui ». Il est affiché dans l'écran des sources.

## Conséquences

- Les tests de `tests/platform/test_http.py` couvrent les plages refusées, les redirections vers les métadonnées cloud, le changement d'adresse entre deux résolutions et les schémas interdits. Toute nouvelle sortie réseau doit passer par ce client.
- Les mesures sur la VM de travail avec de vrais flux (Le Monde, BBC, The Guardian, Python Insider, Nature) donnent des statuts cohérents : Nature réserve la fouille par tdmrep.json et passe en « résumé seulement » ; une adresse du réseau local est refusée.
- Un site qui répond par une page anti-robot à `/.well-known/tdmrep.json` est traité comme sans fichier : seul un JSON valide compte.

## Options écartées

- Filtrer les adresses avant la requête, puis laisser la bibliothèque résoudre à nouveau : une seconde résolution peut renvoyer une autre adresse (DNS rebinding).
- Un mode « ignorer robots.txt » : refusé par principe (R-J03).
- Le planificateur intégré aux workers (cron de Procrastinate) pour la collecte : contraire à ADR-0030, qui réserve les échéances du domaine au rôle `scheduler`.

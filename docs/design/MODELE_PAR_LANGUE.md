# Modèle par langue de rédaction

| | |
|---|---|
| Statut | Construit le 2026-11-11, sans mode « Automatique » (LANG1 et LANG2 en échec) |
| Ouverte le | 2026-11-10 |
| Origine | Joël, 2026-11-10, après la comparaison en néerlandais de trois modèles locaux sur le brief MotoGP |
| Choix concernés | ADR-0027 (passerelle IA : l'utilisateur choisit, l'administrateur autorise ou bloque), contrôle de langue du brouillon |

## 1. Le besoin

Un brief demande une langue de rédaction. Le modèle écrit directement dans cette langue à partir des sources, souvent en français : ce n'est pas une traduction. Les modèles locaux ne se valent pas d'une langue à l'autre. Sur le brief MotoGP en néerlandais, gemma4 écrivait le mieux, mistral-small faisait le moins d'erreurs de faits mais prenait 33 minutes, et qwen3:14b était le plus faible. Aujourd'hui, l'auteur doit s'en souvenir et choisir le modèle dans chaque brief.

## 2. Ce qui est proposé

- **Un réglage de l'utilisateur**, dans ses réglages IA : « Modèle par langue de rédaction ». Pour chaque langue proposée par les briefs, l'utilisateur choisit :
  - « Mon profil habituel » (par défaut) : rien ne change par rapport à aujourd'hui ;
  - un modèle parmi ceux de ses fournisseurs ;
  - « Automatique », **seulement si le banc LANG1 le justifie** pour cette langue (§4).
- **L'ordre de priorité** au moment de rédiger :
  1. le modèle fixé dans le brief, s'il y en a un ;
  2. le modèle réglé pour la langue du brief ;
  3. le profil habituel de l'utilisateur, avec ses replis (ADR-0027).
- **Le rôle de l'administrateur ne change pas** : il autorise ou bloque des fournisseurs. Il ne choisit pas de modèle par langue pour les utilisateurs.
- **Dans la page de création du brief**, un lien « Choisir le modèle pour cette langue » à côté de la liste « Langue ». Il ouvre le réglage dans un nouvel onglet ou un panneau, pour ne pas perdre le brief en cours. Sous la liste, une ligne dit quel modèle écrira : « Écrit par gemma4 (réglage pour le néerlandais) ».
- **Le brouillon garde la trace** du modèle utilisé et de la raison de ce choix (brief, langue ou profil), comme il garde déjà le modèle aujourd'hui.

## 3. Ce qui n'est pas proposé

- Aucune traduction d'un brouillon déjà écrit. C'est un autre sujet, qui pourra venir plus tard.
- Aucun choix caché : le mode « Automatique » affiche toujours le modèle qu'il a pris.
- Aucun changement du contrôle de langue : il reste le filet si un modèle répond dans une autre langue.

## 4. Le mode « Automatique »

Il ne sera proposé que si LANG1 montre, pour une langue, un modèle meilleur de façon stable sur plusieurs sujets, et pas sur un seul brief. Ses règles seront décidées avec Joël après la mesure. Elles seront écrites ici, avec les modèles et la date de la mesure, car un nouveau modèle installé peut les rendre caduques. Si un modèle recommandé n'est pas installé chez l'utilisateur, le mode « Automatique » prend le profil habituel et le dit.

## 5. Questions ouvertes, à trancher après LANG1

- Le mode « Automatique » vaut-il la peine, ou un simple conseil affiché à côté de la liste suffit-il (« Pour le néerlandais, gemma4 a donné les meilleurs résultats ») ?
- Faut-il refaire la mesure quand un nouveau modèle est installé ?
- Le français, langue de la plupart des sources, a-t-il besoin d'un réglage, ou le profil habituel suffit-il ?

## 6. Ce qui est construit (2026-11-11)

Décision de Joël après LANG2 : le réglage manuel d'abord, la ligne de langue neutre dans la charte pour la cohérence, pas de chartes par langue pour l'instant. Si des règles propres à une langue deviennent utiles, ce sera une charte générale complétée par des règles par langue, pas trois chartes indépendantes.

- **Réglages > IA > « Modèle par langue de rédaction »** : pour chacune des 7 langues des briefs, « Mon profil habituel » ou un modèle des fournisseurs de l'utilisateur, avec les mêmes contrôles que le profil (fournisseur à soi, modèle permis par l'instance). Table `ai_language_models` (migration 0047), sous sécurité par ligne comme le profil ; supprimer un fournisseur supprime ses choix.
- **Ordre de priorité à la rédaction** : le modèle du brief, sinon celui de la langue du brief, sinon le profil. Le brouillon garde `model_reason` (`brief`, `language` ou `profile`).
- **Page du brief** : sous la liste « Langue », la ligne « Écrit par … » dit quel modèle écrira et pourquoi, avec le lien « Choisir le modèle pour cette langue » qui ouvre le réglage dans un nouvel onglet.
- **Un conseil, pas un automatisme** : le réglage rappelle que gemma4 est le seul modèle local essayé qui a toujours tenu la langue (LANG1, LANG2).
- **Charte par défaut** : la ligne 20 devient « Écris dans la langue de rédaction demandée par le brief, dans un style correct, clair, fluide et professionnel. ». Une charte modifiée par un utilisateur n'est pas touchée.

Essai réel sur .252 : un brief néerlandais sans modèle, avec gemma4 réglé pour le néerlandais, a été écrit par gemma4 (`model_reason` = `language`), en néerlandais, en 1 min 30. Le réglage de Joël a été remis à vide ensuite.

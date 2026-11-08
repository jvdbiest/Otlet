# Cas de référence du Reporter et de la rédaction

Ces cas servent à rejouer toute modification de la recherche, du tri ou de la rédaction. Chacun est conservé sur l'instance de Joël (VM .252), avec ses conversations et ses briefs. Ils ne sont pas supprimés.

| Cas | Domaine | Ce qu'il montre | Où | Origine |
|---|---|---|---|---|
| Froid (« Pourquoi risque t'il de faire très froid… ») | Recherche, tri | Réponses qui n'écrivent pas « froid » ; articles de pratique (raclette, chauffage) retenus | conversation « [Banc recherche] Pourquoi risque t'il… » ; TRI1, TRI2 | Joël, 2026-11-01 et 07 |
| Ukraine (« dernières actualités ») | Tri | Contexte retenu (présidentielle bulgare) ; effet de lot | conversation « [Banc recherche] Quelles sont les dernières actualités concernant l'Ukraine ? » ; TRI1, TRI2 | Joël, 2026-11-01 et 07 |
| Motos (« Les essais de motos récents ») | Tri | Les « Top 5 » sont du même thème, pas de la matière | jeu figé de TRI1 (`spikes/tri1/labels.csv`) | Joël, 2026-11-07 |
| **MotoGP Qatar : Martín deuxième au lieu de troisième** | **Fidélité des faits** | **Première inversion de fait démontrée.** Le brouillon écrit que Martín finit deuxième du sprint « après avoir dépassé Fabio Di Giannantonio dans le dernier tour ». Les sources disent l'inverse : Di Giannantonio prend la deuxième place à Martín, troisième. Le modèle a mêlé la place au championnat (deuxième) et la place dans la course. Un premier brouillon sur les mêmes articles était juste. | brief 0793d3f8 (article a8aa3e24, version 1), conversation « [RB1-bis] Quels sont les résultats du Grand Prix du Qatar de MotoGP ? » ; sources Auto-Moto « Marquez remporte la course sprint, Bezzecchi chute, Martin impressionnant » et Motor Tribu « MotoGP – Qatar, Losail, la course Sprint » | RB1 §9, Joël, 2026-11-08 |
| MotoGP Qatar : top 5 avec « respectivement » | Fidélité des faits | « Pedro Acosta et Johann Zarco, cinquième, complètent le top 5 avec respectivement 299 et 281 points » : les sources donnent 281 points à Ai Ogura. Deuxième erreur d'association, trouvée par FID1 (V3) | premier brouillon RB1 du MotoGP (question 6) | FID1, 2026-11-08 |
| Réforme de la police fédérale | Fidélité des faits | Matière mince (deux résumés) : renvoyé pour « trop court », le brouillon inventait 3 paragraphes sur 4 | RB1 (question 8), puis [RB1-bis] après la correction | RB1, 2026-11-08 |
| Tests high-tech (« publiés récemment ») | Recherche | Concepts exigés ensemble qui ne se rencontrent jamais : 1 test sur 7, puis 0 avec un autre découpage du modèle | conversations « [RB1] » et « [RB1-bis] Les tests d'appareils high-tech publiés récemment » | RB1, 2026-11-08 |

Pour le cas MotoGP, un contrôle sans modèle devrait vérifier qu'une place (« deuxième », « troisième », « 2e ») liée à un nom dans le brouillon est liée au même nom dans une source. Il reste à mesurer.

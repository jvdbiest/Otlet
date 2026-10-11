# Contribuer

Merci de votre intérêt. Le projet est tenu par un seul mainteneur, à temps partiel : les réponses peuvent prendre quelques jours.

## Signature DCO (obligatoire)

Chaque commit doit porter une ligne `Signed-off-by` qui atteste le [Developer Certificate of Origin 1.1](DCO) :

```sh
git commit -s -m "Votre message"
```

L'intégration continue refuse les commits non signés. Il n'y a pas d'accord de cession de droits : vous restez titulaire de vos contributions, publiées sous `AGPL-3.0-or-later`.

## Avant d'ouvrir une demande de fusion

- Pour une modification non triviale, ouvrez d'abord un ticket : le périmètre de chaque étape est fixé par la [roadmap](docs/design/ROADMAP.md).
- Toute décision qui modifie un document de `docs/design/` passe par un ADR (`docs/adr/0000-modele.md`).
- La CI doit être verte : lint, typage strict, tests, contrats d'imports (`import-linter`, sans exception), licences des dépendances.
- Toute dépendance nouvelle doit avoir une licence compatible avec l'AGPL-3.0 (liste dans `docs/design/TECH_CHOICES.md` §1.1).

## Conventions

- Code, identifiants et commentaires en anglais ; documentation et messages de commit en français (l'anglais est accepté).
- Message de commit : une première ligne courte à l'impératif, puis le pourquoi.
- Le code des preuves de concept vit dans `spikes/` et n'est jamais importé par `backend/`.

# Identité des établissements YEM — interfaces PC

Les écoles possèdent leur **propre logo, bannière, ville et devise**. Ces informations sont stockées par établissement, chargées après la sélection de l'école connectée et présentées dans les en-têtes de ses interfaces de gestion.

Le logo officiel YEM situé en haut à gauche, ses fichiers sources et la palette de l'application ne sont jamais remplacés. Le logo de l'établissement reste distinct et se trouve à côté de son nom et dans la bannière à droite des en-têtes de page. Un établissement qui n'a pas encore chargé de photo voit un fond neutre, et non la photo d'une autre école.

## Configuration

**Paramètres → Identité de l’établissement → Logo et bannière de l’établissement**.

- Nom officiel : reprend la fiche établissement, en lecture seule dans ce module.
- Ville et devise : facultatives.
- Logo : JPEG ou PNG, converti au besoin côté client, 350 Ko maximum au stockage.
- Bannière : JPEG ou PNG panoramique, convertie au besoin côté client, 900 Ko maximum au stockage.
- Chaque modification met à jour l'identité du seul établissement actif.
- Le téléchargement et la suppression sont réservés aux détenteurs de `school.settings.write` et aux propriétaires autorisés.

## Sécurité

Les fichiers sont stockés dans une table privée, sans lien public ni accès anonyme. Chaque lecture est protégée par la session de l'établissement. La mise à jour utilise une version de ligne, des limites de taille, des signatures de type image, un journal d'audit et des réponses sans cache.

Le composant d'identité est utilisé par le tableau de bord connecté et le `PageHeader` commun aux modules PC. La vue mobile conserve le logo YEM et une présentation compacte de l'école ; son design spécifique sera traité séparément.

## Vérifications

`npm test`, `npm run build`, `python backend/manage.py check`,
`python backend/manage.py makemigrations --check --dry-run`,
`python backend/manage.py test institutions.test_school_branding`.

Aucune importation d'images réelles n'est faite automatiquement. Pour une école fictive, l'administrateur peut choisir un logo et une bannière de démonstration.

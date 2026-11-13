# YEM — Espace professeur : PWA et profil synchronisé

## Principe
Les quatre maquettes mobiles validées servent de référence fonctionnelle (accueil, notes, moyennes, appel).
**L'interface réelle conserve le thème YEM**, ses composants et ses droits existants.
Le professeur utilise la PWA YEM commune (manifest et service worker déjà présents). Elle ne crée pas une
nouvelle base de données ni un APK séparé. Les données privées ne sont pas conservées hors ligne.

## Synchronisation des profils
- Un seul `StaffRecord` officiel par école et compte, créé par la direction.
- `StaffProfile` est une extension 1:1 de cette fiche (présentation libre et portrait privé).
- Le professeur peut modifier **sa propre** présentation et sa photo, pas son identité officielle, sa
  fonction, son matricule, son statut ni ses affectations.
- Le module Personnel montre la même photo via le même identifiant de fiche ; les responsables autorisés
  peuvent lire le portrait, sans pouvoir le changer depuis cet endpoint.
- Aucune photo de personnel publiée en URL publique : API privée et contrôle d'accès à chaque lecture,
  avec `Cache-Control: private, no-store`. Table PostgreSQL protégée contre les rôles Data API.
- Les fonctionnalités de notes et d'appel réutilisent les modules existants et leurs vérifications
  d'affectation/permissions.

## API
- `GET/PATCH /api/v1/schools/{school}/staff/me/profile` : lecture et modification de la présentation,
  avec révision optimiste ; exige une fiche active liée au compte.
- `GET/POST/DELETE /api/v1/schools/{school}/staff/{staff}/photo` : lecture pour soi-même
  ou personnel autorisé ; écriture pour soi-même uniquement ; JPG/PNG, maximum 350 Ko.
- La liste `GET .../staff` renvoie `photo_url` lorsqu'une photo existe.

## Dépendances avec les autres travaux
La PR #102 (fiches professionnelles RH) est encore distincte. Lors de sa fusion, afficher le même
`photo_url` dans sa vue de dossier professionnel sans recréer d'image ni de modèle parallèle.
La migration de cette branche porte le numéro 0049, après 0048 sur main au 13/11/2026.
Si d'autres migrations sont fusionnées entre-temps, ajuster les dépendances et résoudre
les branches de migrations avant le déploiement.

## Contrôles
Django : propriété du profil, CSRF, droits, école étrangère, compte révoqué, changement de
photo, contrôle de taille, conflit de révision. Frontend : tests et build de la PR.

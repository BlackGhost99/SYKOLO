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

## Écrans mobiles intégrés (seconde étape)
- L'espace professeur sur téléphone (< 761 px) s'ouvre sur une navigation YEM native : Accueil,
  Notes, Moyennes, Appel, Profil ; l'espace bureau reste inchangé.
- Notes : choix de classe et matière issus **exclusivement** des cours attribués au professeur,
  création d'évaluations avec barème configuré, puis sauvegarde groupée des notes.
- Nouveau `POST .../assessments/{id}/grades/batch` : lot de 1 à 100 notes, validation d'appartenance
  à la classe, révisions optimistes et transaction atomique (tout ou rien). Aucune publication implicite.
- Moyennes : nouveau `GET .../courses/{id}/averages?period={uuid}`, protégé comme un cours.
  Les résultats sont **provisoires**, pondérés par les coefficients des évaluations actives,
  normalisés via les pourcentages calculés dans YEM à partir des barèmes capturés.
  Les notes manquantes sont exclues de la moyenne (pas traitées comme zéro).
  Une note en lettres ou par compétence n'est jamais convertie manuellement côté client.
  Le résultat sur /20 est une échelle d'affichage du suivi uniquement, pas la note officielle du bulletin.
- Appel : réutilisation de l'API de présences, affectation vérifiée par établissement/classe,
  choix des statuts réellement paramétrés, action de marquage des élèves non renseignés,
  sauvegarde de 1 à 100 présences (transaction atomique existante), historique et motif obligatoire
  des corrections ; aucun pouvoir de clôture ni de justification RH conféré au professeur.
- Les données d'élèves restent privées et ne sont jamais mises en cache hors ligne par la PWA.
- En cas de rôle personnalisé, le contrôle des permissions API reste la source d'autorité.
- Tests frontend mobile : saisie groupée, moyenne provisoire, catégories d'appel, navigation.

# YEM — M2.7 : affectation aux divisions et gestion des capacités

Cette étape utilise les inscriptions `Enrollment` déjà créées : elle ne crée
**ni un deuxième dossier élève, ni une deuxième inscription, ni un nouveau
matricule**. L'admission et le paiement obligatoire restent du ressort de
M2.4 à M2.6. L'affectation M2.7 porte sur un **changement de division**
au sein de l'année, du niveau et de la série existants.

## API

`GET /api/v1/schools/{school}/enrollments/{id}/assignment` : liste les
divisions ouvertes du même établissement, année, niveau et série, avec la
capacité, le nombre d'élèves inscrits et les places restantes. Renvoie
`read_only: true` pour les années clôturées, les inscriptions ou dossiers
inactifs. L'information de places restantes est indicative : elle est
revérifiée lors de l'écriture.

`POST /api/v1/schools/{school}/enrollments/{id}/assignment` :
- `{ "revision": 1, "mode": "manual", "classroom": "<uuid>", "reason": "Répartition pédagogique" }`
- `{ "revision": 1, "mode": "automatic", "reason": "Équilibrage des divisions" }`

La répartition automatique choisit, parmi les **autres** divisions éligibles,
celle qui compte le moins d'inscrits (à égalité, tri stable par nom puis UUID).
Il s'agit d'une redistribution d'un inscrit existant, pas d'un déplacement
automatique de toute une classe. Si aucune autre division n'a de place,
l'affectation est refusée.

## Garanties

- `school.students.manage` obligatoire pour consulter les choix et agir.
  L'isolation par établissement est vérifiée avant toute opération.
- Verrou `School`, puis `Enrollment` et les classes candidates pour
  empêcher les prises simultanées de la dernière place. Vérification de la
  capacité réelle dans la même transaction, et révision optimiste.
- Classe source inchangée en cas d'erreur, aucune nouvelle dette ni
  réécriture de paiement. Les barèmes financiers déjà affectés à
  l'inscription restent inchangés : tout ajustement éventuel de tarifs
  propres à une classe doit passer séparément par Finances.
- Impossible de passer silencieusement d'une classe de sixième à une
  cinquième, ou de S à A. Les classes archivées, les années clôturées et
  les dossiers inactifs sont interdits comme destinations.
- Un changement réussi conserve le même `Enrollment` et les mêmes
  matricules ; incrémente `revision`, crée un `EnrollmentEvent` append-only
  avec acteur, classe précédente, classe nouvelle, mode, motif et date,
  ainsi qu'un `SchoolAudit`.
- L'ancien `PATCH /enrollments/{id}` conserve sa compatibilité mais
  ne permet plus de contourner le niveau/la série. Les changements
  effectués par ce chemin reçoivent le mode `legacy` dans l'historique.
  Les motifs/acteurs sont visibles uniquement aux comptes habilités
  à gérer les élèves.

## Interface et recette

La fiche Élèves → Scolarité propose « Choisir une division » ou
« Répartition automatique », puis demande un motif et permet de consulter
les changements historisés. La liste de choix provient du serveur.

Contrôles ciblés :
`python backend/manage.py test institutions.test_m2_class_assignments`,
`npm test`, `npm run build`, `python backend/manage.py check`,
`makemigrations --check --dry-run`, migration et suite Django sur PostgreSQL.

Cette branche ne modifie pas la tarification M2.5 (PR #122) ni la
finalisation de l'inscription M2.6 (PR #123). Avant fusion :
vérifier la compatibilité avec leurs derniers commits et faire la recette
avec des rôles réels en environnement de test. Aucune fusion ou mise en
production automatique.

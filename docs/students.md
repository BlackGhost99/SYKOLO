# YEM Module 05 — Élèves et inscriptions

Ce module introduit un dossier élève par établissement, des contacts de responsables légaux et une inscription par élève et année scolaire. Les données personnelles restent privées : session, permissions d'école, journal de modification, isolation inter-établissements, sans publication dans le laboratoire pédagogique.

API de l'école : /api/v1/schools/{school_id}/students (GET, POST) ; /students/{uuid} (GET, PATCH) ; /students/{uuid}/guardians (GET, POST) ; /students/{uuid}/guardians/{uuid} (PATCH) ; /enrollments (GET, POST) ; /enrollments/{uuid} (GET, PATCH) ; /enrollments/{uuid}/history (GET). Les lectures nécessitent school.students.read ; l'écriture exige school.students.manage. Aucun DELETE : archivage par active=false. Les champs d'identité et les relations d'inscription sont tracés par SchoolAudit et EnrollmentEvent. Les changements exigent revision et renvoient 409 si périmés.

Une inscription est unique pour un élève par année dans une école. Le statut reste un code configurable dans de futurs réglages (pas d'énumération nationale figée). La classe doit appartenir à la même année et école ; la capacité d'accueil (si définie) est vérifiée dans une transaction. Une mutation de classe est conservée dans l'historique. Les responsables légaux ne sont pas encore automatiquement liés à des comptes utilisateurs : le portail parent et les consentements arrivent avec les modules dédiés.

Aucun fichier médical ni donnée de santé n'est stocké. Protéger l'email et téléphone des responsables ; les permissions par défaut ne donnent pas accès aux dossiers des élèves aux enseignants non affectés.

## Parcours simplifiés du secrétariat

Écrans branchés sur l'API (menu **Élèves**, **Paiements**, **Paramètres**) :

| Écran | Rôle | API |
|---|---|---|
| Élèves › Nouvel élève | Fiche de renseignement complète : identité, responsables, pièces fournies, inscription en classe et frais, en une seule transaction | `POST schools/<id>/students/register`, `GET …/students/next-code` |
| Élèves › fiche | Dossier : renseignements modifiables, responsables, pièces, parcours, transfert de classe, frais et paiements avec le moyen utilisé | `GET schools/<id>/students/<id>/dossier` |
| Élèves › Inscriptions par classe | Effectifs, places restantes, liste par classe, inscription groupée d'élèves existants, affectation des frais, export | `GET …/overview/classes`, `POST …/classes/<id>/enroll`, `POST …/classes/<id>/apply-fees` |
| Élèves › Importer Excel | Import d'une liste CSV (enregistrée depuis Excel), une fiche par ligne | `POST …/students/register` |
| Paramètres › Classes | Création de plusieurs classes d'un coup (niveau et cycle créés à la volée), capacité, archivage, nouvelle année | `POST …/academic/quick-classes` |
| Paramètres › Fiche d'inscription | Formulaire modulable propre à l'établissement | `GET/PUT schools/<id>/enrollment-form` |
| Paiements › Suivi des paiements | Payé / partiel / impayé par élève, reste à payer, moyens utilisés, répartition annuelle par moyen, export | `GET …/overview/students`, `GET …/overview/finance` |

### Fiche d'inscription modulable

Chaque établissement règle sa fiche (`EnrollmentFormConfig`, une par école, révision optimiste) ; l'écriture
demande `school.students.manage` (secrétariat ou direction).

- **Socle commun** toujours demandé : nom, prénom, responsable principal.
- **Champs du socle facultatifs** (`fields`) : date et lieu de naissance, sexe, nationalité, adresse,
  établissement précédent, téléphone / email / profession / adresse du responsable, second responsable —
  chacun `visible` et/ou `required`.
- **Questions propres** (`custom_fields`, 30 max) : texte, texte long, date, nombre, liste de choix, oui/non ;
  section élève ou responsable. Réponses stockées dans `Student.extra_fields`.
- **Pièces à fournir** (`documents`, 30 max), obligatoires ou non. Pièces cochées dans `Student.documents` ;
  les pièces obligatoires manquantes s'affichent dans le dossier et la liste par classe.

Le validateur `institutions.enrollment_form.clean_answers` est réutilisable (candidatures en ligne, etc.).
Aucune donnée médicale n'est demandée par défaut ; aucun fichier n'est téléversé (case « pièce fournie »).

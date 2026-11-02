# YEM Module 05 — Élèves et inscriptions

Ce module introduit un dossier élève par établissement, des contacts de responsables légaux et une inscription par élève et année scolaire. Les données personnelles restent privées : session, permissions d'école, journal de modification, isolation inter-établissements, sans publication dans le laboratoire pédagogique.

API de l'école : /api/v1/schools/{school_id}/students (GET, POST) ; /students/{uuid} (GET, PATCH) ; /students/{uuid}/guardians (GET, POST) ; /students/{uuid}/guardians/{uuid} (PATCH) ; /enrollments (GET, POST) ; /enrollments/{uuid} (GET, PATCH) ; /enrollments/{uuid}/history (GET). Les lectures nécessitent school.students.read ; l'écriture exige school.students.manage. Aucun DELETE : archivage par active=false. Les champs d'identité et les relations d'inscription sont tracés par SchoolAudit et EnrollmentEvent. Les changements exigent revision et renvoient 409 si périmés.

Une inscription est unique pour un élève par année dans une école. Le statut reste un code configurable dans de futurs réglages (pas d'énumération nationale figée). La classe doit appartenir à la même année et école ; la capacité d'accueil (si définie) est vérifiée dans une transaction. Une mutation de classe est conservée dans l'historique. Les responsables légaux ne sont pas encore automatiquement liés à des comptes utilisateurs : le portail parent et les consentements arrivent avec les modules dédiés.

Aucun fichier médical ni donnée de santé n'est stocké. Protéger l'email et téléphone des responsables ; les permissions par défaut ne donnent pas accès aux dossiers des élèves aux enseignants non affectés.

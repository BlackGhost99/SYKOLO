# Module 06 — Personnel scolaire et affectations

Les établissements gèrent leurs propres fiches de personnel, avec matricule unique, nom, fonction libre, date d'entrée facultative et compte utilisateur facultatif mais validé comme membre actif de l'école. La fiche est distincte du compte ; un enseignant peut être présent dans plusieurs établissements sans partager les données de ceux-ci.

Les affectations relient un membre du personnel à une classe et à une année scolaire. Leur type (duty) est un code configurable : enseignant, responsable de classe, surveillant, etc. La matière enseignée sera reliée à l'affectation par le module 07. Chaque modification est tracée dans SchoolAudit ; les relations et les dossiers ne sont jamais supprimés physiquement.

API : GET/POST /api/v1/schools/{school_id}/staff ; GET/PATCH /staff/{uuid} ; GET/POST /staff-assignments ; GET/PATCH /staff-assignments/{uuid}. Le personnel peut consulter ses propres affectations via GET /staff/me/assignments, sans accéder à l'annuaire complet si non autorisé. Les droits school.staff.read et school.staff.manage sont obligatoires pour l'administration ; le fondateur n'est pas directeur par défaut.

Le module 06 n'intègre ni paie ni contrat RH, ni gestion de présence, ni matières ou emploi du temps ; ces fonctions seront créées dans les modules prévus.

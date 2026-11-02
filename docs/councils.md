# Module 10 — YEM : délibérations scolaires et rectifications

Chaque école configure ses décisions dans le paramètre hiérarchique deliberation.decisions : une liste de dictionnaires contenant code et label, par exemple admis, maintien, rattrapage, ou tout choix institutionnel. Aucune décision ni note de passage n'est codée en dur. Les conseils sont rattachés à une classe et une période facultative. Chaque décision exige une inscription de cette classe et un bulletin publié pour la période correspondante.

Les conseils restent modifiables avant clôture. Une clôture avec révision courante et au moins une décision fige les décisions ; les actions sont auditées. Les membres sont autorisés via school.deliberations.read, school.deliberations.manage et school.deliberations.finalize. Les fondateurs ne disposent d'aucun accès pédagogique implicite.

Les bulletins publiés demeurent immuables. Les rectifications sont conservées en append-only, avec justification, auteur, copie précédente et numéro de rectificatif. La correction explicite du pourcentage d'une matière recalcule le résultat général dans un nouveau snapshot, sans modifier le bulletin original ni les notes sources. Les rectificatifs PDF portent leur numéro et le motif. Permissions distinctes school.reports.amend et school.reports.read.

Routes /api/v1/schools/{school_id} : GET/POST councils ; GET councils/{id} ; POST councils/{id}/decisions ; POST councils/{id}/close ; GET council-choices?classroom=<uuid>. GET/POST reports/{report_id}/amendments ; GET reports/{report_id}/amendments/{id} ; GET reports/{report_id}/amendments/{id}/pdf. Authentification et CSRF obligatoires, isolation inter-établissements, contrôle de version 409.

Limites : une rectification manuelle est un avenant, pas une modification du carnet de notes historique. Les doubles signatures, décisions automatiques et systèmes réglementaires nationaux ne sont pas imposés.

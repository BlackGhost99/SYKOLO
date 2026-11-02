# Module 04 — Structure académique YEM

Chaque école possède ses propres années scolaires, cycles, niveaux, filières facultatives, classes et périodes. La classe appartient à une année et à un niveau. La filière facultative appartient au même niveau. Une période appartient à une année, avec dates inclusives et sans chevauchement des périodes actives. Aucun nombre de semestres/trimestres n'est imposé.

API : GET et POST /api/v1/schools/{school_uuid}/academic/{resource}, puis GET et PATCH /api/v1/schools/{school_uuid}/academic/{resource}/{uuid}. Resource est years, cycles, levels, tracks, classes ou periods. La création exige code, name et les relations/dates pertinentes. PATCH exige revision; la version augmente de un. Les relations parent sont immuables sur PATCH. Les objets sont archivés avec active=false, sans DELETE.

Sécurité : auth, CSRF, séparation stricte par école, school.academic.read en lecture et school.academic.manage pour écrire. Les nouveaux droits des rôles standard existants non personnalisés sont distribués par migration. Les fondateurs n'obtiennent pas automatiquement ces droits.

Hors périmètre : inscriptions élèves (module 05), personnel et affectations (module 06), évaluations et bulletins (phase 3).

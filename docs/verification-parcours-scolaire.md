# Vérification d'intégration du parcours pédagogique de YEM

Scénario: `backend/institutions/test_full_journey.py`.

La vérification parcourt les véritables routes HTTP Django, avec contrôle CSRF, création d'organisation, de deux écoles et d'une direction, configuration d'un barème /20 et de décisions libres, années, cycle, niveau, classe, période, élève, responsable légal, inscription, enseignant, affectation, deux matières à coefficients distincts, cours et contrôles, saisie de notes via compte enseignant, publication des évaluations, calcul et publication d'un bulletin, PDF A4, conseil de classe, décision, clôture et rectification avec conservation de la version originale. Les tentatives de lecture d'un établissement étranger doivent être refusées.

Ce test d'intégration est exécuté par la CI Django avec PostgreSQL et la suite existante, sans créer de ressource Render et avec uniquement des données fictives. **Il ne constitue pas une recette navigateur interactive, une mise en production, un contrôle de sauvegardes, de performance ou de sécurité exhaustive.**

Pour l'exécuter : `python backend/manage.py test institutions.test_full_journey` avec les dépendances et la base de test configurées. Le workflow GitHub exécute `python backend/manage.py test pedagogy accounts institutions` et inclut automatiquement `test_full_journey.py`.

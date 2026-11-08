# Module 04 — Structure académique YEM

Chaque école possède ses propres années scolaires, cycles, niveaux, filières facultatives, classes et périodes. La classe appartient à une année et à un niveau. La filière facultative appartient au même niveau. Une période appartient à une année, avec dates inclusives et sans chevauchement des périodes actives. Aucun nombre de semestres/trimestres n'est imposé.

API : GET et POST /api/v1/schools/{school_uuid}/academic/{resource}, puis GET et PATCH /api/v1/schools/{school_uuid}/academic/{resource}/{uuid}. Resource est years, cycles, levels, tracks, classes ou periods. La création exige code, name et les relations/dates pertinentes. PATCH exige revision; la version augmente de un. Les relations parent sont immuables sur PATCH. Les objets sont archivés avec active=false, sans DELETE.

Sécurité : auth, CSRF, séparation stricte par école, school.academic.read en lecture et school.academic.manage pour écrire. Les nouveaux droits des rôles standard existants non personnalisés sont distribués par migration. Les fondateurs n'obtiennent pas automatiquement ces droits.

Hors périmètre : inscriptions élèves (module 05), personnel et affectations (module 06), évaluations et bulletins (phase 3).

## Cycle de vie et clôture définitive (sécurisée)

- Une seule année scolaire par établissement peut avoir le statut `current` (« en cours »). Les autres restent en préparation ou sont des archives clôturées.
- La préparation d'une nouvelle année copie uniquement la **structure facultative des classes** ; jamais les élèves, les notes, les recettes ou les affectations.
- L'activation `POST /academic/years/{year}/activate` impose révision et motif, vérifie les autorisations et est auditée.
- La pré-clôture `GET /academic/years/{year}/closure-review` est accessible à la direction disposant de `school.academic.manage` **et** `school.finance.read`, sans restriction à un seul cycle. Elle affiche les indicateurs annuels, les alertes et les blocages.
- La clôture `POST /academic/years/{year}/close` demande `revision`, `confirmation` (code exact d'année), `reason` (20 à 600 caractères). Elle exige une année `current` terminée et aucun blocage.
- Les blocages incluent évaluations non publiées, bulletins brouillons, conseils et séances non clos, transactions SingPay ou paiement parents en cours, caisses ou remises en attente de validation.
- La transaction enregistre un bilan JSON figé (`AcademicYearClosure`) avec empreinte SHA-256, horodatage, auteur, motif et journal d'audit, puis passe l'année à `closed` / `active=False`. Le bilan reste accessible dans l'interface.
- Sur PostgreSQL, la migration 0037 installe des **triggers sur les tables rattachées à une année**, qui bloquent les écritures sur une année clôturée, y compris les mises à jour SQL directes et les callbacks financiers. Les caisses et transferts sont contrôlés par date. La migration 0039 protège la preuve de clôture contre UPDATE/DELETE.
- Les dossiers permanents (élèves, comptes, profils de personnel, structure générale) ne sont pas figés, car ils continuent à vivre d'une année à l'autre. Les rapports publiés gardent leurs instantanés.

### Condition de mise en production

La clôture réelle est **désactivée par défaut** : `YEM_YEAR_CLOSURE_ENABLED=false`. L'API de clôture refuse les demandes (503) sur SQLite ou tant que l'option n'est pas explicitement activée. **N'activer cette option qu'après sauvegarde et restauration testées de la base de production**, revue des flux asynchrones de paiement, validation PostgreSQL des migrations/triggers et essais de lecture seule multi-modules. Ne pas considérer un exercice de restauration sur données synthétiques comme une sauvegarde de production.

L'interface de revue peut être exposée indépendamment de la clôture. Une correction officielle après clôture requiert un futur circuit exceptionnel traçable : ne jamais modifier le procès-verbal ni réouvrir une année automatiquement.

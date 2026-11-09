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


## Automatisation des niveaux et classes de tous les cycles

Pour un établissement ouvrant le cycle `prescolaire` (maternelle seule ou complexe scolaire), YEM propose **Crèche**, **Petite section (3 ans)**, **Moyenne section (4 ans)** et **Grande section (5 ans)**. Les âges sont des intitulés indicatifs, pas un critère de rejet d'inscription.

- À la création de l'établissement par la plateforme, les quatre **niveaux** sont préparés. Une classe doit obligatoirement appartenir à une année scolaire ; YEM n'invente donc pas les dates d'année.
- Lors de la création d'une année scolaire, YEM prépare automatiquement une classe par niveau : Crèche A, Petite section A, Moyenne section A et Grande section A. La préparation d'une année avec copie explicite des classes précédentes conserve plutôt la structure choisie par la direction.
- Pour les établissements déjà créés, le bouton **Compléter les classes standards** (`POST /schools/{id}/academic/preschool-standard-classes`, avec `{"year":"uuid"}`) ajoute uniquement les niveaux/classes manquants. Il est sans doublon et ne remplace jamais une classe renommée ou archivée.
- Chaque classe reste renommable et archivable dans **Paramètres → Classes**. La fonction **Dupliquer** (`POST /schools/{id}/academic/classes/{id}/clone`, avec `{"name":"Petite section B"}`, nom facultatif) reprend uniquement le niveau, la filière, l'année et la capacité. Aucun élève, professeur, cours, emploi du temps, tarif, évaluation ou bulletin n'est cloné.
- Les deux opérations vérifient l'établissement, l'année non clôturée, le périmètre de délégation de cycle et les noms uniques ; elles sont transactionnelles et auditées.
- L'option existante **Générer les classes** permet toujours de créer plusieurs divisions A/B/C ou 1/2/3, avec renommage avant enregistrement.

Aucune migration ni modification rétroactive des données n'est requise par cette automatisation.

### Catalogue multi-cycles et usage quotidien

YEM généralise le catalogue aux types d'établissements effectivement ouverts :

| Cycle ouvert | Niveaux préenregistrés | Divisions initiales |
|---|---|---|
| Préscolaire | Crèche, Petite section, Moyenne section, Grande section | Crèche A, Petite section A, Moyenne section A, Grande section A |
| Primaire | 1re, 2e, 3e, 4e, 5e année | 1re année A…5e année A |
| Collège | 6e, 5e, 4e, 3e | 6e A…3e A |
| Lycée général | Seconde, Première, Terminale | Seconde A, Première A, Terminale A |
| Lycée technique | Seconde, Première, Terminale | Seconde technique A, Première technique A, Terminale technique A |

Les établissements mixtes cumulent **uniquement les cycles activés**. Les subdivisions A/B/C sont des **divisions de classe**, à ne pas confondre avec les séries ou spécialités ; pour les lycées général et technique, la filière n'est pas présumée.

- À la création de l'établissement par la plateforme, le catalogue des **niveaux** est préenregistré sans année fictive. Une fois l'année créée, YEM génère une division A pour chaque niveau, avec les noms conservés si le niveau a été personnalisé.
- Dans **Paramètres → Classes**, le bouton unique **Compléter les classes standards** appelle `POST /schools/{id}/academic/standard-classes` avec le JSON `{"year":"uuid"}`. Il complète seulement les niveaux des cycles que l'utilisateur a le droit de gérer. L'ancien endpoint maternel reste fonctionnel.
- Les niveaux et classes déjà présents, y compris renommés ou archivés, ne sont ni remplacés ni réactivés. Les classes sont uniques par nom et par année ; les opérations sont atomiques et auditées.
- **Dupliquer** reprend uniquement la division (niveau, année, filière, capacité), et jamais les élèves, emplois du temps, évaluations, personnel ni finance. Les classes A/B/C et les noms libres restent modifiables.
- Lorsqu'une nouvelle année **copie** explicitement les classes de l'année précédente, YEM respecte la structure copiée et n'ajoute pas automatiquement d'autres divisions ; les niveaux manquants sont toujours ajoutables volontairement avec le bouton de complément.
- Aucun schéma ou migration supplémentaire n'est nécessaire et **aucune classe ancienne n'est modifiée rétroactivement**.

## Ouverture explicite des séries et archivage réversible (novembre 2026)

Le cycle **lycée général** n'ouvre plus automatiquement « Seconde A », « Première A » ou « Terminale A » lorsque YEM crée une année scolaire ou complète les classes standards. Le même principe s'applique au **lycée technique** : éviter les classes fantômes. Les niveaux Seconde, Première et Terminale restent proposés, sans série obligatoire.

### Catalogue et choix de l'établissement

- **Général (source : annuaire statistique 2020/2021 du Gabon)** : Seconde **LE, S** ; Première **A1, A2, B, S** ; Terminale **A1, A2, B, C, D**. Les intitulés locaux non listés (A1 en Seconde, S1/S2/SU, etc.) sont acceptés si l'établissement les utilise.
- **Technique** : suggestions **ACA, ACC, ACG, CG, CFE, F1, F1C, F1D, F2, F3, F4, MI, MSI, SI, GSI, RHC, M, ERE, BIOT, SPCL**. Les séries documentées par BacTech ne constituent pas une liste réglementaire prouvant leur existence à chaque niveau. **ACG** est une appellation locale rapportée ; l'établissement vérifie son libellé.
- Les suggestions ne créent **ni série active ni classe**. La direction choisit un niveau, saisit ou sélectionne une série, prépare de 1 à 30 **noms éditables** (Seconde S1, S2, SU, Première ACC1…), puis confirme. Une `AcademicTrack` propre à ce niveau et cette école est créée au besoin et rattachée aux seules nouvelles `AcademicClass` de l'année choisie, sans élèves, matières ou paiements.
- Endpoint : `POST /schools/{school_id}/academic/series-classes` avec `{"year":"uuid","level":"uuid","series":"S","names":["Seconde S1","Seconde SU"],"capacity":35}`. Noms libres et uniques par année, codes stables, périmètre de cycle, transaction et audit.
- Aucun ancien nom de classe n'est modifié automatiquement, même les anciennes « Seconde A ». L'établissement peut les archiver depuis **Paramètres → Classes**.

### Archivage, retour et protection du catalogue parent

- Chaque classe possède un booléen `active`. Boutons **Archiver** / **Réactiver** en gestion des classes, avec confirmation. L'archive ne supprime pas les dossiers ni les inscriptions ou bulletins existants et ne peut pas être modifiée dans une année clôturée.
- Le catalogue parent masque les classes inactives, ainsi que celles liées à un cycle, un niveau ou une série inactive. La création directe de candidature et les inscriptions côté serveur refusent ces mêmes cas.
- **Réouvrir dans cette année** permet de **reprendre une classe archivée d'une année antérieure** via `POST /schools/{school_id}/academic/classes/{class_id}/carry-forward` avec `{"year":"uuid"}`. Il crée une **nouvelle** division active (même niveau, série, nom et capacité) dans une année postérieure modifiable, tandis que l'archive et ses inscriptions restent intactes. Un doublon de nom est refusé. Il ne copie ni élèves, ni notes, ni paiements, ni emplois du temps.
- Une classe inactive n'est pas reportée automatiquement lors de la préparation d'une nouvelle année ; sa réouverture est **un choix explicite** de la direction. Les classes actives sont copiées par le mode de reprise annuelle existant.
- Les droits de gestion sont limités au cycle effectivement délégué. Aucune migration du schéma n'est requise.

Sources : annuaire statistique du secteur Éducation/Formation du Gabon (publié en 2023, description scolaire 2020–2021), `https://instatgabon.org/uploads/folder_1/RGOE/Annuaire_2020-2021_31_10_2023_.pdf` ; catalogue BacTech `https://bactechgabon.com/affiche_listinscritserie.php` ; Lycée technique de Ntoum (appellations locales ACA/ACC, ACG).

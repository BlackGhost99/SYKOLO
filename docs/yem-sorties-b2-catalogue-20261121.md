# YEM — Sorties B2b : catalogue configurable des dépenses

**Périmètre exclusif :** dépenses. Aucun frais scolaire, recette ou encaissement n'est modifié.

## Fonctionnement
- Catalogue **propre à chaque établissement**, deux niveaux (catégorie et sous-catégorie).
- Chaque élément possède un code permanent unique par établissement, un libellé personnalisable, un pôle suggéré facultatif, un état actif/archivé, une révision et une date de création.
- La catégorisation par **nature de dépense** est indépendante des **cinq pôles d'activité** et de la catégorie libre du budget historique.
- L'utilisateur avec `school.operating.read` peut consulter. Celui avec `school.operating.manage` peut créer, renommer et archiver. Aucune suppression destructrice.
- Code et parent immuables : on renomme ou archive, sans briser les références anciennes.
- Une sous-catégorie doit appartenir à une catégorie racine du même établissement. Pas de troisième niveau. On archive les enfants actifs avant leur parent.
- Une nouvelle demande sélectionne une catégorie active. Une sous-catégorie est facultative.
- Une suggestion de pôle ne remplace jamais la sélection explicite de l'activité.
- Les **libellés des catégories sont copiés dans l'opération à sa création**. Renommer ensuite une catégorie ne réécrit donc pas les libellés de dépenses historiques. Les projets peuvent être corrigés avant approbation sous contrôle de révision.
- Anciennes opérations : références NULL et libellés vides → affichage « À classer (historique) ». Aucun recalcul ni requalification automatique.
- Un projet ne peut être approuvé sans catégorie ou avec une catégorie/sous-catégorie archivée.
- Un paiement enregistré ne fait **pas** sortir de l'argent : le registre demeure déclaratif.

## API privée
Préfixe `/api/v1/schools/<school_id>/operating/` :
- `GET/POST categories`
- `GET/PATCH categories/<category_id>`
- `POST expenses` exige `category_ref`, accepte `subcategory_ref` facultatif, en plus de `activity_pole`.
- `GET expenses` et `GET expenses/<id>` renvoient les identifiants et libellés de catégorie **figés**.
- `PATCH expenses/<id>` peut réaffecter la catégorie tant que la dépense est à l'état projet.
- `GET summary` n'a pas de changement de calcul dans cette PR.

### Permissions et sécurité
- Vérification du rôle et du tenant dans Django, plus CSRF pour les écritures.
- `select_for_update` et `revision` sur les modifications, journal `SchoolAudit` sans détail salarial.
- `PROTECT` sur les références ; table de catalogue sous RLS PostgreSQL, révocation des accès directs `PUBLIC`, `anon` et `authenticated`.
- Aucune donnée réelle n'est importée automatiquement.

## PR et coordination
- Ce lot est **empilé sur B2a #257**, elle-même dépendante de **B1a #255**.
- Seul fichier partagé modifié : `backend/institutions/urls.py`, avec l'import du module de catalogue et **deux routes strictement `/operating/categories`**. Aucun endpoint `/finance` ni `/entries` n'est modifié.
- Les PR A **#253 et #256** modifient aussi `urls.py` mais dans d'autres blocs : rebase/contrôle de hunk obligatoire au moment de la fusion.
- La migration `0083_operating_expense_catalog` dépend de `0082_operating_expense_classification`. Revalider le graphe Django avant fusion et après toute autre migration.
- Les budgets continuent provisoirement à utiliser le champ historique libre `category`. Leur raccordement définitif au catalogue sera une extension ultérieure : **ne pas prétendre qu'il est déjà fait**.

## Validation avant production
1. Tests `institutions.test_operating`, dont catalogues multi-écoles, droits, hiérarchie, archivage, snapshots et projets historiques.
2. Tests `OperatingPanel.test.jsx`, compilation React, `manage.py check` et `makemigrations --check`.
3. Tests PostgreSQL et contrôles RLS.
4. Vérification de la compatibilité des routes de #253/#256 et des nouvelles migrations.
5. Sauvegarde **réelle** chiffrée de Supabase + restauration isolée avant toute migration en production.
6. Fusion uniquement après CI verte, sans paiement réel ni données fictives en production.

**Statut à la création :** correctifs enregistrés sur branche de travail ; tests non exécutés localement ; aucun déploiement.

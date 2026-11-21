# YEM — Sorties B3c : file de traitement des demandes

## Objectif
Présenter aux responsables une file de **dépenses et demandes de sortie** filtrable par état, avec navigation par lots et sans chiffres incomplets. Aucun développement d'entrée ou modification de l'encaissement scolaire.

## Contrat backend — dépenses uniquement
`GET /api/v1/schools/{school_id}/operating/expenses` accepte :
- `year` (année scolaire dans l'établissement), `activity_pole` (pôle),
- `workflow_state` : draft, submitted, rejected, approved,
- `limit` entier de 1 à 100 (défaut : 50), `offset` entier de 0 à 1 000 000.

Réponse :
- `expenses` : lignes paginées et triées par date, création et identifiant ;
- `total` : nombre **réel et exhaustif** correspondant au filtre d'état ;
- `has_more`, `offset`, `limit` : navigation explicite ;
- `workflow_counts` : compteurs **exhaustifs** pour l'école/année/pôle sélectionnés, calculés **avant** le filtre d'état.

La séparation entre engagements approuvés et simples demandes reste inchangée : les KPI budgétaires ne comprennent pas les brouillons/soumissions/refus, et les paiements déclarés conservent leur propre registre.

## Interface
- Filtres cliquables : Toutes, Brouillon, En attente de validation, Refusée, Autorisée.
- Filtre par pôle d'activité et réinitialisation de la pagination au changement de filtre.
- Boutons Page précédente / Page suivante et nombre total de dossiers ; fenêtre de 30 résultats par page.
- Les demandes approuvées puis partiellement ou totalement réglées restent dans l'état de workflow **approved** ; leurs statuts de règlement restent visibles séparément dans chaque dossier.
- Le dossier détaillé et l'historique de validation proviennent du module B3b sans toucher aux recettes.

## Sécurité / tests
- Les filtres sont obligatoirement appliqués au périmètre `school` et `year` côté serveur. Les calculs sont effectués après le filtrage école ; aucun accès d'un autre établissement.
- Cas de tests : trois statuts, compteurs, pagination, données distinctes, limites invalides, rôle enseignant et compte externe refusés.
- Test d'interface : choix d'état, passage en page suivante et vérification des paramètres d'API, sans accès aux routes d'entrées.

## Git et déploiement
- Dépendance sur B3b **#264**, lui-même sur #261 / #258 / #257 / #255.
- Aucun fichier d'entrées, aucune migration et aucun routeur partagé modifié dans ce lot.
- Tester `institutions.test_operating`, `OperatingPanel.test.jsx`, migrations et exécution PostgreSQL après rebase.
- Aucune fusion/deploiement Supabase/Render tant que les CI et la recette réelle ne sont pas validées. Les tests ne sont pas attestés comme exécutés par cette livraison.

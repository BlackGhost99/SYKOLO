# YEM — Encaissements groupés et contrôle quotidien des espèces

Ce module s'adresse aux écoles privées du Gabon, maternelles, écoles primaires, collèges, lycées ou groupes scolaires. Le thème vert et le logo de YEM sont conservés.

## Encaissement groupé

Le comptable ou l'économe autorisé peut sélectionner plusieurs frais d'un seul élève. L'enregistrement est une seule transaction SQL avec une seule clé anti-doublon, sans paiement partiel en cas d'erreur. La réponse inclut un lien vers un reçu PDF récapitulatif. Les anciens paiements individuels ne sont ni supprimés ni convertis.

API POST /api/v1/schools/{id}/finance/batches : inscription UUID, lignes avec charge et montant décimal, méthode, référence, date et clé idempotente UUID. Entre une et trente lignes, même élève, même école, même devise, soldes disponibles. Un nouvel essai identique rend le même reçu. Une nouvelle opération avec une clé déjà utilisée et un contenu différent est refusée.

API GET /api/v1/schools/{id}/finance/batches/{id} : détail et paiements associés.

API GET /api/v1/schools/{id}/finance/batches/{id}/receipt : reçu PDF A4, sans cache public, tenant compte des annulations éventuelles.

Les modes Airtel Money, Moov Money, espèces et virements restent des déclarations d'encaissement manuel : aucune demande de débit ni confirmation d'opérateur n'est réalisée.

## Contrôle de caisse journalier

L'agent disposant du droit de réception déclare, pour sa journée et sa devise, le montant d'espèces physiquement compté. Le serveur calcule le montant attendu à partir des encaissements en espèces de ce même agent, de cette date et de cette devise, hors annulations. Une différence exige une justification.

API GET/POST /api/v1/schools/{id}/finance/cash/closings : déclarations de clôture, comptage, écart, statut et ajustements postérieurs.

API POST /api/v1/schools/{id}/finance/cash/closings/{id}/approve : vérification par une AUTRE personne disposant du droit d'annulation financière. L'autovalidation est interdite, même pour une direction ayant tous les droits. Pour une école avec un seul agent, la clôture peut être soumise mais nécessite la nomination d'un autre contrôleur pour être approuvée.

Après la déclaration, les nouveaux encaissements en espèces du même caissier, date et devise sont bloqués. Les nouvelles annulations restent visibles comme ajustements postérieurs à la clôture, sans modifier rétroactivement le montant figé.

## Limitations et déploiement

Ce module ne réalise pas le rapprochement bancaire, le remboursement effectif, la gestion de paie, de stocks, la comptabilité SYSCOHADA ni les dépenses. Une véritable passerelle de paiement Mobile Money devra disposer d'une vérification serveur indépendante et d'un rapprochement sécurisé avant d'être activée.

La branche est construite sur le main après fusion des PR parents et organigramme. Migration 0019_finance_payment_batches, après 0018_school_appointments.

La PR #26 modifie également LiveScreens.jsx. À sa fusion, réconcilier cette interface financière avec les écrans d'inscription. Ne pas fusionner ni déployer avant les tests PostgreSQL et React, les contrôles d'isolation et une recette avec de fausses opérations de caisse.

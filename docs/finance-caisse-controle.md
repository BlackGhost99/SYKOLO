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

La branche est construite sur le main après fusion des PR parents et organigramme. Migration 0020_finance_payment_batches, après 0019_parent_payments (issue de la PR #38).

La PR #26 modifie également LiveScreens.jsx. À sa fusion, réconcilier cette interface financière avec les écrans d'inscription. Ne pas écraser les travaux des autres conversations. Ne pas fusionner ni déployer avant les tests PostgreSQL et React, les contrôles d'isolation et une recette avec de fausses opérations de caisse.


## Séparation financière (suite de #41)

La direction lit les finances et contrôle les clôtures, sans encaisser, modifier les tarifs ni annuler par défaut. Le comptable contrôle et peut annuler l'encaissement d'un autre agent. L'économe encaisse, déclare sa caisse et documente les remises/dépôts. Le rôle tarification gère les frais. Les rôles supplémentaires d'un membre cumulent ses habilitations ; ils ne suppriment jamais l'interdiction d'auto-validation. Le propriétaire peut attribuer ces fonctions ; les autres gestionnaires ne peuvent attribuer des droits qu'ils ne possèdent pas.

Les migrations 0021 puis 0022 prolongent 0020 sans modifier les migrations déjà publiées. 0022 retire les anciens droits financiers excessifs de direction/comptabilité et crée les nouveaux rôles sans écraser un rôle personnalisé existant. Les affectations de caisse/tarification doivent être attribuées explicitement par le propriétaire après migration. Le retour arrière du schéma ne rétablit pas les anciens droits excessifs.

Les vues élèves, caisse, relances et tableau de bord permettent de choisir la devise et l'année. Les encaissements du tableau de bord suivent l'année des frais, y compris les inscriptions archivées. Le tableau de synthèse de la clôture couvre tous les exercices ; il ne mélange jamais les devises.

Après déclaration d'une caisse, les nouvelles écritures espèces et les annulations de cette caisse sont bloquées pour préserver son instantané. Une clôture dont le journal aurait changé ne peut pas être approuvée. Toute correction après clôture exige pour l'instant un traitement supervisé distinct : il n'existe pas de réouverture automatique.

Une remise ne peut dépasser le montant compté d'une clôture validée. Un dépôt ne peut dépasser les remises déjà contrôlées. Les mouvements en attente réservent les fonds pour empêcher leur double affectation ; les écritures sont sérialisées sur la clôture. Référence, destinataire/banque et date sont obligatoires. Chaque justificatif est contrôlé par un autre compte habilité, même en cas de cumul de fonctions. Ces écritures documentent un mouvement physique déclaré : elles ne constituent pas une confirmation bancaire automatique. Les mouvements sont conservés et ne disposent pas d'une suppression automatique.

Les PR #26 et #33 sont anciennes et comportent des migrations parallèles : ne pas les fusionner sans les réconcilier avec la chaîne actuelle. La présence d'une correction dans GitHub ne prouve pas son déploiement Render ; comparer séparément le SHA du déploiement live.

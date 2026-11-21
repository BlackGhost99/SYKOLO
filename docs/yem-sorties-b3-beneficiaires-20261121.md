# YEM — Sorties B3a : bénéficiaires non commerciaux

## Périmètre
Ce lot concerne uniquement les demandes de **dépenses de fonctionnement** du module `/operating/`. Il ne modifie ni les frais, ni les encaissements, ni les fiches de paie et ne déclenche pas de transfert bancaire ou Mobile Money.

### Objet
Éviter la création de faux « fournisseurs » pour enregistrer une sortie en faveur :
- d'une administration publique ;
- d'un membre du personnel pour un remboursement/indemnité **hors paie** ;
- d'un parent/responsable légal (enregistrement déclaratif seulement, **pas** un remboursement automatique des frais de scolarité) ;
- d'une personne physique, d'une association/organisation ou d'un autre bénéficiaire ;
- d'un fournisseur/prestataire réel (parcours inchangé).

## Données / migrations
La migration additive `0084_operating_expense_beneficiaries` dépend de `0083_operating_expense_catalog` :
- `supplier` devient nullable (un fournisseur demeure obligatoire pour le type `supplier`) ;
- `beneficiary_type` vaut `supplier` pour **toutes les anciennes lignes** ;
- `beneficiary_name` et `beneficiary_reference` restent facultatifs au niveau SQL pour préserver l'historique ;
- les lignes existantes conservent leur `supplier_id`, sans réécriture des paiements ni des montants ;
- les nouvelles demandes non commerciales exigent une désignation explicite du bénéficiaire ;
- le nom du fournisseur est copié au moment de la création ou de la modification d'un brouillon, avec repli de lecture sur la fiche pour les anciens enregistrements.

Aucune migration de données ne fabrique de noms ou de fournisseurs.

## API et validations
- `POST /api/v1/schools/{school}/operating/expenses` : le type `supplier` requiert un fournisseur propre à l'école ; tout autre type exige un nom et interdit un fournisseur associé.
- `PATCH /.../operating/expenses/{id}` : changement de bénéficiaire seulement pour un brouillon, sous contrôle de `revision`, permissions et `transaction.atomic()`.
- Les opérations approuvées gardent leur bénéficiaire. La séparation préparateur/approbateur/économe, le contrôle de budget et la clé anti-doublon de paiement sont conservés.
- `GET` : champs `beneficiary_type`, `beneficiary_name`, `beneficiary_reference`, `supplier` nullable et `supplier_name` rétrocompatible.
- Référence interne facultative ; ne pas y enregistrer de pièces d'identité, comptes bancaires, secrets ou coordonnées privées inutiles.
- Les salaires et salaires nets restent **exclusivement** dans `/payroll/`, pour éviter le double comptage.
- Un remboursement de frais de scolarité ne doit pas être considéré exécuté ni réconcilié par cette seule écriture : lien à la transaction d'origine et parcours de remboursement sécurisé à développer avec coordination du chantier A.
- La preuve d'un virement sortant réel exige une attestation externe spécifique ; les règlements de ce module restent **déclaratifs**.

## Contrôles avant fusion
- Tester le maintien des dépenses fournisseurs existantes (création et lecture), les changements de bénéficiaire non commerciaux, les approbations et les paiements partiels.
- Refuser les faux fournisseurs d'autres établissements et les incohérences type/nom/supplier.
- Tester la confidentialité/rôles ; vérification du `SchoolAudit` et des limites de l'exercice.
- Tester PostgreSQL + SQLite, Django, Vitest, build et `makemigrations --check`.
- Contrôler le graphe des migrations après chaque PR parallèle.
- Avant toute migration de production : sauvegarde réelle chiffrée de Supabase avec restauration vérifiée dans une base hors production.

## Conflits Git
Cette PR est empilée sur la PR sorties #258, elle-même sur #257 puis #255. Elle modifie uniquement les fichiers `operating_*`, le test des dépenses, `OperatingPanel` et une nouvelle migration `0084`. Elle ne touche pas `entry_income.py`, `finance_views.py`, `finance_models.py`, `FinancePanel.jsx`, `urls.py` ou les modules d'encaissement.

**Statut à la rédaction** : code sur branche, tests runtime à confirmer, aucune fusion ni déploiement.

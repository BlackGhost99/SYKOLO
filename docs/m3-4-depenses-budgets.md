# YEM M3.4 — Fournisseurs, dépenses et budgets de fonctionnement

## Périmètre

M3.4 permet aux établissements de gérer les **charges hors rémunérations et hors scolarité** : entretien, électricité, consommables, travaux, prestations, achats, sans liste de catégories codée en dur.

Tout reste associé au **même établissement** et à **l'année scolaire** sélectionnée, avec devises distinctes.

**Important :** le registre constate des engagements budgétaires et des versements déclarés ; il ne constitue ni une comptabilité générale SYSCOHADA, ni une intégration bancaire, ni une caisse de sortie certifiée. Les montants n'ont aucun effet sur les soldes des élèves ou les fiches de paie.

## Processus

1. La comptabilité enregistre un fournisseur (nom et contacts facultatifs, sans coordonnées bancaires). Une désactivation conserve l'historique.
2. Un responsable habilité propose un budget par catégorie, année et devise. Le budget est modifiable uniquement à l'état de projet.
3. **Un autre acteur** approuve l'enveloppe ; elle devient non modifiable. Chaque catégorie+devise+année possède une enveloppe unique.
4. La comptabilité prépare une dépense dans cette enveloppe, avec fournisseur, libellé, date et **référence de facture/devis** obligatoire. Tant que la dépense est en projet, elle est modifiable par un habilité.
5. Un second acteur approuve la dépense. La transaction PostgreSQL verrouille l'enveloppe et refuse de dépasser le disponible même en cas de validations simultanées.
6. L'économe enregistre un règlement **déjà exécuté** (espèces, virement déclaré, Mobile Money déclaré, autre), partiel ou intégral, avec référence, date et UUID d'idempotence.
7. Une annulation exige un **autre acteur**, un motif explicite et laisse subsister le versement initial dans l'historique.

### Indicateurs de budget

- **Plafond** : enveloppe approuvée.
- **Engagé** : somme des dépenses approuvées, payées ou non.
- **Déclaré payé** : somme des règlements enregistrés non annulés.
- **Disponible** : plafond moins engagé. Annuler un règlement ne libère pas le budget, car la dette fournisseur demeure.
- **Restant dû** : total engagé moins déclaré payé, séparé par catégorie et devise.

Les propositions non validées ne comptent pas dans les engagements. Les budgets non validés ne comptent pas comme ressources disponibles.

## Matrice des droits

| Permission | Usage |
|---|---|
| `school.operating.read` | Voir fournisseurs, budgets et dépenses |
| `school.operating.manage` | Créer/corriger les fournisseurs, budgets projets et dépenses projets |
| `school.operating.approve` | Approuver indépendamment budgets et demandes |
| `school.operating.pay` | Déclarer les règlements effectués avec justificatifs |
| `school.operating.reverse` | Annuler le règlement d'un autre agent |

Rôles standard privés : comptabilité = lecture/préparation/annulation ; direction = lecture/validation ; économe = lecture/règlements. Aucun accès accordé automatiquement aux parents, élèves, enseignants ou secrétariat. Les rôles configurables doivent conserver le principe de double contrôle.

Contrôles : établissement isolé, année clôturée verrouillée pour les mutations, anti-doublon, versionnage des brouillons, plafond budgétaire, aucune somme comptable écrite dans le journal général `SchoolAudit.details`, en-têtes no-store, tables PostgreSQL RLS avec `REVOKE` pour les rôles `anon`/`authenticated`.

## API

Préfixe `/api/v1/schools/{school_id}/operating/` :

- `GET/POST suppliers`, `GET/PATCH suppliers/{id}`
- `GET/POST budgets`, `GET/PATCH budgets/{id}`, `POST budgets/{id}/approve`
- `GET/POST expenses`, `GET/PATCH expenses/{id}`, `POST expenses/{id}/approve`
- `POST expenses/{id}/payments`, `POST payments/{id}/void`
- `GET summary?year={uuid}`

Le champ `invoice_reference` désigne un justificatif conservé par l'établissement ; **cette version ne charge pas encore les documents PDF/images**. Le module de pièces jointes privées est une extension distincte à concevoir, avec antivirus, stockage sécurisé et permissions de téléchargement.

## Recette et politique de livraison

- Tests : `institutions.test_operating`, suite `pedagogy accounts institutions`, tests React, `makemigrations --check`, migration `0052_operating_budget_expenses`, Docker + Postgres.
- Aucun jeu de données financier de test injecté en production.
- **Ne pas déployer automatiquement** les migrations `0051` / `0052` sans sauvegarde **réelle** et chiffrée de Supabase YEM et restauration vérifiée sur un environnement indépendant.
- La sauvegarde **synthétique** de CI n'est pas une preuve de restauration du système réel.
- Le rapprochement bancaire, l'édition de factures, les pièces justificatives binaires, les dépenses dans la caisse du jour et les états comptables réglementaires restent à traiter ensuite.

Raccordement visuel : nouvelle section **Dépenses et budgets**, dans le thème actuel YEM. Aucune modification des espaces Parents/Professeurs.

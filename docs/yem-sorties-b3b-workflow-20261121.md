# YEM — Sorties B3b : demandes, soumissions et autorisation indépendante

## Règle de périmètre
Ce lot **ne développe que les sorties** : aucune mutation de facture scolaire, frais, encaissement, paiement des familles ou remboursement d'entrée. Les dépenses et la paie restent deux registres distincts. Aucun transfert bancaire n'est déclenché par une autorisation.

## Machine à états et contrôles

| État | Actions autorisées | Effet financier |
|---|---|---|
| `draft` | Préparer / modifier / soumettre avec `school.operating.manage` | Aucun engagement validé |
| `submitted` | Approuver ou refuser par `school.operating.approve`, agent **distinct** du préparateur ET soumissionnaire | Aucun engagement jusqu'à l'approbation |
| `rejected` | Corriger sous contrôle de révision, puis resoumettre (pas de resoumission directe) | Aucun engagement |
| `approved` | Règlement **déjà effectué** déclaré par `school.operating.pay`, autre acteur | Engagement dans le plafond budgétaire, règlement distinct |

- Chaque transition verrouille la dépense dans une transaction et exige la révision courante ; les tentatives concurrentes et doubles requêtes ne peuvent pas répéter une décision.
- Les validations de base sont maintenues : budget approuvé, exercice ouvert, pôle et catégorie actifs, bénéficiaire valide et justificatif référencé, plafond budgétaire verrouillé.
- Le refus est obligatoirement motivé (10 à 240 caractères).
- Les décisions `submitted`, `rejected`, `revised`, `approved` sont historisées dans `OperatingExpenseDecision` (auteur, révision, motif, horodatage), sans copier des montants dans `SchoolAudit.details`.
- Un refus ne supprime aucune demande, ne débite aucune trésorerie et ne libère aucun budget engagé puisque la demande n'avait jamais été approuvée.
- Une demande déjà approuvée n'est plus éditable. Les paiements restent partiels/intégraux déclaratifs, historisés et annulables sous contrôle.
- Les approbateurs ne peuvent être ni préparateur ni soumissionnaire. Les autorisations d'autres établissements sont inaccessibles.

## Migration
`0085_operating_expense_workflow` dépend de `0084_operating_expense_beneficiaries`.
- Nouvelles colonnes `workflow_state`, `submitted_by`, `submitted_at`.
- Tous les anciens enregistrements approuvés sont conservés et marqués `approved` sans nouvel acte d'autorisation (la preuve d'autorisation historique reste `approved_by/approved_at`). Les anciens brouillons restent `draft`.
- Nouvelle table de décisions avec `PROTECT`, RLS PostgreSQL et `REVOKE` direct pour `PUBLIC`, `anon`, `authenticated`.
- Aucun montant, paie, paiement élève, fournisseur ou budget réécrit.

## Routes web API
Sur le préfixe `/api/v1/schools/{school_id}/operating/` :
- `POST expenses/{id}/submit` avec `revision` ;
- `POST expenses/{id}/reject` avec `revision` et `reason` ;
- `POST expenses/{id}/approve` **existant**, désormais réservé aux demandes soumises et validées indépendamment ;
- `PATCH expenses/{id}` uniquement sur brouillons ou refusées, ce qui réinitialise la soumission antérieure, sans perdre l'historique des refus ;
- `GET expenses/{id}` expose les décisions et motifs réservés aux personnes ayant `school.operating.read`.

## Interface
- Préparateur : bouton « Soumettre pour autorisation » sur brouillon.
- Contrôleur : « Autoriser » et formulaire de refus motivé sur état soumis.
- Refusée : motif et historique lisibles dans le dossier ; révision indispensable avant resoumission.
- Chaque transition utilise les permissions et la version API. Pas de fenêtre de saisie bloquante pour motif : formulaire intégré.

## Tests ajoutés ou adaptés
- Interdiction de payer ou autoriser sans soumission ; un refus ne crée aucun engagement.
- Cycle `brouillon → soumise → refusée → corrigée → soumise → autorisée` et preuve historisée.
- Double soumission/rejeu et révision obsolète rejetés.
- Impossibilité de s'approuver/refuser soi-même.
- Permissions multi-rôles, cloisonnement établissement, impossibilité de modifier une demande soumise.
- Mise à jour des anciens tests de validation de dépense ; tests React préparateur et contrôleur.

## Intégration sans conflit avec les entrées
Empilement : **#255 → #257 → #258 → #261 → B3b**.
Seuls fichiers propres aux dépenses modifiés, plus une extension minimale du routeur commun `urls.py` (deux routes `/operating/expenses/.../submit|reject`, aucun changement aux routes `/finance/`).
La branche principale a entre-temps reçu #253, #256 et #260 pour le chantier A : rebase et revalidation des conflits indispensables avant fusion.

## À vérifier avant fusion et déploiement
- Exécuter `manage.py check`, `makemigrations --check`, `institutions.test_operating`, tests React et tests PostgreSQL.
- Revalider graphe migrations : nouvelle `0085` contre toute migration parallèle ouverte, pas de numéro en collision.
- Vérifier CI sur la base rebasée et tests multi-comptes. Audit visuel seul insuffisant.
- Conserver PR en brouillon jusqu'aux validations.
- Avant toute migration Supabase en production : **sauvegarde réelle chiffrée et restauration dans un environnement distinct**. Aucun déploiement automatique.

**Statut à la rédaction :** code et tests écrits sur branche, non exécutés dans cet échange ; aucune fusion, migration ni opération financière réelle.

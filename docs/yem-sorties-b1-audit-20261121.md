# YEM — Chantier B (sorties) — Audit B1

Date : 21 novembre 2026  
Statut : **audit statique du dépôt ; recette runtime et production non vérifiées**  
Dépôt : `BlackGhost99/SYKOLO` — branche source `main`

## 1. Frontière impérative entre chantiers

- **B (ce chantier)** : dépenses, demandes/approbations, fournisseurs et bénéficiaires, budgets, engagements, paie, décaissements déclarés, investissements, analyses des sorties.
- **A (autre chantier en parallèle)** : scolarité, frais, créances, ventes, recettes, encaissements et imports financiers des entrées.
- Les modèles et endpoints des entrées ne doivent pas être modifiés par B.
- Les composants communs (caisse, registre financier, catégorisation, stocks, tableaux de bord, contrepassations, permissions, clôtures) nécessitent un contrat d'interface et un propriétaire de changement explicite. Aucune migration concurrente ni modification directe de `main`.
- PR A observée ouverte : [#253 — catégorisation des frais scolaires](https://github.com/BlackGhost99/SYKOLO/pull/253), sur `backend/institutions/entry_category_policy.py`, `entry_income.py`, `urls.py`, `test_entry_categories.py` et `frontend/FinancePanel.jsx`, `IncomeFeeCategoryPanel.jsx` et son test. Ces fichiers sont **hors périmètre d'écriture B**.
- Autres PR observées ouvertes (non liées au périmètre de correction B) : #235, #240, #245, #246. Réexaminer leur état juste avant tout rebase ou fusion.

## 2. Existant vérifié dans le code

| Domaine | Fichiers / PR | État démontré par lecture | Limite |
|---|---|---|---|
| Paie privée | `payroll_models.py`, `payroll_views.py`, `PayrollPanel.jsx`, migration `0051`, [#132](https://github.com/BlackGhost99/SYKOLO/pull/132) | Brouillon, validation indépendante, règlement déclaré, annulation historisée, permissions, clés UUID | Aucun transfert d'argent réel, calcul automatique légal ou paie réglementaire certifiée |
| Dépenses de fonctionnement | `operating_models.py`, `operating_views.py`, `OperatingPanel.jsx`, migration `0052`, [#133](https://github.com/BlackGhost99/SYKOLO/pull/133) | Fournisseurs, enveloppes annuelles par catégorie/devise, demande, validation indépendante, décaissement déclaré partiel, annulation, rôles, budget verrouillé | Ne couvre pas le catalogue complet de sorties ni la classification par activité |
| Contrôle de caisse | `finance_cash_views.py`, [#244](https://github.com/BlackGhost99/SYKOLO/pull/244) | Clôtures et recettes cash déclarées | Pas encore de solde de trésorerie intégrant les sorties et les fonds d'ouverture |
| Indicateurs financiers partagés | `finance_summary_views.py`, `owner_overview_views.py` | Résumés de frais, paiements et recouvrements scolaires | Ne pas les présenter comme des flux nets, bénéfices ou résultats incluant les sorties |
| Tests existants | `backend/institutions/test_operating.py`, `frontend/OperatingPanel.test.jsx` | Scénarios de base présents dans le dépôt | Non exécutés durant cet audit ; aucune réussite CI ou production attestée |

Les PR #36 et #37 ont été remplacées par #41 (fusionnée) ; #42, #45, #104, #132, #133, #195, #219, #231, #232, #239 et #244 ont été identifiées fusionnées au moment de la lecture. **Ne pas assimiler PR fusionnée et fonctionnement vérifié en production.**

## 3. Écarts et risques vérifiables

### P0 — Fidélité et consolidation des indicateurs

1. **Synthèse budgétaire incomplète au-delà de 200 enveloppes** : `operating_views.summary` parcourt `budgets[:200]`, puis produit les totaux sur ce sous-ensemble. Un établissement avec davantage de budgets aurait des chiffres consolidés sous-estimés sans signalement. Supprimer cette limite pour les agrégations et prévoir pagination pour les listes.
2. **Trésorerie globale incomplète** : le module `finance_cash_views` compte des recettes déclarées, et `finance_summary_views` s'appuie sur `FeeCharge`/`FeePayment`. Les règlements de dépenses et de paie restent dans deux registres séparés. Ajouter ultérieurement un contrat de lecture de **sorties** (agrégations en API B) ; ne pas modifier ni présumer le contrat des **entrées**.
3. **Terminologie** : les règlements sont **déclarés**, pas certifiés par une banque. N'utiliser « confirmé » qu'avec une preuve adaptée ; distinguer engagement, charge, décaissement et flux net.

### P1 — Couverture fonctionnelle

4. **Fournisseur commercial obligatoire** : `OperatingExpense.supplier` est non nullable ; `operating_views.expense_fields` exige un fournisseur ; `OperatingPanel.jsx` rend le champ requis. Or les dépenses internes, indemnités, remboursements, administrations publiques et autres bénéficiaires ne supposent pas forcément de fournisseur commercial. Correction à concevoir avec migration additive contrôlée et bénéficiaire explicite.
5. **Classification de l'activité absente** : `OperatingBudget` porte une catégorie libre ; `OperatingExpense` n'a ni pôle scolaire/extrascolaire/commun/investissement/trésorerie, ni centre de coût, ni clé de répartition. Le cahier B impose une classification d'activité indépendante de la catégorie comptable.
6. **Demandes de dépense limitées** : pas de circuit complet soumission/examen/refus/engagement/réception/autorisation de règlement. Un projet exige un budget préalablement approuvé et une référence de facture/devis obligatoire. Cela empêche certaines demandes préalables à l'achat.
7. **Paiement réellement exécuté non vérifié** : `OperatingExpensePayment` et `StaffPayDisbursement` sont des justificatifs déclaratifs. Aucune API de transfert sortant SingPay ne doit être présumée. Vérifier capacités contractuelles et techniques avant tout transfert réel.
8. **Livrables avancés manquants ou non attestés** : dépenses récurrentes, avances, gestion d'immobilisations, rattachement de pièces binaires, budgets par activité/service/projet, répartition de charges communes, tableaux interactifs traversant jusqu'au justificatif, comptes de résultats par activité.
9. **Risque de listes tronquées** : `operating_views.expenses` retourne les 400 premières dépenses sans pagination ; prévoir pagination et distinction explicite entre totaux exhaustifs et lignes affichées.

### P2 — Utilisabilité et interconnexion

10. La séparation scolaire/extrascolaire, les coûts d'activité et la rentabilité ne doivent **jamais** résulter d'une réécriture des recettes du chantier A. B expose ses coûts propres ; un agrégateur commun, distinct, consommera les interfaces publiées des deux chantiers.
11. Le suivi de la paie du personnel et les dépenses de fonctionnement ne sont pas un grand livre comptable SYSCOHADA. Ne pas publier de résultat comptable « certifié » sans le socle adapté.

## 4. Cartographie des responsabilités

| Zone | Propriétaire de modification |
|---|---|
| `operating_models.py`, `operating_views.py`, `test_operating.py`, `OperatingPanel.jsx` et test | B |
| `payroll_models.py`, `payroll_views.py`, `test_payroll.py`, `PayrollPanel.jsx` | B |
| `entry_income.py`, `entry_category_policy.py`, `FinancePanel.jsx`, `IncomeFeeCategoryPanel.jsx` | A |
| `finance_models.py`, `finance_cash_views.py`, `finance_summary_views.py`, `owner_overview_views.py`, `urls.py`, migrations, rôles, tableau de bord | Partagés : pas de modification sans coordination |

Les sous-domaines propres au chantier B peuvent utiliser des endpoints B et leurs tests sans éditer les fichiers partagés. Toute extension de modèle doit contrôler le dernier graphe des migrations au moment de la PR.

## 5. Premier lot technique recommandé, sans migration ni conflit A

**B1a : corriger la synthèse des dépenses** dans `operating_views.py` et étendre `test_operating.py` :
- résultats exhaustifs (pas de tranche `[:200]` dans les totaux) ;
- calculs par établissement, année et devise, uniquement sur budgets approuvés et règlements non annulés ;
- test avec plus de 200 budgets, tests des soldes, et non-régression sur les permissions ;
- aucune mutation des données d'entrées ni des modules de caisse.

**B2 ensuite** : schéma de classification des sorties (pôle / activité / catégorie / centre de coût), avec stratégie de reprise conservant les anciens enregistrements et aucune valeur arbitraire appliquée rétroactivement.

**B3 ensuite** : bénéficiaires non commerciaux et demandes préalables, migration contrôlée, recettes de tests isolées.

## 6. Validation impérative avant fusion/déploiement

- Recontrôler le `main` actuel et les PR A ouvertes.
- Afficher le diff exact ; refuser les modifications d'entrées et de composants partagés non coordonnées.
- Exécuter tests Django ciblés, tests frontend, contrôle des migrations et tests d'accès croisés.
- Vérifier les scénarios concurrents (double validation, même clé UUID, dépassement de budget, annulation).
- Aucune écriture de simulation dans Supabase de production.
- Avant migrations de production, sauvegarde réelle chiffrée + restauration testée hors production.
- Fusionner uniquement après CI verte et contrôle des conflits ; confirmer séparément l'état de déploiement Render.

## 7. Statut de cet audit

- **Fait** : lecture des principales sources B, des interfaces B, migrations 0051/0052, documentations M3.3/M3.4, et statut des PR pertinentes.
- **Non fait** : lancement effectif de la suite Django/React, inspection des données Supabase, validation des rôles en production, tests réels SingPay, validation de restauration d'une sauvegarde.
- **Aucune modification métier, migration, fusion ou mise en production** réalisée dans ce lot documentaire.

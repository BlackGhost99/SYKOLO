# YEM — B1 : audit technique des sorties financières

**Date du contrôle :** 21 novembre 2026. **Référentiel :** cahier des charges original du *chantier B — gestion intégrale et catégorisée des sorties financières* (38 sections, dont la section 2 sur l'audit, la section 36 sur les 46 tests d'acceptation et la section 37 sur les 12 phases). **Dépôt :** `BlackGhost99/SYKOLO`.

> **Périmètre :** revue du code GitHub accessible, des PR et de leurs fichiers, des documentations M3.3/M3.4, de l'historique des migrations de Supabase YEM (lecture seule) et des configurations Render. Ce document est un état technique de la vérification ; il ne vaut pas validation des 46 scénarios, restauration d'une vraie sauvegarde, recette par rôles ni déploiement.

## 1. Statuts utilisés

- **Existant testé** : module et tests identifiés ; ne signifie pas que toutes les variantes du cahier sont couvertes.
- **Existant à compléter** : mécanisme réel, mais fonctions du cahier non démontrées.
- **Défectueux / risque** : défaut identifié, régression possible ou écart de cohérence.
- **Absent du périmètre audité** : aucun modèle/endpoint spécialisé identifié dans les fichiers inspectés ou dans la recherche du dépôt ; vérifier avant de conclure à une absence définitive.
- **En PR non fusionnée** : code prêt sur branche d'intégration, sans disponibilité garantie en production.

## 2. Historique des PR citées par le cahier

| PR | État GitHub observé | Réemploi / conclusion |
| --- | --- | --- |
| #36, #37 | Fermées, non fusionnées et remplacées | Ne pas les réintroduire : la succession mène à #41 |
| #41 | Fusionnée | Encaissements multi-frais, caisse, contrôles |
| #42 | Fusionnée | Séparation des fonctions financières et transferts de caisse |
| #45 | Fusionnée | Protection des délégations financières |
| #104 | Fusionnée | Vue propriétaire (indicateurs scolaires/financiers) |
| #132 | Fusionnée | M3.3, paie confidentielle et règlements déclarés |
| #133 | Fusionnée | M3.4, fournisseurs, budgets et dépenses |
| #195 | Fusionnée | Console commerciale BWETEK — distincte des dépenses d'école |
| #219 | Fusionnée | Commande de rapprochement SingPay, **pas** un moteur de décaissement |
| #231, #232 | Fusionnées | Reprise des historiques financiers, préparation/contrôle |
| #235 | Ouverte, brouillon, **non fusionnée** | Contrepassation historique ; migration `0080_historical_reversal` déjà appliquée à Supabase par un autre chemin : rapprocher la provenance avant toute fusion |
| #244 | Fusionnée | Caisse, clôtures et actualisation des recettes |
| #255 → #257 → #258 → #261 → #264 → #265 | Ouvertes, brouillons, dépendances en chaîne | Correctif total des budgets ; pôles ; catalogue ; bénéficiaires ; soumissions/refus ; file et pagination |
| #269 | Ouverte, brouillon | Branche d'intégration des sorties sur un ancien `main` ; CI complète, audit responsive et exercice de restauration **synthétique** réussis, mais `main` a avancé depuis |

Sources : métadonnées GitHub et fichiers modifiés des PR citées, code inspecté sur `main` et la branche #269.

## 3. Matrice des fonctionnalités constatées

| Bloc du cahier | Code existant / état | Lacune et action sans doublon |
| --- | --- | --- |
| **Scolarité, encaissements, clôture de caisse** | **Existant testé** : `finance_models.py`, `finance_cash_views.py`, `finance_batch_views.py`, rôles et tests des PR #41/#42/#244 | **Composant partagé** : ne pas refaire une caisse dans les sorties ; raccorder les décaissements sans mélanger les encaissements |
| **Droits direction/comptabilité/économe** | **Existant testé** : `services.py`, droits `school.operating.*` et `school.payroll.*`, contrôles et tests | **À compléter** : droit distinct pour la demande d'un enseignant / rôle personnalisé, circuits d'autorisation configurables et preuve de la recette multi-rôles |
| **Budgets / dépenses / fournisseurs M3.4** | **Existant testé** sur `main`, migration `0052_operating_budget_expenses`, `operating_views.py`, `operating_models.py` | Budgets principalement par catégorie/année ; pas toutes les périodicités, projets, transferts budgétaires, exceptions ni rapprochements demandés |
| **Agrégat de plus de 200 budgets** | **Défectueux sur `main`** : `summary` limitait les lignes à `budgets[:200]` | **Corrigé seulement en PR #255 et #269** : `iterator(chunk_size=200)`, test au-delà de 200 budgets ; non déployé |
| **Pôles S1–S5 / sous-catégories / centres de coûts / nature comptable** | **En PR non fusionnée**, migrations `0082` et `0083`, catalogue et labels historiques figés | Classification partielle : centre de coûts et nature comptable encore en texte libre ; paramétrage global, règles par exercice, affectation et référentiels à finaliser en B2 |
| **Bénéficiaires non commerciaux** | **En PR non fusionnée**, migration `0084`, personne, personnel, organisme, parent, association | Contrats, pièces, échéances, profils de tiers, justificatifs et rapprochements non consolidés |
| **Demandes / approbation indépendante** | **En PR non fusionnée**, migration `0085`, brouillon/soumise/refusée/approuvée, historique des décisions et file paginée | **Incomplet** : quantités, urgence, date souhaitée, motif structuré, pièces, statut en examen/annulée, délégations par montant et demandes des enseignants ; l'API `submit_expense` exige actuellement `school.operating.manage` |
| **Décaissements des dépenses** | **Existant testé** : versements déclarés, partiels, idempotence, annulation contrôlée dans `OperatingExpensePayment` | **Incomplet** : pas d'exécution bancaire ni de versement SingPay attesté ; moteur de règlements groupés/multifactures, autorisations de paiement et rapprochements à construire |
| **Paie M3.3** | **Existant testé** : migration `0051_payroll_ledger`, `StaffPayRun`, `StaffPayDisbursement`, contrôle indépendant, version, confidentialité et paiement déclaré | **Incomplet** : primes/cotisations/avances structurées, coût total employeur, bulletins, réclamations et confirmation personnelle à étudier en B4. Ne pas dupliquer `StaffPayRun` |
| **Achats / bons de commande / factures fournisseurs** | **Absent du périmètre audité** comme chaîne autonome ; `invoice_reference` est un champ texte, non une facture numérisée | Créer le flux devis → commande → réception → facture → dette → paiement → avoir ; sans doubler les opérations de stock du chantier A |
| **Stocks, marges et immobilisations** | **Absent du périmètre audité** comme grand livre et mouvements partagés des sorties ; un catalogue de produits extrascolaires existe côté entrées | Définir modèle commun entrée/sortie, valorisation et coûts vendus ; registre des immobilisations/amortissements en B7 |
| **Remboursements et contrepassations** | **Partiels** : annulations tracées de versements, migration historique `0080` déjà appliquée ; PR #235 toujours ouverte | Réconciliation opération initiale → avoir → remboursement réel ; vérification anti-double remboursement, séparation de l'annulation et du transfert |
| **Synthèse scolaire / extrascolaire et résultat comptable** | **Partielle** : tableau propriétaire, synthèse des encaissements, ventilation de dépenses de #269 | Nécessite modèle fiable charges/ventes/stock, comptes de trésorerie et affectation des charges communes ; distinguer flux et résultat comptable |
| **Diagrammes cliquables / widgets personnalisés** | **Partiels** : panneaux et indicateurs existants | Parcours synthèse → catégorie → sous-catégorie → transaction → justificatif et préférences persistées non validés pour toutes les sorties |
| **Justificatifs / exports** | **Incomplets** : références textuelles ; `docs/m3-4-depenses-budgets.md` confirme l'absence d'upload de PDF/images pour les dépenses | Stockage privé, antivirus, droits, intégrité, PDF/Excel/CSV et documents professionnels à réaliser en B8 |
| **Notifications / actualisation synchronisée** | **Existants ailleurs dans YEM ; non démontrés pour toutes les sorties** | Événements demandes, décisions, échéances, paiements, remboursements et rafraîchissement multi-rôles à valider |
| **46 tests d'acceptation** | Tests automatisés existants ; sur #269 : CI générale, build, PostgreSQL, Docker et audit responsive réussis | **Non validés comme une matrice exhaustive des 46 scénarios du cahier** ; recette par rôle, PC, mobile et PWA à établir B11 |
| **Déploiement / sauvegardes** | **Non finalisé** pour ces PR | Supabase production ne contient pas encore les migrations `0082`–`0085`; sauvegarde/restauration **réelle** non attestée ; Render suit `main` avec déploiement automatique |

## 4. Revue du dépôt, migrations et données

Fichiers principaux inspectés : `operating_models.py`, `operating_views.py`, `operating_catalog_views.py`, `operating_workflow_views.py`, `payroll_models.py`, `payroll_views.py`, `staff_models.py`, `staff_profile_models.py`, `finance_models.py`, `finance_cash_views.py`, `finance_summary_views.py`, `finance_quality_views.py`, `finance_evidence.py`, `financial_migration_views.py`, `owner_overview_views.py`, `overview_views.py`, `singpay_models.py`, `singpay_service.py`, `services.py`, et les panneaux React, tests et migrations indiqués à la section 2 du cahier. Les documentations `docs/m3-3-remunerations-personnel.md` et `docs/m3-4-depenses-budgets.md` ont été lues.

Vérification Supabase **en lecture seule** : projet `kxkifsrlkwhedqraojvj`, `ACTIVE_HEALTHY`, version PostgreSQL 17, dernière migration `institutions` = `0081_gemini_daily_usage`. En particulier, `0082`, `0083`, `0084`, `0085` ne sont pas en production. La vérification n'a transféré aucune donnée personnelle et n'a effectué aucune modification SQL.

**Production sensible :** Render `yem-api` suit `main` avec déploiement automatique après vérification ; `yem-pc-preview` suit `main` avec déploiement automatique à chaque commit. Supabase YEM est sur le plan Free. Aucun exercice attesté de restauration d'une vraie sauvegarde. **Ne pas fusionner de PR contenant des migrations financières en production** avant sauvegarde chiffrée, restauration isolée, validation d'une fenêtre de déploiement et plan de retour arrière.

**Évolution concurrente :** après la création de #269, `main` a avancé de deux commits portant sur les devis et règles de vente extrascolaires ; `backend/institutions/urls.py` est partagé avec ce chantier. Rebaser/reporter **uniquement les quatre routes des sorties**, vérifier le diff et refaire les tests avant toute intégration.

## 5. Ownership et risques d'intégration entre A (entrées) et B (sorties)

| Composant | Responsable logique | Contrat d'intégration |
| --- | --- | --- |
| Scolarité, créances, ventes, encaissements | A | Ne pas toucher aux paiements élèves ni aux écritures scolaires existantes |
| Dépenses, budgets, paie, obligations fournisseurs, immobilisations | B | Reprendre et étendre M3.3/M3.4, isoler par établissement et acteur |
| Caisse, trésorerie, stocks, remboursements, indicateurs, notifications, permissions | A + B | Définir un **modèle commun** ; traiter les transferts internes sans les additionner comme charges ; isoler scolaire/extrascolaire ; coordonner les changements de `urls.py` et migrations |

Risques prioritaires : création de doubles registres, cumul entre engagements et paiements, montants des salaires exposés à des rôles non habilités, fusion de migrations divergentes, rupture de `main` durant le chantier parallèle, activation involontaire du déploiement automatique.

## 6. Passage B1 → B2

**B1 — Audit du dépôt YEM et de l'infrastructure : réalisé au niveau de preuve ci-dessus**. Ce qui n'est **pas** prouvé : couverture d'anciens dépôts dont l'identité n'a pas été fournie, recette multi-rôles, sauvegarde réelle, opérationnalité de toutes les exigences. Un audit ne rend pas une fonctionnalité prête en production.

**Travaux B2 à exécuter dans l'ordre :**
1. Contrôler les 20 familles B01–B20 du cahier **sans coder 20 catégories rigides** : référentiel initial administrable et extensible, respect du passé.
2. Rendre configurables les cinq pôles S1–S5 et les centres de coûts, avec activités et natures comptables séparées.
3. Encadrer les catégories/subcatégories et l'archivage, les noms historiques figés, les permissions et l'isolation multi-établissements.
4. Écrire les tests de mutation, lecture historique et compatibilité avec les entrées ; prouver que le même coût n'est compté qu'une fois.
5. Conserver les PR #257/#258 comme base et **ne pas recréer** les modèles déjà présents ; validation sur branche avec `main` actualisé.

**Règle de suivi :** chaque phase B2 à B12 doit posséder un tableau exigence → code → test → preuve de livraison → état, avec des verdicts « démontré », « partiel », « absent », « bloqué ». Les tests verts d'une phase ne valent pas achèvement du cahier intégral.

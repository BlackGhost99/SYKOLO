# YEM Sorties — B2 finalisation du catalogue et de la classification

Référence : cahier des charges initial du chantier B (sections 3, 4, 5, 8, 24–26, 34–36). Travaux empilés sur la branche d'intégration #269. **Pas une preuve de déploiement.**

## Réutilisation de l'existant

- `OperatingExpenseCategory` (PR #258) : deux niveaux, codes uniques par école, archivage et révision, libellés des dépenses historisés.
- `OperatingExpense` (PR #257/#261/#264) : pôle stable, centre de coûts et nature comptable existants en texte libre, bénéficiaires différenciés et circuit d'autorisation.
- `OperatingSupplier`, `OperatingBudget`, `StaffPayRun`, `CashClosing` ne sont pas dupliqués.
- L'ensemble des API et écrans d'encaissement côté chantier A reste inchangé.

## B2d — Catalogue administratif facultatif

`operating_seed_catalog.py` reprend **20 familles B01–B20 et leurs 211 sous-catégories** à partir du texte original du cahier.

`GET /api/v1/schools/{school}/operating/catalog-defaults` : aperçu en lecture seule. `POST` avec `{"families":["b01","b02"],"include_subcategories":true}` : installation explicite, éventuellement partielle.

- Jamais d'injection automatique à la lecture ou à la migration.
- Une famille et une sous-catégorie existantes conservent leur nom, statut d'archivage et révision. L'installation est **idempotente** et transactionnelle.
- Codes réservés au modèle uniquement dans le cadre de l'import ; le catalogue est administrable, extensible et non rigide.
- Les pôles proposés sont des **suggestions** ; aucune écriture ne change de pôle par simple catégorie.
- L'import exige `school.operating.manage` ; la lecture exige `school.operating.read` ; les écoles sont isolées.

## B2e — Pôles S1–S5, centres et natures

Nouveau référentiel **`OperatingClassificationOption`**, par école, avec `kind` (`pole`, `cost_center`, `accounting_nature`), code stable, libellé, activité associée facultative pour les centres, archivage et révision. Migration additive **0086**, RLS activé et privilèges Data API révoqués sur la nouvelle table.

- **Pôles** : cinq codes fonctionnels stables (`school`, `extraschool`, `common`, `investment`, `cash_other`). Leurs libellés et leur activation sont configurables par école ; GET renvoie des valeurs par défaut **sans écrire dans la base**.
- **Centre de coûts** : créé et archivé à volonté ; peut être restreint à un pôle ou partagé. Une dépense ne peut pas sélectionner un centre d'une autre école, archivé ou incompatible.
- **Nature comptable** : référentiel distinct du pôle et de la catégorie, sans restriction d'activité.
- **Historique** : les champs texte `cost_center`, `accounting_nature` restent lisibles. Les nouvelles références `cost_center_ref` et `accounting_nature_ref` sont facultatives pour les opérations historiques ; les libellés des anciennes dépenses ne sont jamais recalculés après renommage.
- Les nouveaux dossiers issus de l'interface utilisent les références contrôlées ; l'API conserve l'ancien contrat texte pour ne pas casser les intégrations déjà utilisées. Cette compatibilité devra être surveillée lors d'une future stratégie de dépréciation.
- Les validations se font à la création, à la correction d'un brouillon, à la soumission et à l'approbation ; une référence archivée ne peut pas devenir une nouvelle autorisation.
- L'archivage ne supprime jamais les opérations ; un centre déjà rattaché à une dépense ne peut pas changer de pôle, pour préserver sa cohérence.

API :
- `GET/POST /api/v1/schools/{school}/operating/classification`
- `GET/PATCH /api/v1/schools/{school}/operating/classification/{uuid}`
- `PATCH /api/v1/schools/{school}/operating/classification/poles/{code}`

## Contrôles de recette B2

1. Catalogue initial 20 + 211 et lecture seule avant import.
2. Import partiel, idempotence, absence de doublon, révisions/archivages conservés.
3. Conflit de code : aucune importation partielle.
4. Isolation entre établissements ; permissions lire / configurer séparées.
5. Cinq pôles, libellés configurables sans changer les codes.
6. Centres paramétrables et nature comptable indépendante.
7. Protection du pôle lié, rejeu de révisions, choix d'une autre école refusé.
8. Historique texte préservé après changement de nom ou archivage.
9. Régles de soumission et d'autorisation avec centres archivés.
10. Non-régression M3.3 (paie), caisse, encaissements et schéma migratoire.
11. Validation Django PostgreSQL, Vitest, build, Docker et responsive par GitHub Actions avant tout déploiement.

## Reste explicitement hors B2

Demande d'achat avec quantité/date souhaitée/urgence, pièces jointes, plafonds d'autorisation et contrôles par fonction : **B3**. Budgets par projet, engagements fournisseurs, achats/commandes et dettes : **B5**. Décaissement effectif et rapprochements : **B6**. Stocks, immobilisations et charges communes réparties : **B7/B10**. Documents/exports et diagrammes : **B8/B9**.

**B2 n'autorise aucune fusion vers `main` tant que la sauvegarde réelle Supabase n'a pas été restaurée en environnement isolé.** Render déploie automatiquement `main` et ne doit pas être déclenché accidentellement.

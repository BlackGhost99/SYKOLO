# YEM — P0 : preuves, simulations et rapprochement financier

## Constat du 14 novembre 2026
- Les écritures existantes dans Supabase mélangent des opérations d'entraînement et des opérations déclarées dans le registre scolaire. Elles ne prouvent pas l'encaissement bancaire réel.
- Au Lycée Privé 1, les lignes de frais explicitement préfixées « DÉMO — » sont des simulations identifiables.
- Au Lycée AWASSI, 600 paiements historiques sous la méthode « cash » ne permettent pas, sur la seule base du code, de prouver qu'une somme a été physiquement reçue.
- Aucun reclassement automatique, aucune suppression, aucun paiement créé. Conserver les pièces d'origine et la date de constat.

## Service d'audit
L'API GET /api/v1/schools/{school_id}/finance/quality est réservée à school.finance.read.

La classification se fonde sur la méthode déclarée et sur le libellé figé dans la facture `FeeCharge.label` ; elle ne se fonde **pas** sur `FeeSchedule.label` car un gestionnaire peut modifier le tarif ultérieurement. Un changement de libellé tarifaire ne doit jamais changer rétroactivement la classification d'un paiement ou l'attestation PDF.
L'année scolaire est filtrable par ?year={uuid}; les montants sont regroupés par devise.
Catégories disjointes :
1. explicit_demo_charges : frais dont le libellé ou celui du tarif indique explicitement DÉMO.
2. explicit_demo_payments : paiements sous méthode simulation ou relatifs aux frais marqués DÉMO.
3. legacy_cash_unverified : écritures historiques cash sans preuve d'espèces réelles.
4. cash_declared : montants déclarés sous especes, non certifiés par une banque.
5. other_manual_unverified : virements, mobile_money et autres méthodes déclarées, à rapprocher.

Les tableaux de bord historiques ne sont pas modifiés par ce premier lot ; l'écran de caisse signale la classification et ne présente jamais ce rapport comme un certificat de recettes. Les comptes individuels, remboursements et restes à payer gardent leur historique intact jusqu'à arbitrage indépendant.

## Blocages et preuves nécessaires
- Fournir une sauvegarde chiffrée de la vraie base, copiée hors du dépôt et hors des conversations.
- Tester une restauration sur une instance PostgreSQL 17 locale isolée (scripts existants : scripts/yem_backup.sh et scripts/yem_restore_drill.sh), puis vérifier les montants, identifiants, permissions et historiques.
- Rapprocher les anciennes écritures AWASSI avec les justificatifs physiques, ou avec un procès-verbal confirmant leur origine fictive. Le nom de l'établissement seul ne suffit jamais à classifier l'opération.
- Après preuve, produire une migration explicitement validée / une correction auditée sans effacer les lignes ni modifier rétroactivement les reçus.
- Tester ensuite les montants identiques sur fiche élève, caisse, direction, propriétaire, parents, puis les clôtures.

La PR #136 bloque la saisie de nouveaux codes historiques cash/simulation et réserve l'espèce déclarée au code especes. Elle reste séparée et en brouillon tant que sa CI et la revue de rapprochement ne sont pas concluantes.

Aucun exercice de CI sur base fictive ne prouve une restauration de production.

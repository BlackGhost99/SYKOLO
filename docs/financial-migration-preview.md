# Reprise financière — aperçu sans écriture

Issue #226, parent #225. Cette livraison est indépendante de la PR #227.

## Contrat API
POST multipart /api/v1/schools/{school_id}/imports/finance/preview
- file : CSV/XLSX, mêmes limites et parseur que l'import élèves.
- sheet et header_row : facultatifs.
- year : UUID de l'année scolaire ouverte.
- cutoff : date ISO de reprise, dans l'année et non future.
- mapping : JSON, par exemple {"student_code":0,"amounts":[{"column":1,"schedule":"UUID_DU_TARIF"}]}.

L'opérateur associe explicitement les colonnes aux tarifs XAF actifs de cette école et année. Il s'agit de montants cumulés déclarés par échéance, pas de transactions individuelles. L'accès exige school.finance.approve. Maximum 12 tarifs, 2 000 cellules financières. Matricule exact sans suppression des zéros initiaux (insensible à la casse), unique dans le fichier et les inscriptions actives de l'année. Pas de rapprochement automatique par nom.

## États
- proposed : montant positif dans la limite des frais, à justifier.
- zero : zéro explicitement déclaré.
- unknown : cellule vide, ne pas interpréter comme zéro.
- overpayment : montant déclaré ou déjà comptabilisé au-delà du dû.
- existing_review : présence d'un paiement YEM, rapprochement manuel requis ; ne jamais déduire automatiquement une différence.
- invalid : montant ambigu, tarif incompatible, échéance future ou frais de démonstration.
- identity_review : matricule inconnu/ambigu/répété.

Les montants calculés utilisent le snapshot du frais existant, sinon le barème actif et la remise de bourse reconnue par le moteur métier. Rien n'est créé. Les soldes déclarés ne sont pas les soldes comptables certifiés. Les frais d'admission spécifiques sont exclus de cette première brique : leur ledger séparé nécessite un autre rapprochement. Le résultat n'est ni un jeton d'engagement ni un justificatif.

## Suite
- [ ] Interface financière PC/mobile, sélection de tarif par classe et période, aperçu et anomalies.
- [ ] Modèle de reprise historisée distinct de la caisse, avec sources justificatives, date de reprise et montants validés ; étudier les impacts sur tous les relevés, paiements, exports et clôtures.
- [ ] Permissions distinctes de préparation et d'approbation, double validation, idempotence, revalidation atomique, prévention des réimportations.
- [ ] Génération contrôlée des frais manquants et intégration des bourses/admissions.
- [ ] Reprise des écritures uniquement après recette comptable complète.

Aucune donnée envoyée à un fournisseur IA, aucun paiement SingPay, aucune écriture de production.

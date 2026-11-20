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
- [x] Première interface financière PC/mobile (à valider par CI et recette visuelle), sélection explicite de tarif, aperçu et anomalies.
- [ ] Modèle de reprise historisée distinct de la caisse, avec sources justificatives, date de reprise et montants validés ; étudier les impacts sur tous les relevés, paiements, exports et clôtures.
- [ ] Permissions distinctes de préparation et d'approbation, double validation, idempotence, revalidation atomique, prévention des réimportations.
- [ ] Génération contrôlée des frais manquants et intégration des bourses/admissions.
- [ ] Reprise des écritures uniquement après recette comptable complète.

Aucune donnée envoyée à un fournisseur IA, aucun paiement SingPay, aucune écriture de production.

## Interface de reprise

Encaissements → Reprise financière, visible pour les titulaires de school.finance.approve. POST multipart /imports/finance/inspect sous les mêmes droits : en-têtes, suggestion du matricule, colonnes financières possibles, années ouvertes, tarifs XAF non démonstratifs de l'école ; aucune valeur d'élève renvoyée. On choisit l'année, la date de reprise, le matricule et les tarifs, puis on examine les résultats et les anomalies. Les fichiers mixtes multi-classes doivent encore être fractionnés par classe lorsque les tarifs sont spécifiques. Aucun bouton d'écriture. Les fiches élèves sont importées séparément. CI puis recette réelle PC/mobile nécessaires.


## Extension : reprise des crédits historiques (PR #232, audit)

Le backend crée des lots préparés, puis des crédits d'ouverture historiques approuvés, distincts de FeePayment. Les trois tables disposent de RLS PostgreSQL et aucun droit client PUBLIC/anon/authenticated. Le préparateur (school.finance.receive) peut inspecter, prévisualiser, préparer et annuler ses propres lots non approuvés. Le comptable (school.finance.approve) peut examiner les lots de son établissement et approuver ceux d'un autre utilisateur. Les écrans Encaissements → Reprise financière affichent le registre et les détails du lot avant sa validation indépendante.

- POST /imports/finance/prepare : mêmes champs multipart que preview, crée uniquement un lot. Les montants inconnus doivent être régularisés ou exclus du fichier ; aucun zéro déduit.
- GET /imports/finance/batches : 100 derniers lots visibles, filtre year facultatif. Le préparateur ne voit que ses lots, sauf s'il possède aussi le droit d'approbation.
- GET /imports/finance/{batch_id} : détail des entrées, matricules locaux, tarifs et montants.
- POST /imports/finance/{batch_id}/approve : reason (référence justificative), confirmation distincte, nouvelle vérification identité/année/tarif/bourse/montant, verrou école, contrôle des opérations SingPay en cours.
- POST /imports/finance/{batch_id}/cancel : reason ; réservé au préparateur avant approbation.

Les frais historiques entièrement couverts par une bourse ne créent aucune dette. Les soldes des familles, rappels, listes élèves et synthèses intègrent les crédits ; les recettes et méthodes de paiement restent distinctes. Les synthèses comptables exposent historical_credit et settled séparément. La clôture annuelle inclut les crédits dans les soldes, pas dans les recettes, et bloque les lots préparés non traités.

Limites à lever avant fin du chantier : import multifichiers et multi-classes sur une seule colonne, sources justificatives par ligne et documents sécurisés, contrepassation des lots déjà approuvés (annulation interdite actuellement), frais d'admission, revue des libellés UI/PDF pour distinguer crédits et encaissements, tests de concurrence sur PostgreSQL et recette réelle PC/mobile. Aucun déploiement de production sans CI verte et audit.
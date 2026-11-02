# YEM — Module 11 : frais scolaires et encaissements internes

La V1 financière est un **journal d'encaissements manuels**, pas une passerelle de paiements. Aucun débit bancaire, Mobile Money ni paiement par carte n'est déclenché. Les méthodes de paiement sont des libellés configurables (code : especes, virement, mobile_money, autre) saisis par le personnel ; l'établissement reste responsable de rapprocher physiquement les encaissements.

## Tarification et affectation

Chaque établissement gère des tarifs par année et facultativement par classe, avec code, libellé, montant positif précis à deux décimales, devise ISO trois lettres (exemple XAF), date d'échéance facultative et statut actif. Aucun prix, remise ou date n'est fixé par YEM. La création d'une charge pour une inscription copie la valeur, la devise et l'échéance du tarif : une modification du tarif futur ne réécrit pas les montants historiques. Une même charge tarifaire ne peut être affectée deux fois à une inscription. Les charges ne se suppriment pas.

## Journal de caisse

Les paiements partiels sont autorisés jusqu'à concurrence du solde. Chaque enregistrement est créé dans une transaction qui verrouille la charge pour éviter les doubles allocations concurrentes. Chaque création exige une clé d'idempotence UUID : répéter la même opération renvoie le reçu existant sans ajouter de somme. Les entrées sont immuables. Pour annuler une erreur, la direction enregistre une opération d'annulation avec motif ; la ligne originale et son historique restent consultables. Le total réellement reconnu soustrait automatiquement les paiements annulés.

Le reçu PDF A4 porte la mention **encaissement déclaré et enregistré**, sans promettre une confirmation de banque. Une annulation fait apparaître le statut annulé sur ce même reçu. Le PDF utilise Cache-Control private, no-store. Le relevé des frais d'inscription indique facturé, payé et restant dû par devise, sans effectuer d'addition entre devises différentes.

## Sécurité

Les API sont isolées par école. Permissions : school.finance.read, school.finance.manage, school.finance.receive, school.finance.reverse. Le rôle « comptabilité » dispose des trois premières pour la caisse, mais **pas** de l'annulation. La direction peut annuler. Les anciens rôles non personnalisés reçoivent ces droits par migration. Toutes les écritures exigent la session et le jeton CSRF et inscrivent un événement dans le journal de l'école. Les données financières des élèves ne sont pas publiques.

## API

GET/POST /api/v1/schools/{school_uuid}/finance/schedules ; GET/PATCH /finance/schedules/{uuid}. GET/POST /finance/charges ; GET /finance/charges/{uuid}. GET/POST /finance/payments ; POST /finance/payments/{uuid}/void ; GET /finance/payments/{uuid}/receipt. GET /finance/enrollments/{uuid}/statement.

Les requêtes POST de paiement incluent : charge (UUID), amount (chaîne décimale), method (code), reference (chaîne, éventuellement vide), paid_on (date ISO), idempotency_key (UUID). La clé doit rester identique lors des tentatives de renvoi du même paiement.

Ce module n'intègre pas de paiement en ligne, de connexion bancaire, d'envoi de notification, de remboursement effectif, de réduction/bourse ni de rapprochement automatisé. Ces fonctions nécessitent des workflows supplémentaires et une validation métier avant exploitation en réel.

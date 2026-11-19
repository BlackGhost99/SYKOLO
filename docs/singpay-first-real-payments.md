# Premiers paiements SingPay dans YEM

## Avant le premier paiement

1. Faire confirmer par SingPay le bénéficiaire légal, le portefeuille, la distribution, les frais contractuels et l'autorisation de production Airtel/Moov. La présence d'identifiants API ne remplace pas cette validation.
2. Utiliser le portefeuille propre à l'école pour la scolarité. Les abonnements YEM utilisent exclusivement un compte marchand BWETEK distinct, configuré par le super-administrateur avec MFA.
3. Sur le serveur, exécuter `python manage.py yem_singpay_status --verify-wallets`. Cette commande ne débite rien et affiche seulement des indicateurs sans secrets.
4. Activer les indicateurs `YEM_SINGPAY_ENABLED` et `YEM_PAYMENTS_LIVE_ENABLED` et renseigner `YEM_SINGPAY_APPROVED_DESTINATIONS` uniquement pour les destinations validées. Format école : `UUID_ECOLE:WALLET:DISTRIBUTION:live`. Format plateforme : `platform:WALLET_BWETEK:DISTRIBUTION_BWETEK:live`. Séparer les destinations par des virgules.
5. Activer `YEM_SINGPAY_RECONCILIATION_ENABLED=true` puis déployer. Le processus périodique vérifie les transactions par GET authentifié, avec verrou PostgreSQL et pause de 60 secondes entre cycles ; il ne lance aucun paiement.
6. Le propriétaire enregistre puis active le compte marchand école. L'activation vérifie l'accès au portefeuille chez SingPay ; elle ne certifie pas à elle seule la propriété de la distribution.

Ne jamais communiquer un Client Secret, une clé de chiffrement ou un code PIN Mobile Money dans un ticket ou une capture.

## Essai parent

1. Ouvrir le compte parent rattaché et vérifié à l'enfant, puis un frais exigible.
2. Vérifier l'école bénéficiaire et le montant. Commencer par 100 FCFA si le contrat et les limites SingPay le permettent et si le solde est suffisant. Un frais de dossier doit être payé intégralement.
3. Choisir Airtel Money ou Moov Money et saisir le numéro du titulaire payeur.
4. Lancer une seule demande puis valider sur le téléphone avec le code personnel Mobile Money.
5. En cas d'attente, de fermeture ou d'erreur réseau, utiliser « Vérifier » et consulter l'historique. Ne pas créer une nouvelle demande pour contourner une opération ouverte.
6. Après confirmation serveur, vérifier le reçu, la diminution exacte du solde et l'unique écriture dans les finances de l'école. Contrôler séparément le règlement reçu par l'école sur son relevé marchand.
7. Répéter avec l'autre opérateur sur un frais ou un solde disponible.

## Essai abonnement YEM

1. Le super-administrateur configure le compte marchand BWETEK dans la console d'abonnement. Il doit avoir été validé indépendamment des comptes des écoles.
2. Le propriétaire ouvre « Abonnement YEM — BWETEK Informatyk », choisit un contrat émis avec un solde positif et le montant à régler.
3. Vérifier que BWETEK est bénéficiaire, choisir l'opérateur et valider sur le téléphone.
4. Vérifier l'opération, le reçu d'abonnement et la mise à jour du solde contractuel et de l'échéancier. Aucun frais élève ne doit être modifié.

## Personnel

Les versements déclarés et confirmations du personnel restent distincts des confirmations prestataire. L'API publique `/transfer` documente une distribution adossée à un encaissement réussi configuré `isTransfer=true`. Aucun décaissement salarial autonome n'est activé sur cette seule base. Il faut obtenir de SingPay le contrat de décaissement applicable : source de fonds, bénéficiaires autorisés, limites, frais, états de confirmation, idempotence et justificatifs. Ne jamais utiliser l'argent encaissé pour la scolarité comme source salariale implicite.

## Cas à examiner

- `pending` / `unknown` : rapprochement périodique ou vérification manuelle, aucun rejeu du débit.
- `initiating` ancien : recherche serveur par référence, sans nouvelle émission du paiement.
- `review` : preuve incohérente ou affectation impossible ; contrôle financier nécessaire.
- `refund_review` : conserver le reçu initial ; traiter le remboursement par une écriture compensatoire après contrôle.
- `test_success` : succès prestataire de test, aucune dette réelle diminuée.

Les callbacks publics restent fermés tant que leur authentification officielle n'est pas établie ; le rapprochement utilise la consultation authentifiée du prestataire.

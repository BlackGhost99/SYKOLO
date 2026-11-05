# YEM Parents — Ouverture sécurisée et PWA (issue #39)

## État observé (05/11/2026)
- PWA installable par navigateur Android, service worker de base et page hors connexion disponibles dans le code.
- SMTP via fournisseur Resend/SMTP prévu et activation des comptes parents conditionnée à sa configuration. La livraison effective d'e-mails réels et les enregistrements SPF/DKIM/DMARC du domaine **ne sont pas prouvés**.
- Intégration parent PayCentral distincte du registre de scolarité, et intégration SingPay préparatoire. Paiements live maintenus **OFF** sur Render ; ne pas activer sans preuve bancaire.
- Notifications actuellement consultables dans l'application ; ne pas les appeler « Web Push en arrière-plan » sans abonnements, VAPID et service worker Push.
- Base Supabase YEM : RLS activée sur 66 tables, nouvelle migration 0029 pour sécuriser les 13 tables non protégées, et test CI pour repérer les futures régressions.

## Avant ouverture parent
1. Vérifier à partir d'une adresse d'expédition contrôlée les DNS SPF, DKIM, DMARC, les éventuels coûts et conditions du fournisseur. Tester le lien de vérification et le renvoi sur téléphone.
2. Deux écoles pilotes, deux familles fictives, plusieurs enfants ; vérifier absence de fuite entre les écoles.
3. Tester PWA sur Android réel, Android bas de gamme et réseau intermittent ; vérifier service worker, cache et expiration des sessions. Aucune donnée scolaire ni paiement ne doit persister dans un cache public.
4. Notifications en arrière-plan P1 : ajouter un abonnement Push par compte avec opt-in explicite, clés VAPID en variables privées, suppression à la déconnexion/révocation, désabonnement et protection des notifications (pas de note, santé ou identité de mineur dans le texte visible sur écran verrouillé). Les essais doivent être faits appareil fermé, réseau perdu puis rétabli.
5. Le Play Store/TWA ne doit pas être annoncé avant les tests réels et la préparation des publications requises.

## Paiements Mobile Money : **maintenir désactivés**
1. Chaque école valide son propre compte marchand SingPay/PayCentral et son bénéficiaire, coût, frais, conditions de reverssement et remboursement.
2. Le prestataire confirme par écrit les signatures de callbacks/webhooks, le processus de relecture serveur et la gestion anti-rejeu.
3. Exécuter tests sandbox : succès, refus, expiration, paiement en retard, callback dupliqué, callback falsifié, panne réseau, remboursement et rapprochement.
4. Un paiement parent ne crée pas automatiquement une écriture de frais scolaires doublée. Reçus délivrés seulement après preuve serveur et validation comptable prévue.
5. Un responsable métier autorise explicitement l'activation à l'issue d'un PV. Les clés restent uniquement dans le coffre Render, jamais dans le frontend ou GitHub.

## Liens de recette
- Parent : docs/parent-finalization-20261104.md et docs/parent-discovery.md
- SingPay : docs/singpay-audit.md (document historique, attention à l'état de fusion actuel)
- Recette : docs/recette-pilote-commerciale.md
- Sauvegardes : docs/continuite-activite-yem.md

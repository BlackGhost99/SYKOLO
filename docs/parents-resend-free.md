# YEM Parents — configuration Resend Free (novembre 2026)

Le compte Resend **gratuit** suffit pour l'envoi transactionnel lors d'un pilote : **100 e-mails/jour et 3 000/mois**, jusqu'à trois domaines d'envoi (https://resend.com/pricing). Il ne faut pas confondre abonnement Resend gratuit et possession d'un domaine : l'achat ou le renouvellement d'un domaine peut être payant.

## Mode pilote sans activation e-mail — temporaire

À la demande de l'exploitant, **YEM permet temporairement la création de comptes parents sans confirmation e-mail** pour tester les fonctionnalités sans domaine expéditeur et sans consommer le quota de Resend Free.

- Le réglage serveur `YEM_PARENT_EMAIL_VERIFICATION_REQUIRED` vaut **`false` par défaut pendant le pilote**. Tant qu'il reste à `false`, chaque nouvelle inscription valide crée directement un compte parent actif ; aucun courriel d'activation n'est envoyé ni requis pour se connecter.
- L'adresse e-mail est toujours demandée dans le formulaire, mais elle n'est **pas vérifiée** et ne vaut pas preuve d'identité. Un mot de passe robuste et un identifiant unique restent obligatoires, ainsi que les contrôles anti-abus.
- Un compte créé ainsi ne reçoit **aucun droit d'établissement, aucun bulletin, aucune inscription d'élève ni accès aux paiements d'un enfant**. Le personnel habilité doit toujours vérifier la responsabilité légale avant d'associer les dossiers.
- L'option de renvoi du lien est masquée. La récupération de mot de passe par e-mail reste indisponible si le prestataire d'envoi ne peut pas livrer à ce destinataire. Conserver les mots de passe de test et utiliser les contrôles administrateur si nécessaire.
- **Avant l'ouverture publique** : configurer un domaine expéditeur vérifié (le forfait Resend gratuit convient), mettre `YEM_PARENT_EMAIL_VERIFICATION_REQUIRED=true` dans Render, redéployer puis tester la livraison des e-mails.
- **Attention :** réactiver cette option ne certifie pas rétroactivement les adresses des comptes créés pendant le pilote. Les comptes pilotes devront être supprimés ou faire l'objet d'une vérification dédiée avant un usage avec de vrais dossiers.

## Mode test sans domaine (situation provisoire, lorsque l’activation e-mail est requise)

Lorsque `YEM_PARENT_EMAIL_VERIFICATION_REQUIRED=true` et `YEM_FROM_EMAIL=YEM <onboarding@resend.dev>`, l'API Resend peut envoyer des essais seulement aux destinataires autorisés pour le compte Resend. **Ne pas annoncer l'inscription publique opérationnelle** : les autres adresses peuvent être refusées en HTTP 403.

YEM affiche un avertissement « Mode test Resend » avant l'inscription. Si Resend refuse le courrier, la transaction de création du compte est annulée et un message explicite est affiché. Le parent ne reçoit ni compte actif ni droit d'accès à un enfant.

## Activation des inscriptions publiques sur le forfait gratuit

1. Disposer d'un domaine d'envoi que l'on contrôle, puis le déclarer et le **vérifier** dans Resend avec les enregistrements DNS demandés. Un abonnement payant Resend n'est pas nécessaire.
2. Dans le service YEM sur Render, configurer les variables d'environnement (jamais dans le dépôt) :

   ```env
   APP_ENV=production
   AUTH_PUBLIC_BASE_URL=https://<adresse-publique-YEM>
   YEM_RESEND_API_KEY=<clé-API-privée-Resend>
   YEM_EMAIL_BACKEND=accounts.email_backends.ResendEmailBackend
   YEM_FROM_EMAIL=YEM <notifications@<domaine-vérifié>>
   ```

3. Déployer le service avec `YEM_PARENT_EMAIL_VERIFICATION_REQUIRED=true`, contrôler `GET /api/v1/auth/parents/registration-status` : `email_registration_available=true`, `email_verification_required=true`, `email_test_mode=false`.
4. Avec une **nouvelle adresse de test autorisée**, créer un compte, vérifier la réception réelle, les indésirables, l'activation du lien avant 30 minutes et la connexion. Tester également un renvoi et un refus de livraison. L'état `email_registration_available` ne prouve pas la délivrabilité.
5. Contrôler la consommation Resend Free. Les liens d'activation, renvois et e-mails de réinitialisation consomment chacun du quota.

## Réponses publiques et sécurité

- Les inscriptions au format valide (création acceptée ou identifiant/e-mail déjà utilisé) reçoivent le même **HTTP 200** et le même message neutre. Cette mesure réduit l'énumération des comptes mais ne supprime pas tous les canaux auxiliaires (p. ex. temps de réponse).
- En cas d'échec technique de messagerie, YEM renvoie **HTTP 503** et annule la création ; il ne prétend pas qu'un e-mail a été envoyé.
- Le blocage anti-abus de 5 tentatives et les accès scolaires par contrôle humain restent inchangés.
- Un compte confirmé par e-mail n'obtient **aucun accès** au dossier d'un élève sans vérification du représentant légal par l'établissement.

**Sans domaine vérifié, conserver le mode pilote restreint et ne pas distribuer le formulaire d'inscription publique aux familles.** Aucune modification du code ne peut lever les restrictions de livraison imposées par Resend.

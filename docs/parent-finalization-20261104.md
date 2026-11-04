# YEM Parents — clôture technique du pilote Android (04/11/2026)

Dernière vérification : contrat PayCentral (initiation ULID / exemple webhook UUID), validation HMAC et isolation des transactions, et activation RLS des nominations scolaires 0018 avant déploiement.

Cette phase suit la PR #31 et s'appuie sur `0018_school_appointments`. Son développement est isolé des PR #26 (dossiers élèves), #33 (profils) et #36 (finance). **Ne pas modifier la comptabilité des frais de scolarité depuis le module de candidature.**

## 1. Compte parent et e-mail de validation

- `GET /api/v1/auth/parents/registration-status` indique si la messagerie transactionnelle est utilisable (sans révéler aucun secret).
- Le formulaire d'inscription est désactivé si SMTP n'est pas configuré.
- `POST /api/v1/auth/parents/resend-verification` renvoie un lien à un compte parent créé par inscription publique et toujours inactif. Réponse générique et limitation anti-abus ; on ne divulgue pas l'existence d'un compte.
- L'activation utilise un lien à durée de validité liée à `PASSWORD_RESET_TIMEOUT` (actuellement 30 min). Aucun droit d'établissement n'est créé automatiquement.

**À renseigner dans Render pour le service `yem-api`, par le propriétaire des accès SMTP :**

```text
AUTH_PUBLIC_BASE_URL=https://yem-api.onrender.com
YEM_SMTP_HOST=<serveur SMTP du fournisseur>
YEM_SMTP_PORT=587
YEM_SMTP_USER=<identifiant>
YEM_SMTP_PASSWORD=<secret>
YEM_FROM_EMAIL=<adresse expéditrice vérifiée>
YEM_SMTP_TLS=true
```

Le fournisseur SMTP et l'adresse d'expédition doivent réellement exister, être autorisés et être validés. Le code ne crée ni contrat marchand ni compte e-mail.

## 2. Frais de dossier et paiement en ligne

Le paiement de **candidature** est un objet séparé des `FeeCharge`/`FeePayment` de scolarité ; un succès ne crée ni élève ni inscription officielle, ni frais encaissés dans la caisse. Les rapprochements / affectations comptables feront l'objet d'une intervention contrôlée avec la PR #36 pour éviter une double comptabilisation.

- Montant XAF paramétrable par établissement, année scolaire et niveau, versionné avec contrôle de révision.
- La candidature conserve son montant au moment de la soumission (les changements futurs de tarifs ne modifient pas son montant).
- Chaque école configure **son propre compte marchand PayCentral** (jamais celui d'une autre école) : clé API + secret HMAC chiffrés, non renvoyés dans les réponses API.
- Les moyens Gabon disponibles dans l'adaptateur : Airtel Money, Moov Money. Disponibilité réelle à confirmer par l'opérateur et le prestataire.
- `GET /api/v1/schools/{school}/admission-gateway`, `POST` idem : uniquement personnel combinant droits admissions et finances.
- `GET/POST /api/v1/schools/{school}/admission-fees` : même politique.
- `POST /api/v1/parents/applications/{request}/pay` : génère une tentative locale unique, puis sollicite le prestataire. Double clic ou réseau incertain ne génèrent pas une nouvelle tentative tant que la précédente n'est pas définitivement échouée.
- `POST /api/v1/parents/paycentral/webhook` : route publique **uniquement pour un HMAC SHA256 valide**, puis comparaison référence, montant, devise et opérateur, en acceptant la différence documentée de format d'identifiant sur un webhook HMAC signé (contrôle strict d'identifiant conservé pour le statut API) ; gestion répétée idempotente.
- `POST /api/v1/parents/applications/{request}/payment-refresh` : statut réinterrogé **sur le serveur** avec la clé marchande, jamais accepté depuis une affirmation du navigateur.
- `GET /api/v1/parents/applications/{request}/payments` : compte propriétaire uniquement.
- `GET /api/v1/schools/{school}/admission-payments` : comptabilité ou gestion admissions autorisée de l'école.
- `GET /api/v1/parents/notifications` : événements d'admission et de paiement de la famille uniquement.

**Variables à configurer séparément :**

```text
YEM_PAYMENT_ENCRYPTION_KEY=<secret aléatoire de 48+ caractères, à conserver>
YEM_PAYMENTS_LIVE_ENABLED=false
```

Le chiffrement utilise cette clé d'environnement, pas une clé embarquée dans React. Sa perte empêche de relire les clés marchandes chiffrées. La valeur `false` est le mode par défaut et **interdit les paiements réels**.

Le directeur habilité prépare dans Admissions → Frais et paiements : école, année, niveau, montant, clé `sk_sandbox_...`, secret `whsec_...`, et inscrit `https://yem-api.onrender.com/api/v1/parents/paycentral/webhook` comme webhook dans le tableau de bord de **son** compte marchand.

Une validation payante en production exige en plus contrat/frais vérifiés, compte marchand **de l'école**, test réel sur un faible montant, clé `sk_live_...`, webhook live distinct et activation explicite par l'exploitant de `YEM_PAYMENTS_LIVE_ENABLED=true`. Ne pas activer sans confirmation du coût et des destinataires de fonds. Les clés live ne doivent jamais être consignées dans GitHub.

Documentation du prestataire : https://paycentral.gabondunumerique.com/site/docs/api.html ; https://paycentral.gabondunumerique.com/site/docs/webhooks.html . Les exemples servent à la construction de l'adaptateur ; seule une transaction réelle vérifiée confirme l'ouverture commerciale.

## 3. Installation Android

- Manifest PWA, thème YEM vert, `display: standalone`, `scope: /`.
- Icônes PNG de dimensions 192 et 512 générées au **build**, sans générateur externe. Source `frontend/generate-pwa-icons.mjs`.
- Service worker avec cache **uniquement** des assets publics et d'une page hors ligne. Aucune session, aucun document, aucune réponse `/api/` mis en cache.
- Sur Android, ouvrir `https://yem-api.onrender.com` dans Chrome → menu ⋮ → Installer / Ajouter à l'écran d'accueil ; le bouton intégré apparaîtra si Chrome expose l'invite d'installation.
- Notifications dans l'application : statuts et décisions à la demande ; alertes de navigateur lorsque l'application est ouverte et permission accordée. Les notifications **push en arrière-plan** restent indisponibles tant qu'un service Web Push avec authentification VAPID n'est pas configuré. Aucun push n'est simulé comme s'il était livré en arrière-plan.
- Ce déploiement n'est pas un APK signé et ne publie rien sur Google Play.

## 4. Tests de recette

Automatisation :
```bash
npm ci --ignore-scripts
npm test
npm run build
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test pedagogy accounts institutions
```

Scénarios de recette attendus : plusieurs parents, plusieurs écoles publiques/privées, niveau et capacité, inscription directe, concours, orientation, paiement espèces, initiation sandbox, succès HMAC, webhook falsifié, montant erroné, webhook en double, isolation, refus de lecture d'une école étrangère, aucun accès aux bulletins avant validation légale de la tutelle. Les tests automatisés utilisent une réponse prestataire **simulée par mock** ; jamais des fonds réels.

**Mise en production sûre :** revue PR, tests CI verts, migration Django, RLS et privilèges Supabase vérifiés pour toutes nouvelles tables, déploiement manuel Render, santé `/healthz` et `/readyz`, inspection logs, puis recette physique sur 1–2 établissements pilotes.

**Protection Supabase** : les tables Django sont privées pour `anon`/`authenticated`. Ne jamais réactiver les privilèges publics pour exposer les dossiers depuis le client PWA. Le navigateur communique seulement avec Django et ses permissions par établissement.

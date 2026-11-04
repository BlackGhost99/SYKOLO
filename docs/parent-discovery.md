# YEM Parents — phase 1, inscription des familles et recherche d'école

Cette livraison **étend** le module 15 existant ; elle ne remplace pas les bulletins, emplois du temps et absences déjà servis par les API sécurisées.

## Parcours opérationnel

1. Sur la page d'authentification, choisir **Créer un compte parent**. Les comptes sont globaux à YEM, sans privilège d'école. Un lien de validation e-mail active le compte (SMTP requis).
2. Le directeur / secrétariat autorisé ouvre **Admissions → Publication dans YEM Parents**, renseigne la ville, le quartier, le contact, les coordonnées publiques et coche **Publier**. Publication désactivée par défaut ; l'école doit d'abord être classifiée (maternelle, primaire, collège, lycée ou groupe) et ses cycles configurés.
3. Depuis l'espace parents (adapté à l'écran Android), le parent voit uniquement les écoles publiées, les classes ouvertes et un nombre de places *indicatif* basé sur les inscriptions actives.
4. Le parent enregistre un ou plusieurs profils d'enfants **privés** puis sélectionne une classe et une voie d'admission autorisée (inscription directe, concours, orientation). Le dossier arrive dans le même workflow administratif que les candidatures au guichet.
5. Le parent choisit pour l'instant **paiement en espèces sur place** (intention uniquement), consulte son statut dans **Mes demandes**, et suit le traitement administratif.
6. Lorsque l'école admet et inscrit officiellement l'élève, elle vérifie la qualité de responsable légal avant de lui donner accès à la scolarité ; cette étape de sécurité du module 15 reste obligatoire.

## Contrats API

- `POST /api/v1/auth/parents/register` puis `POST /api/v1/auth/parents/verify` : compte parent par e-mail vérifié.
- `GET /api/v1/parents/catalog` : écoles et classes volontairement publiées. Accessible sans compte.
- `GET/POST /api/v1/parents/family-children` : profils privés de chaque parent.
- `GET/POST /api/v1/parents/applications` : dépôts et statuts propres au parent connecté.
- `GET/POST /api/v1/schools/{id}/parent-listing` : publication réservée aux comptes avec `school.admissions.manage`.

Le dépôt de candidature crée une `AdmissionApplication` dans le système actuel, avec une relation propriétaire `ParentAdmissionRequest`. Le statut côté parent est consultable **uniquement** depuis son compte. Les dossiers scolaires d'un enfant restent protégés par les liaisons `GuardianAccountLink` vérifiées par l'école.

## Garanties et limites

- Aucune inscription ni place définitive n'est créée par une candidature ; la capacité est contrôlée à nouveau lors de l'inscription officielle.
- Aucune pièce d'identité de mineur n'est reçue par un endpoint public de cette phase.
- Les coordonnées de parent transmises dans une candidature ne donnent aucun droit d'accès automatique au dossier élève.
- Aucune transaction Mobile Money / carte n'est déclenchée : **payer en ligne est désactivé**, aucun reçu n'est créé par la demande en ligne. Le paiement réel reste dans le module caisse existant et doit être confirmé par le personnel autorisé.
- Pas encore d'application Android native ni de publication Play Store. L'interface React actuelle est responsive et utilisable dans le navigateur Android ; installabilité PWA/APK à tester et livrer séparément.
- Le déploiement nécessite la migration `0017_parent_discovery` après `0016_school_profiles`, `AUTH_PUBLIC_BASE_URL` et un fournisseur SMTP configuré et testé. Aucun nouvel abonnement n'est ouvert par cette PR.
- Avant mise en production : tests de charge sur les dépôts simultanés, anti-abus à renforcer à l'échelle de plusieurs IP, validation RGPD/local des données de mineurs, consentement et durée de conservation, tests réels smartphone.
- La PR 26 d'administration des inscriptions est indépendante ; résoudre ses conflits de migration avant de fusionner les chantiers en parallèle.

## Tests

```bash
python backend/manage.py test accounts.test_parent_signup institutions.test_parent_admissions institutions.test_parent_portal
python backend/manage.py makemigrations --check --dry-run
npm test
npm run build
```

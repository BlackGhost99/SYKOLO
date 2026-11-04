# YEM — mots de passe oubliés et récupération sécurisée

## Parcours A : récupération autonome (parent, enseignant, direction)

La page **Connexion → Mot de passe oublié** demande l'adresse e-mail du compte et appelle
`POST /api/v1/auth/password/reset/request`. Si la messagerie SMTP est configurée, YEM
envoie un lien dont la validité maximale est de **30 minutes**. L'API renvoie un message
identique que l'adresse existe ou non pour éviter la divulgation des comptes.

Le propriétaire ouvre le lien `/#/reset?uid=…&token=…` et définit un nouveau mot
de passe selon les règles Django. Le changement invalide l'ancien lien et les anciennes
sessions (contrôle de l'empreinte du mot de passe). **La MFA reste active** : une
réinitialisation de mot de passe ne donne pas accès aux facteurs TOTP ni aux codes
de secours.

### À configurer sur Render pour activer l'envoi

Aucune valeur de démonstration ne doit être utilisée en production.

| Variable d'environnement | Rôle |
|---|---|
| `AUTH_PUBLIC_BASE_URL` | `https://yem-api.onrender.com` ou domaine YEM public final |
| `YEM_SMTP_HOST` | Hôte SMTP du fournisseur choisi |
| `YEM_SMTP_PORT` | Port SMTP autorisé par l'hébergeur / fournisseur |
| `YEM_SMTP_USER` | Identifiant SMTP |
| `YEM_SMTP_PASSWORD` | Mot de passe ou clé SMTP privée |
| `YEM_FROM_EMAIL` | Adresse d'expédition vérifiée |
| `YEM_SMTP_TLS` | `true` pour connexion STARTTLS (selon fournisseur) |

Le code calcule `PASSWORD_RESET_ENABLED` depuis cette configuration en déploiement.
**Configurer le nom des variables sans un service d'envoi fonctionnel ne suffit
pas** : tester l'envoi réel, la réception, la protection du domaine expéditeur,
le taux de délivrabilité, les retours d'erreur et les éventuelles restrictions
de sorties réseau de l'hébergeur.

En attendant, le bouton utilisateur reste indisponible si la messagerie manque.
Ceci est volontaire : YEM ne doit pas simuler un envoi.

## Parcours B : assistance super-administrateur — comptes scolaires

Console YEM → **Utilisateurs & rôles** → choisir l'école → rechercher le compte →
**Mot de passe oublié**.

Conditions :
- Session du **super-administrateur** déjà authentifiée avec MFA.
- Reconfirmation de son propre mot de passe, soumise à limitation des tentatives.
- Motif obligatoire et attestation de contrôle de l'identité du titulaire.
- Compte membre de l'établissement choisi et actif ; aucun reset des comptes
  `is_staff` / `is_superuser` par cette voie.
- L'opérateur reçoit **uniquement un lien de réinitialisation** (jamais le mot de
  passe existant ni un secret MFA) ; il le remet par canal privé à la personne.
- Le lien est affiché seulement dans cette interaction, avec en-têtes HTTP
  `no-store` ; aucune URL / token n'est inclus dans les journaux d'audit.
- La personne choisit son propre nouveau mot de passe et le lien devient invalide
  après son utilisation.

API : `POST /api/v1/auth/password/admin-reset` avec
`{school_id, member_id, reason, current_password}`.

## Parcours C : assistance super-administrateur — comptes parents

Console YEM → **Utilisateurs & rôles** → **Récupération d'un compte parent**.

Il faut entrer **l'identifiant exact ET l'adresse e-mail exacte** du compte,
avec le motif, la confirmation du mot de passe super-admin et le contrôle
d'identité effectué hors application. L'API vérifie que le compte est actif,
non privilégié et qu'il n'appartient pas au personnel d'une école.

API : `POST /api/v1/auth/password/admin-parent-reset` avec
`{username, email, reason, current_password}`.

Un compte parent inactif, en attente de confirmation d'e-mail, doit d'abord
être activé par le workflow de vérification prévu pour ce compte. Le reset de
mot de passe n'est pas un moyen de contourner cette vérification.

## Règles importantes

- Les liens contiennent des jetons sensibles. Ne pas les afficher dans les
  journaux, les captures d'écran, un groupe de messagerie ou un ticket public.
- Les liens de récupération ne doivent jamais être utilisés pour **désactiver
  automatiquement la MFA**.
- Perte simultanée du mot de passe et du facteur MFA : traitement exceptionnel
  distinct, avec contrôle d'identité renforcé et journalisation.
- Les comptes super-admin ne sont pas réinitialisables par la console
  super-admin : rétablissement exceptionnel hors application après vérification
  de l'identité du propriétaire du système.
- Une personne peut appartenir à plusieurs établissements avec un seul compte ;
  le mot de passe du compte reste **global**, même si l'initiateur du reset
  l'a retrouvé via une école.
- L'application ne stocke pas de mot de passe en clair et n'en affiche aucun
  à l'opérateur.

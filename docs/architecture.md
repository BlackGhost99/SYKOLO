# Architecture YEM

## Module 01

Monorepo : `backend/config` pour les réglages d'environnement et le transport Django, `backend/accounts` pour l'identité extensible, `backend/pedagogy` pour le moteur indépendant et ses modèles de départ, `frontend` pour React/Vite. L'image Docker compile React dans une première étape, puis sert le bundle et l'API depuis Django/Gunicorn/WhiteNoise sur une même origine. Le processus démarre par les migrations, puis Gunicorn reçoit directement SIGTERM.

PostgreSQL 17 est requis en staging et en production. SQLite sert uniquement de solution locale de démarrage et de test rapide. Les migrations initiales installent un modèle utilisateur extensible avec identifiant UUID ; aucun endpoint de connexion n'est encore exposé. La CI vérifie la même migration avec PostgreSQL.

Les variables APP_ENV, DATABASE_URL, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DJANGO_DEBUG et APP_TIME_ZONE sont externes au code. Les booléens sont explicitement interprétés. Environnements distincts : bases et clés différentes en dev, staging et production. Aucun accès aux ressources d'autres projets n'est requis.

## Contrat de configuration v1

`schemaVersion`, `name`, `scale {kind,max}`, `precision`, `missing`, `bands [{min,label,value}]`, `report {showScore,showLabel}`, `notification {enabled,below,message}`.

Le moteur Python est la seule autorité de validation et de calcul. React appelle l'API pour les résultats et avant sauvegarde/import/export. Les calculs utilisent Decimal ; l'arrondi à moitié supérieure n'affecte que le résultat affiché. Seuils et alertes utilisent la valeur non arrondie. Les bandes couvrent [0,100] par seuil inférieur inclus et seuil suivant exclu ; le dernier inclut 100. Les seuils et libellés sont uniques. Les équivalences des catégories se situent dans leur bande.

Les notes numériques sont normalisées en pourcentage avant pondération. Les coefficients sont strictement positifs. Une absence est exclue ou compte comme zéro selon le profil. Si toutes les notes sont exclues, le résultat est absent. Les modèles se trouvent dans un fichier JSON séparé et sont copiés avant modification. Aucun seuil de réussite, barème national, tarif ou rôle institutionnel obligatoire n'est fixé par le moteur.

## Modules 02 et 03 à développer

Le module 02 développe l'authentification par session Django (CSRF), l'identité UUID, MFA TOTP chiffré et anti-rejeu, les codes de secours à usage unique, la récupération email avec jeton expirant et le journal des événements d'authentification. Les rôles et permissions métier propres aux établissements, dépendants de la future adhésion d'école, arrivent au module 03. Les protections de transport déjà présentes (CSRF, CSP, hôtes explicites, HTTPS, cookies sécurisés, limites de taille) constituent le socle du module 02.

Le module 03 introduira organisation/fondateur, école, campus, année et cycles configurables, adhésions et isolation inter-écoles. Fondateur, directeur, comptable, secrétaire, enseignant, parent et apprenant auront des droits contrôlés côté serveur par action et périmètre. Un fondateur ne doit pas être assimilé automatiquement à un directeur.

Les configurations institutionnelles seront versionnées par école/année/cycle/classe avec héritage et dérogations explicites. Un bulletin publié conservera un instantané de sa configuration et de ses résultats. Prévoir audit et concurrence optimiste. Le stockage local de l'atelier sera alors remplacé par une persistance protégée, sans changer le moteur.

## Limites de la livraison

Le laboratoire est public et utilise des données fictives ; ses profils restent uniquement dans le navigateur. La présence de PostgreSQL et du modèle utilisateur initial ne signifie pas que l'authentification, le multi-établissements ou le stockage institutionnel sont disponibles. Le serveur ne conserve ni profil pédagogique ni dossier élève à ce stade.

## Sécurité des comptes (module 02)

Pas d'inscription publique : le premier exploitant utilise `python backend/manage.py createsuperuser`, puis des invitations et adhésions par école seront livrées au module 03. Les comptes ne donnent aucun droit sur les données scolaires. Les sessions utilisent HttpOnly, SameSite=Lax, rotation CSRF et durée maximum de huit heures. Les échecs de connexion sont limités par empreinte HMAC de l'adresse serveur et de l'identifiant sur une fenêtre de 15 minutes, persistée en base ; dans une future infrastructure proxy, revoir l'extraction de l'IP derrière un proxy de confiance. L'audit stocke type d'action, utilisateur identifié le cas échéant, horodatage et empreinte IP, jamais mot de passe, code TOTP ou adresse IP brute. Le journal de l'application n'est pas une archive WORM.

Le secret TOTP est chiffré par Fernet avec une clé indépendante `MFA_ENCRYPTION_KEY` (32 caractères minimum en staging/production). La rotation de cette clé nécessite une procédure de migration des secrets. Les codes de secours sont stockés sous empreinte HMAC et consommés une seule fois. Récupération de compte : Django PasswordResetTokenGenerator, validité 30 minutes et tokens invalidés après changement du mot de passe. La remise à zéro exige un serveur SMTP et une URL HTTPS en staging et production. Une migration complète multi-écoles et les permissions métiers restent à développer.

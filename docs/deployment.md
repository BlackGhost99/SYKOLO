# Déploiement et environnements

## Mode actuel : aperçu local uniquement

Les Blueprints définissent uniquement de nouvelles ressources YEM dans My Workspace, région Frankfurt. Production : `render.yaml`, branche main, service `yem-production`, base `yem-db-production`. Staging : `deploy/render.staging.yaml`, branche staging, service `yem-staging`, base `yem-db-staging`.

Chaque service utilise Docker, le plan web gratuit de démonstration, le contrôle HTTP `/readyz`, une clé secrète générée par Render et la connexion interne de sa propre base PostgreSQL 17. Chaque base est indépendante, avec 1 Go, plan `0.1c-256mb`, sans accès externe (`ipAllowList: []`). Les déploiements automatiques attendent les contrôles CI.

Les plans de base sont payants. Le seul emplacement PostgreSQL gratuit autorisé dans My Workspace est déjà occupé par une base Gaboshop ; aucune ressource Gaboshop ne doit être réutilisée ou modifiée pour YEM. Les coûts exacts doivent être revus au Dashboard avant création. Ne pas appliquer le Blueprint sans approbation du propriétaire.

Le propriétaire a choisi de conserver uniquement l'aperçu local pour le moment. Aucun service ni base Render YEM n'est créé. Les Blueprints restent des configurations préparées ; ne pas les appliquer sans nouvelle demande explicite.

## Étapes après validation

1. Confirmer le budget et la création de la base et du service production ; staging reste une création distincte à approuver.
2. Vérifier les contrôles de la PR et fusionner le code validé sur main.
3. Créer une branche staging à partir de la même version validée si le staging est approuvé.
4. Appliquer le Blueprint correspondant depuis le dépôt GitHub ; ne jamais copier les URL de connexion ou clés dans le dépôt, un message ou un journal.
5. Attendre le statut terminal live du déploiement et comparer le commit de `/healthz` au commit fusionné.
6. Vérifier `/readyz`, la page React, les modèles et un calcul JSON avec cookie/en-tête CSRF. Consulter les logs runtime pour détecter une erreur.

Les deux Blueprints sont validés contre le schéma JSON officiel. Le CLI Render n'est pas installé localement : la validation sémantique côté Render doit également être effectuée avant application. Le poste local n'a pas Docker ; la construction et le test du conteneur sont exécutés par la CI Linux avec PostgreSQL.

## Variables

| Variable             | Source                                                               |
| -------------------- | -------------------------------------------------------------------- |
| APP_ENV              | development, test, staging ou production                             |
| DATABASE_URL         | référence interne fromDatabase, différente pour chaque environnement |
| DJANGO_SECRET_KEY    | secret généré, distinct par environnement, 50 caractères minimum     |
| DJANGO_ALLOWED_HOSTS | hôtes explicites ; le nom Render injecté est ajouté automatiquement  |
| DJANGO_DEBUG         | false en staging/production ; activation refusée                     |
| APP_TIME_ZONE        | facultatif, Africa/Libreville par défaut                             |
| PORT                 | injecté par Render ; 8000 par défaut dans Docker                     |

Les migrations sont exécutées au démarrage avant Gunicorn. Pour les futures migrations risquées, prévoir une étape de migration dédiée et des changements compatibles avec l'ancienne version ; le mécanisme actuel convient aux seules migrations initiales. Un retour au code précédent ne restaure pas une base de données.

## Limites des plans

Le service web gratuit se met en veille et utilise le quota mensuel partagé de My Workspace. Il sert ici à démontrer les fondations, pas à exploiter des données scolaires réelles. La mise en production métier sera conditionnée aux modules sécurité/isolation, à un dimensionnement et à une politique de sauvegarde adaptés.

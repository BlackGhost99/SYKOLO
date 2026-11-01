# YEM

Gestion scolaire modulaire, de la maternelle au supérieur.

Modules 01 et 02 : architecture et sécurité des comptes (module 02 en vérification). Django 5.2 LTS/API, React 19, PostgreSQL 17, Docker, CI GitHub et configurations Render séparées. Version 0.3.0 (branche de développement).

## Lancer en local

Avec Docker et Docker Compose :

```sh
docker compose up --build
```

Ouvrir http://localhost:3000. PostgreSQL possède un volume local nommé ; les valeurs de connexion de Compose sont réservées au développement.

Sans Docker (Python 3.13 et Node 24) :

```sh
python -m venv .venv
# Windows : .venv/Scripts/python.exe ; Linux : .venv/bin/python
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm ci --ignore-scripts
npm run build
.venv/Scripts/python.exe backend/manage.py collectstatic --noinput
.venv/Scripts/python.exe backend/manage.py migrate
.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:3000
```

Sans DATABASE_URL, le développement local utilise SQLite uniquement pour faciliter le démarrage. Staging et production refusent de démarrer sans PostgreSQL, sans clé secrète dédiée ou avec DEBUG activé. Pour le rechargement React : lancer Django sur 8000 puis `npm run dev` sur 5173.

## Vérifier

```sh
npm test
npm run build
.venv/Scripts/python.exe backend/manage.py check
.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe backend/manage.py test pedagogy
```

La CI utilise PostgreSQL 17, exécute les migrations, les tests backend/frontend, les contrôles Django de production, construit Docker et vérifie le conteneur avec PostgreSQL. Elle valide aussi les deux Blueprints Render contre le schéma officiel.

## Démonstrateur pédagogique

Huit modèles éditables : notes sur 10/15/20/100, pourcentages, lettres, appréciations et compétences. Maximum libre, seuils, libellés, équivalences, coefficients, décimales, absences, aperçu de bulletin et prévisualisation d'alerte. Les seuils des modèles sont des exemples, pas des normes institutionnelles.

Les calculs et la validation passent par Django. Les profils restent dans le navigateur et s'importent/s'exportent en JSON. Le module 02 ajoute connexion sur invitation/administration, MFA TOTP, codes de secours, récupération de mot de passe par email, limites d'essais et audit. Aucun dossier élève, paiement ni bulletin officiel n'est livré. Données fictives uniquement.

## Environnements et API

- `/healthz` : version, commit, environnement et stack.
- `/readyz` : disponibilité de la base avec `SELECT 1` ; contrôle de santé Render.
- GET `/api/v1/presets` : modèles et cookie CSRF.
- POST `/api/v1/policies/validate` et `/api/v1/evaluate` : JSON et en-tête `X-CSRFToken` requis.

Voir [déploiement](docs/deployment.md), [architecture](docs/architecture.md) et [ordre des modules](docs/modules.md). Les configurations Render sont prêtes à réviser ; aucune ressource YEM n'est actuellement créée sur Render. Le module 02 n'est pas un déploiement. Les comptes initiaux sont provisionnés par la commande Django `createsuperuser` (aucune inscription libre). La récupération par email ne fonctionne en environnement déployé qu'après configuration SMTP HTTPS.

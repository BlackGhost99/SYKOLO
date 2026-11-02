# YEM

Gestion scolaire modulaire, de la maternelle au supérieur.

Modules 01 et 02 fusionnés ; module 03 multi-établissements en développement. Django 5.2 LTS/API, React 19, PostgreSQL 17, Docker, CI GitHub et configurations Render séparées. Version 0.4.0 (phase 1, branches intégrées après validation).

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

## Module 03 — organisations et écoles

Les nouvelles API sont sous `/api/v1/organizations` et `/api/v1/schools`. L'utilisateur authentifié crée une organisation et devient fondateur. Le fondateur crée une école puis nomme **explicitement** un directeur parmi les comptes existants. Fondateur n'est jamais directeur automatiquement. Chaque école possède ses rôles modifiables, ses membres, ses propres configurations et son audit. Une école étrangère répond 404 même si son UUID est connu. L'héritage des réglages (établissement/année/cycle/niveau/classe) est versionné avec verrouillage optimiste et contrôle des barèmes par le moteur Django. Cette base ne contient ni dossiers élèves ni notes officielles.

L'interface de la phase 1 affiche les organisations, écoles, affectations et paramètres d'école après connexion. Les permissions métier et configurations fines sont pilotées par l'API. L'atelier public reste séparé des données scolaires réelles.

## Module 04 — Structure académique

Années scolaires et dates, cycles et niveaux, filières facultatives, classes par année et périodes configurables sans découpage obligatoire (semestres, trimestres ou autres). Les objets sont séparés par école et contrôlés avec les droits `school.academic.read` et `school.academic.manage`. Les modifications exigent une révision optimiste ; suppression physique interdite, utilisez `active=false`. API documentée dans `docs/academic.md`.

## Module 05 — Élèves et inscriptions

Dossier élève par école, responsables légaux, inscriptions et réinscriptions par année/classe, capacité de classe, mutations historisées et droits d'accès aux informations personnelles. Aucune publication de données personnelles dans le démonstrateur public. Voir docs/students.md.

## Module 06 — Personnel et affectations

Fiches du personnel indépendantes des comptes (association facultative à un compte existant membre de l'école), affectations à des classes/années et responsabilités configurables, contrôles de rôles, révisions et archivage. API privée et interface React ; voir docs/staff.md.

## Module 07 — Matières et programmes

Matières par établissement, cours et coefficients configurables par classe/année, unités de programme et affectation des enseignants autorisés. Accès API isolé et interface React ; voir docs/curriculum.md.

## Module 08 — Évaluations et notes

Évaluations de cours liées aux barèmes configurés, copie immuable des règles, saisie de notes numériques/lettres/compétences, normalisation par le moteur Django et droit d'édition par enseignant affecté. Données non publiées tant que le module bulletin n'est pas livré ; voir docs/assessments.md.

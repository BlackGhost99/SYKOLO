# SYKOLO

Gestion scolaire modulaire, de la maternelle au supérieur. Version 0.1.0 : fondations et atelier de configuration pédagogique.

## Démarrer

Node.js 24.11.1 (sans dépendance externe).

```sh
npm ci --ignore-scripts
npm test
npm run check
npm start
```

Ouvrir http://localhost:3000. `PORT` est configurable ; écoute sur `0.0.0.0` pour Render.

## Premier module livré

- Huit modèles éditables : notes sur 10/15/20/100, pourcentages, lettres, appréciations, compétences.
- Maximum libre, seuils, libellés, équivalences, coefficients, décimales et absences.
- Calcul pondéré, aperçu de bulletin et prévisualisation d’une notification sous un seuil configurable.
- Enregistrement de plusieurs profils dans ce navigateur, réouverture, import/export JSON validé.
- API stateless : GET `/api/v1/presets`, POST `/api/v1/policies/validate`, POST `/api/v1/evaluate`.
- Santé/version/commit : GET `/healthz`.

Les seuils des modèles sont des exemples, pas des normes scolaires. Les règles institutionnelles sont des données validées ; aucun seuil de réussite n’est imposé par le moteur.

## Limites explicites

Atelier de démonstration, sans compte ni dossier élève. Les profils sont conservés dans le stockage local du navigateur, sans synchronisation serveur. Exporter un JSON pour sauvegarder ou transférer un profil. Les notifications ne sont pas envoyées. L’aperçu n’est pas un bulletin officiel ni un générateur PDF. Ne pas saisir de données personnelles.

## Déploiement Render

Web service Node, dépôt `BlackGhost99/SYKOLO`, branche `main`, plan `free`, région `frankfurt`.

- Build : `npm ci --ignore-scripts && npm run check && npm test`
- Start : `npm start`
- Node : `.node-version`
- Endpoint à vérifier après déploiement : `/healthz` ; son `commit` doit correspondre au commit fusionné.

Pas de base de données ni de disque requis pour ce premier module. La mise en veille du plan gratuit peut ralentir la première ouverture. Configurer `/healthz` comme contrôle HTTP dans le Dashboard ; le contrôle TCP de Render s’applique par défaut.

## Organisation

- `src/domain/` : moteur pur et modèles de départ ; partagé entre navigateur et API.
- `src/server.mjs` : transport HTTP, validation, taille des requêtes et fichiers publics autorisés.
- `public/` : interface accessible et responsive, sauvegarde locale, aucune insertion HTML de contenu importé.
- `test/` : scénarios métier et intégration HTTP.
- `docs/architecture.md` : contrats, limites et trajectoire multi-écoles.

Travail par module sur une branche `feat/…`, tests, PR vers `main`, revue et fusion après validation, puis contrôle du commit réellement déployé.

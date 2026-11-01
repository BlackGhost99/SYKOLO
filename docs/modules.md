# Ordre des modules

La liste ci-dessous reprend uniquement les trois modules communiqués par le porteur du projet. Les quinze autres ne sont pas encore spécifiés dans ce dépôt.

| Module                                     | Périmètre                                                                                     | État                                                                                                      |
| ------------------------------------------ | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 01 — Architecture et déploiement           | GitHub, Django/API, React, PostgreSQL, Docker, dev/staging/production, Render et CI/CD        | Code et configurations en validation ; déploiement Render soumis à approbation de création des ressources |
| 02 — Authentification et sécurité          | Connexion, récupération de compte, MFA, permissions par rôle, audit et protection des données | À développer sur une nouvelle branche après validation du module 01                                       |
| 03 — Multi-établissements et configuration | Isolation entre écoles, identité visuelle, paramètres et moteur hiérarchique                  | À développer après le module 02                                                                           |

Le démonstrateur pédagogique livré avec le module 01 est un banc d'essai du moteur configurable, sans comptes d'école ni données réelles. Il ne constitue pas la livraison du module 03.

Chaque module suit le même cycle : branche dédiée, code, tests, commit/push, PR, validation, fusion sur main, déploiement Render puis vérification du SHA live. Le staging reçoit uniquement une version validée et utilise sa propre base et sa propre clé.

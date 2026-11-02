# Ordre des modules

La liste ci-dessous reprend uniquement les trois modules communiqués par le porteur du projet. La feuille de route générale comprend 18 modules ; seuls les trois premiers sont suivis ici dans le détail technique.

| Module                                     | Périmètre                                                                                     | État                                                                                                      |
| ------------------------------------------ | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 01 — Architecture et déploiement           | GitHub, Django/API, React, PostgreSQL, Docker, dev/staging/production, Render et CI/CD        | Code et configurations en validation ; déploiement Render soumis à approbation de création des ressources |
| 02 — Authentification et sécurité          | Connexion, récupération de compte, MFA, permissions par rôle, audit et protection des données | Développé sur feat/module-02-identity-security, en attente de validation CI/PR                                       |
| 03 — Multi-établissements et configuration | Isolation entre écoles, identité visuelle, paramètres et moteur hiérarchique                  | En développement sur feat/module-03-schools-isolation, validation CI/PR attendue                                                                           |

Le démonstrateur pédagogique livré avec le module 01 est un banc d'essai du moteur configurable, sans comptes d'école ni données réelles. Il ne constitue pas la livraison du module 03.

Chaque module suit le même cycle : branche dédiée, code, tests, commit/push, PR, validation, fusion sur main, déploiement Render puis vérification du SHA live. Le staging reçoit uniquement une version validée et utilise sa propre base et sa propre clé.


## Phase 2

04 — Structure académique : années, cycles, niveaux, filières, classes et périodes ; en validation sur feat/module-04-academic-structure.

10 — Conseils et décisions scolaires configurables ; rectificatifs de bulletins audités (en développement).

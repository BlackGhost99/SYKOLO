# Fonctions, délégations et connexion par établissement

## Organisation et droits

Le catalogue suit les cycles ouverts : maternelle, primaire, collège, lycée général, technique et groupe scolaire. Les censeurs principal, des études et de la vie scolaire complètent les fonctions existantes. L'établissement peut activer toutes, certaines ou aucune fonction dans Personnel > Comptes et accès. Une personne peut exercer plusieurs fonctions ; aucun poste ne doit obligatoirement être pourvu. Désactiver une proposition conserve les affectations historiques.

Les fonctions déclarées sur les comptes, comme les nominations de l'organigramme, ne confèrent aucun droit. Les rôles applicatifs existants sont conservés comme ensembles de permissions explicitement administrés. Les fonctions d'un compte existant et ses rôles supplémentaires peuvent être remplacés depuis le même écran.

Une délégation donne une liste explicite de permissions à un compte actif de la même école, avec motif, auteur, éventuelle fonction remplacée et échéance facultative. Elle peut couvrir un poste vacant sans créer de personne fictive. Le retrait conserve le dossier avec auteur, date et motif. Le serveur recalcule les droits à chaque requête : le retrait et l'expiration prennent effet sans reconnexion. Les droits provenant d'autres délégations ou rôles restent actifs.

Les délégations ne peuvent pas fabriquer d'autres administrateurs. Le délégant doit administrer les rôles et posséder les droits transmis, ou être propriétaire de l'organisation. Les attributions financières restent réservées au propriétaire ; encaissement et validation/annulation ne peuvent pas être réunis par une délégation. Les contrôles existants interdisant l'approbation de sa propre caisse et de ses propres justificatifs restent en place, y compris en cas de cumul de rôles.

## Connexion

L'espace établissement demande le code permanent de l'école (son UUID, affiché dans la console et les comptes et accès), puis l'identifiant et le mot de passe. La connexion plateforme est séparée par `/#/admin` et exige un superadmin ; les opérations plateforme conservent leur exigence MFA. Le parcours parents garde son accès distinct.

La table SchoolLogin impose l'unicité (école, identifiant). Deux écoles peuvent créer `directeur1` avec le même mot de passe : elles obtiennent deux comptes distincts. Le nom interne du compte peut différer de l'identifiant affiché. Une session scolaire ne peut appeler aucune route d'une autre école ni les routes d'organisations ou de plateforme. Un changement d'école demande une nouvelle connexion ; la liste des écoles est limitée au contexte de connexion.

## Migration et continuité

0023 ajoute les identités locales, fonctions facultatives et délégations. Elle recopie les identifiants des membres et propriétaires existants sans modifier les UUID utilisateurs, mots de passe, appartenances, élèves ni écritures financières. Les comptes historiquement partagés entre plusieurs écoles restent partagés pour préserver leurs données, avec une identité locale par école et une session limitée à l'école sélectionnée. Les nouveaux comptes créés par école sont distincts.

Les anciennes sessions sont fermées lors de la migration pour imposer la sélection d'établissement. Les utilisateurs doivent se reconnecter, les superadmins par Administration plateforme et les parents par Parents. 0024 ajoute le détail des modifications de fonctions/rôles dans l'audit. Les délégations conservent leur historique complet et les événements d'audit pointent vers leur identifiant.

## Intégration

Travail isolé dans artifacts/yem-functions-work, branche codex/school-functions-tenant-login. Base : main 7efe032, avec le correctif de sécurité 6775f39 déjà présent dans audit-main (autorité indépendante du propriétaire pour les attributions financières). Les dossiers et branches des autres chats n'ont pas été modifiés. Les PR #26 et #33 restent indépendantes, sans fusion ni écrasement.

Le service Render yem-api était sur aa84e0f à l'inspection ; son déploiement automatique est désactivé. Le service statique yem-pc-preview suit main automatiquement. Attendre la CI PostgreSQL, les migrations et le test Docker avant la fusion et le déploiement manuel de yem-api. Vérifier /healthz, /readyz, l'interface et les journaux après passage live. Un retour au code précédent ne restaure pas la base ; les migrations sont additives, mais les anciennes sessions restent fermées.

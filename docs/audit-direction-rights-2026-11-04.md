# Audit des droits effectifs de la direction — YEM

Date : 4 novembre 2026 (Africa/Lagos). Dépôt : BlackGhost99/SYKOLO.
Base auditée : main, `7efe032b3dfd3b281a04af62a68061bf07a9c995` (PR #42).
Correctifs proposés sur `codex/audit-direction-rights`, dans une copie indépendante du chantier local.

## Conclusion et preuve du décalage de production

La capture de « directrice 1 » est cohérente avec la version réellement déployée.
Render, espace My Workspace confirmé par l’utilisateur, service yem-api
`srv-dbkbfde1egvs739jacug`, annonce le déploiement live
`dep-dblobtt9fdbs73cbj1k0` du commit `aa84e0fcb144330d4175201157152175614c058f`
(PR #41), terminé le 4 novembre à 20:26:03, heure de Lagos. Auto-déploiement : désactivé.
La PR #42 n’est donc pas le code déclaré live lors de la vérification.

À ce commit déployé, `ROLE_TEMPLATES` donne bien `sorted(PERMISSIONS)` à
`direction` : tarifs, encaissements et annulations sont tous inclus. Ce n’est pas
une escalade : ce sont des pouvoirs explicitement attribués. Le précédent constat
« tout est corrigé » confondait fusion sur main et livraison en production.
La configuration exacte en base du compte « directrice 1 » n’a pas été lue : on ne
prétend pas connaître ses personnalisations, ni avoir effectué un encaissement réel.
Aucune écriture en production, aucun déploiement.

## Résolution réelle des droits sur main

Sources : `backend/institutions/services.py`, `views.py`, `school_functions.py`,
`organization_views.py`, `platform_views.py`, `accounts/password_admin_views.py`.

- Le libellé Direction et le badge Économe ne sont pas des contrôles d’accès.
- Les droits sont l’union du rôle principal et des `additional_roles` appartenant
  à la même école, sur un SchoolMember actif dont le rôle principal appartient
  lui-même à l’école. Les rôles supplémentaires étrangers sont ignorés.
- Les modèles sont éditables : le code `direction` n’impose pas un plafond immuable.
- Sur main, direction a toutes les permissions du catalogue SAUF finance.manage,
  finance.receive, finance.reverse et finance.deposit. Elle conserve finance.read,
  finance.approve, members.write et roles.manage, ainsi que de larges pouvoirs
  pédagogiques et administratifs. La séparation financière ne limite pas ces autres fonctions.
- Les nominations d’organigramme (`SchoolAppointment`) utilisent
  school.organization.manage. Elles n’accordent aucune permission API et ne sont
  pas les affectations SchoolMember/SchoolRole. Les portées par cycle de ces
  nominations ne réduisent pas l’union des droits d’un rôle scolaire.
- Propriétaire correspond à OrganizationMember.role=founder, pas à un libellé de
  SchoolRole. Il bénéficie de members.write et peut nommer des rôles au-delà de
  ses droits courants. Il peut se nommer lui-même et cumuler des fonctions.
  Cette autorité explicite est une frontière de confiance, pas une escalade.
  Il n’a pas implicitement les droits financiers ou roles.manage.
- Une direction seule ne devient pas founder par les endpoints de membres ou
  de rôles. Un rôle personnalisé nommé « propriétaire » ne crée pas cette qualité.
- Les endpoints plateforme exigent is_superuser ET une session MFA vérifiée.
  Les réinitialisations administratives exigent aussi la réauthentification et
  ne sont pas accessibles à la direction. Aucun contournement par ces voies identifié.

## Matrice financière du rôle direction standard

Toutes les permissions ci-dessous commencent par `school.finance.`.
Les routes sont relatives à `/api/v1/schools/<school>/finance/`.

| Action | Contrôle serveur sur main | Direction seule sur main | Version live #41 |
| --- | --- | --- | --- |
| Lire tarifs, frais, reçus, relevés | read | Oui | Oui |
| Créer/modifier tarifs (`schedules`) | manage | Non | Oui |
| Affecter un frais (`charges`) | manage | Non | Oui |
| Recevoir (`payments`, `batches`) | receive | Non | Oui |
| Annuler (`payments/<id>/void`) | reverse | Non | Oui |
| Déclarer sa caisse (`cash/closings`) | receive | Non | Oui |
| Approuver une clôture | approve | Oui, autre compte déclarant | reverse, autre compte déclarant |
| Déclarer remise/dépôt (`closings/<id>/transfers`) | deposit | Non | Fonction absente |
| Approuver remise/dépôt | approve | Oui, autre compte déclarant | Fonction absente |

Les endpoints d’admission pour la passerelle et les frais demandent ensemble
admissions.manage et finance.manage : la direction standard sur main ne configure
pas ces paiements. Les webhooks de paiement relèvent d’un autre mécanisme,
ils ne deviennent pas accessibles par un rôle direction.

L’annulation sur main rejette recorded_by == request.user et bloque les espèces
après déclaration de caisse. Les clôtures et transferts rejettent submitted_by ==
request.user. Les clôtures contrôlent aussi le total courant ; remises et dépôts
ont leurs limites de fonds et contrôles d’état. Ce sont des contrôles par compte,
pas une preuve d’indépendance des personnes physiques.
Il n’existe pas d’interdiction générale « auteur du tarif != caissier » : une personne
cumulant tarification et econome peut configurer puis encaisser. La restriction
porte sur l’annulation de son propre paiement et sur l’approbation de ses propres
clôtures/transferts, pas sur tout cumul de fonctions ou toute chaîne financière.

## Escalades testées et résultat sur main

Les écritures de membres, la création de comptes et les créations/modifications
de rôles comparent les permissions proposées à effective_permissions de l’acteur,
sauf l’exception founder sur les nominations et créations de comptes.

| Tentative direction seule | Résultat |
| --- | --- |
| PATCH de son rôle avec finance.receive/manage/reverse/deposit | 403 |
| Création d’un rôle contenant un de ces droits absents | 403 |
| S’assigner econome en rôle principal | 403 |
| Ajouter econome, tarification ou comptabilite à sa propre affectation | 403 |
| Déléguer à un autre un droit qu’elle ne possède pas | 403 |
| Accéder directement aux écritures financières interdites | 403 avant validation métier |

Aucune escalade séquentielle ajoutant un droit financier absent n’a été démontrée
pour la direction seule sur ce main. Posséder roles.manage ne permet pas d’écrire
n’importe quelle permission : oublier le contrôle d’inclusion conduirait à un faux
positif d’audit. Une délégation founder ou des rôles supplémentaires préexistants
peuvent en revanche rendre une directrice aussi puissante qu’avant, volontairement.

## P1 — La direction peut fabriquer un approbateur qu’elle contrôle

Sur main avant ce correctif :

1. Direction possède members.write et finance.approve.
2. POST `schools/<id>/users`, rôle direction, identifiant/email libres et mot de
   passe choisi par l’acteur : 201, car tous les droits demandés sont déjà les siens.
3. Le second compte possède finance.approve. La directrice connaît son mot de passe.
4. Une clôture déclarée par le premier compte est rejetée en auto-approbation (403),
   mais acceptée sous le second compte (200).

Le test prépare une clôture à total nul pour isoler l’approbation sans toucher à
un paiement. Pour une chaîne d’encaissement réelle, le premier compte doit avoir
reçu explicitement receive (par exemple via econome). Direction seule ne peut pas
obtenir ce droit par cette démonstration. Le même principe de comptes contrôlés
menace les contrôles de transferts ; reverse nécessite une délégation supplémentaire.

Il s’agit d’un contournement de séparation des tâches et d’une délégation de
contrôle insuffisamment indépendante, pas d’une acquisition de permissions
initialement absentes. Ne pas assimiler union de rôles, droits effectifs et droit
d’approuver sa propre transaction.

Correctif proposé : les fonctions financières manage/receive/reverse/approve/deposit
ne sont plus délégables par un administrateur scolaire non founder. La règle couvre
les nominations principales et supplémentaires, les créations de comptes, les
créations de rôles et les changements de permissions financières d’un rôle existant.
La création/nomination d’une autre direction requiert donc maintenant un founder,
car direction contient approve. Les délégations non financières et changements
de libellé sans changement de droits restent possibles. Les vérifications existantes
de permissions, école, révision et audit restent en place.

Cette mesure empêche la direction de fabriquer seule un nouvel approbateur via ces
API. Elle ne prouve pas l’identité réelle des agents, ne révoque pas les comptes
contrôlés déjà créés et ne neutralise pas un founder malveillant ou une collusion.
Une recette de production doit examiner les comptes et délégations historiques.

## P2 — Actions affichées au-delà des droits

`frontend/FinancePanel.jsx` affichait création de tarifs, affectation, réception
et annulation sans lire les droits effectifs ; l’API pouvait néanmoins les refuser.
Le bouton d’annulation portait encore « (direction) », devenu incorrect sur main.
Correctif : lecture de my-access, affichage fermé par défaut des écritures, contrôle
séparé de manage, receive et reverse, libellé neutre. Les reçus et relevés restent
consultables. Ce filtrage améliore l’interface ; les refus serveur restent la sécurité.

L’écran de la capture est `LivePayments` : sur main il reçoit canReceive depuis
my-access et masque déjà les champs en l’absence de receive. Le badge Économe est
fixe. Une capture affichant ces champs ne prouve donc pas une escalade sur main ;
le décalage de version live est ici constaté indépendamment via Render.

## Migrations et données anciennes

- 0009_finance_ledger ajoute les droits manage/receive/reverse à direction, et
  manage/receive à comptabilite, pour les rôles revision=1 seulement.
- Les migrations pédagogiques historiques ajoutent aussi des droits aux rôles
  standards ; certaines protègent les rôles personnalisés par leur révision.
- 0020_finance_payment_batches suit 0019_parent_payments et ajoute les lots et
  clôtures, sans retirer les droits historiques de direction.
- 0021_financial_controls suit 0020 : additional_roles et transferts de fonds.
- 0022_finance_role_separation suit 0021 : retire les quatre droits à tous les
  rôles code=direction, y compris révisés ; retire manage/receive/deposit à
  comptabilite, ajoute approve aux deux et reverse à comptabilite ; incrémente
  les révisions et crée econome/tarification si absents.
- Les libellés et autres personnalisations sont conservés. Les rôles personnalisés
  d’autres codes et les rôles econome/tarification déjà existants ne sont pas
  normalisés. Les cumuls additional_roles ne sont pas révoqués. Une migration
  réussie ne garantit donc pas qu’une personne réelle perd tous ses droits.
- Le reverse de 0022 est noop : revenir au code #41 ne restaure pas les anciennes
  permissions en base. Le déploiement et la migration doivent être vérifiés ensemble.

Aucune migration nouvelle ou modification d’une migration historique dans ce correctif.

## Intégration et validation

Les PR ouvertes #26 et #33 ont été inventoriées avec leurs fichiers. Elles ont déjà
des conflits avec main avant ce correctif (notamment migrations/profils pour #33,
routes et tableaux de bord pour #26). Ne pas promettre une absence générale de conflits.
Le correctif évite les modèles, services, routes, migrations et SchoolDashboard.
Seul views.py chevauche la liste de #33 ; la compatibilité des hunks est vérifiée
séparément par simulation de fusion. Résultat sur les têtes récupérées : mêmes
3 fichiers en conflit pour #26 et mêmes 9 fichiers pour #33, avec origin/main ou
avec le commit corrigé ; aucun conflit supplémentaire, notamment aucun sur views.py.
Aucun changement dans les branches de ces PR.

Les tests de régression couvrent les refus d’escalade, l’approbateur contrôlé, la
frontière founder, les opérations ordinaires et l’affichage direction/caisse/tarifs.
Le test de démonstration réactive seulement l’ancienne règle de délégation par mock ;
les autres contrôles réels et l’endpoint d’approbation sont exécutés normalement.
La démonstration a aussi été exécutée en remplaçant temporairement views.py par
les octets exacts de origin/main, puis en restaurant le correctif dans un finally :
preuve de création/approbation réussie, deux tests de protection échouant avec
201 au lieu de 403 avant correction ; les neuf tests direction passent après correction.

Validation locale finale : 213 tests Django exécutés, 209 réussis et 4 ignorés
(PostgreSQL requis) ; 28 tests Vitest réussis ; compilation Vite réussie ;
makemigrations --check --dry-run : aucune modification ; git diff --check réussi.
Les tests existants couvrent auto-annulation, auto-clôture, auto-transfert et migration 0022.

Limites : pas d’examen des permissions du compte de production, pas de preuve
PostgreSQL de concurrence sur ce poste (Docker indisponible), ni d’audit exhaustif
de concurrence des changements de rôles. Les contrôles d’inclusion utilisent des
lectures hors transaction sur main ; une révocation concurrente n’est pas une
preuve de révocation instantanée. Les tests de verrouillage PostgreSQL doivent
passer dans la CI avant intégration. Aucun test local SQLite ne valide ces garanties.

# YEM — Contrôle par cycle : fondations sécurisées et mise en service

Cette couche est empilée sur la PR #58 (formulaire unique). Elle ne prétend pas rendre **tous** les modules conformes à la gestion par cycle.

## Règle métier

- Un **établissement** peut contenir maternelle, primaire, collège et lycée ; les cycles réels sont les \`AcademicCycle\` de cet établissement (UUID). Ce ne sont ni les noms des fonctions, ni les codes matricules.
- Un **compte** possède des rôles applicatifs et une portée globale \`SchoolMember.access_cycle_ids\` :
  - \`null\` : accès historiquement global à son établissement (valeur conservée pour les membres existants).
  - \`["uuid_cycle", ...]\` : portée limitée. La liste doit être non vide et composée de cycles académiques actifs appartenant à **cette même école**.
- Les fonctions sont des nominations (\`SchoolAppointment\`) distinctes ; une personne peut en avoir plusieurs. Les nominations ne créent pas de droits.
- Le propriétaire \`OrganizationMember(role=founder)\` reste une autorité indépendante du rôle SchoolMember et ne peut être "restreint" par ce champ, afin de ne pas donner de faux sentiment de protection.
- Les restrictions d'un compte sont **intersectionnelles** : même si un rôle donne une permission globale, l'accès effectif passe par les contrôles de cycle.
- Les membres historiques **ne sont pas requalifiés automatiquement** ; le propriétaire doit leur appliquer le cycle correspondant et valider les accès après contrôle.

## Couche serveur (fail closed)

Pour un membre à portée limitée, un middleware vérifie **chaque route** \`/api/v1/schools/<id>/...\` AVANT son exécution. Toute route non explicitement auditée pour le filtrage par cycle renvoie HTTP 403. Ceci est prioritaire sur le menu React et les permissions de rôle. Le contrôle relit la portée sur chaque requête : révocation sans reconnexion.

Endpoints autorisés après validation des rôles historiques :
- GET \`my-access\` (permissions affichées limitées aux modules compatibles).
- GET \`academic/years|cycles|levels|tracks|classes\` et leurs fiches ; années communes, autres listes filtrées par cycle.
- GET \`students\`, \`students/<id>\`, \`students/<id>/guardians\` : seulement élèves dotés d'une **inscription active** dans un cycle autorisé.
- GET \`enrollments\`, \`enrollments/<id>\` : filtrés par le cycle de la classe.
- GET \`staff/me/assignments\` : affectations du compte dans ses cycles seulement.
- GET \`organization/my-appointments\` : uniquement nominations propres à la personne.
- GET / POST \`staff/onboard\` : création atomique de personnel avec contrôles des cycles des nominations, classes et du compte créé.

Pour l'instant, les modifications d'élèves, notes, bulletins, absences, évaluations, finances, admissions, imports/exports et autres modules sont **refusées** pour les membres restreints, même avec une permission théorique. Leurs routes doivent être auditées et filtrées avant toute ouverture. Les comptes à périmètre global conservent les contrôles métier existants.

## Formulaire / propriétaire

Lors de l'ajout d'un collaborateur : choix explicite d'un rôle et de cycles académiques réellement configurés. Une personne peut exercer plusieurs fonctions avec une fiche et un seul compte facultatif. Un responsable limité ne peut pas créer un compte global, ni accorder une nomination ou une affectation dans un autre cycle. Les rôles financiers restent soumis aux contrôles indépendants en place.

Un propriétaire peut consulter les comptes dans le formulaire puis modifier leur périmètre via \`PATCH /api/v1/schools/<id>/members/<member_id>/cycle-access\`, avec **motif d'au moins 8 caractères**, audit \`member_cycle_scope_changed\` et prise d'effet immédiate. Cette opération ne révoque ni les nominations ni les droits globaux appartenant à un fondateur.

## Limites et prochaines phases

1. Le cycle dans \`SchoolAppointment\` est un **code de profil** (\`prescolaire\`, \`primaire\`, etc.), tandis que le cycle académique est un **UUID** et peut avoir un autre code. Pour une création par responsable limité, seules les nominations dont le code de cycle correspond **exactement** à un code du profil scolaire sont autorisées. Si l'établissement utilise un code libre différent, il faudra enregistrer une association explicite entre les deux référentiels ; ne jamais deviner le lien.
2. La portée enregistrée s'applique actuellement à **l'ensemble des rôles** du compte. Une personne avec « direction primaire » et « enseignement maternelle » requiert ensuite une **matrice permission×cycle** afin d'accorder des droits différents à chaque cycle, et pas seulement une union de droits sur deux cycles.
3. Les opérations de modification (élèves, notes, absences, tableaux de bord, rapports, finances) doivent être adaptées une par une et testées en rôle restreint, y compris les liens indirects, exports, fichiers et historiques.
4. Le propriétaire doit réviser les comptes historiques non limités (NULL), ainsi que les comptes créés depuis les anciens formulaires, avant d'annoncer que tous les membres d'un complexe sont séparés par cycle.
5. Le parcours « modifier un collaborateur / départ / changement de fonction » reste dans les onglets historiques. Ne pas le confondre avec la révocation du périmètre des cycles.

## Recette

- Tests : \`python backend/manage.py test institutions.test_cycle_scoped_staff institutions.test_staff_onboarding\`
- Validation : suite Django et Vitest complètes, migrations PostgreSQL, build et smoke test.
- Manuel : un complexe Maternelle + Primaire, au moins un élève dans chaque cycle, un compte direction restreint au Primaire, un propriétaire et un gestionnaire du personnel.
- Vérifier : aucune donnée maternelle dans les lectures du primaire ; écriture de classe maternelle ou accès financier refusé ; création d'un compte global par responsable restreint refusée ; changement de périmètre instantané ; tests des droits de la direction globale inchangés.
- Ne pas fusionner ou déployer avant tests et revue approfondie des restrictions de routes.

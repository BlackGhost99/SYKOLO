# YEM — Fiche élève : quatre droits distincts (11 novembre 2026)

La sécurité de la fiche de l'élève distingue le **métier**, le **rôle YEM**, le **périmètre de cycle** et le **niveau d'information personnelle**. Ces droits sont attribuables depuis « Rôles et permissions » et contrôlés au serveur, pas uniquement dans React.

## Droits

| Permission | Autorise | N'autorise pas à elle seule |
|---|---|---|
| `school.students.profile.read` | Identité minimale (nom, prénom, matricules), existence du dossier et parcours scolaire | Date de naissance, adresse, origine, réponses personnalisées, pièces, familles, finances |
| `school.students.admin.write` | Modifier un dossier existant, sous réserve du droit de lire ce dossier | Créer et inscrire des élèves sans `school.students.manage`; consulter ou modifier les champs sensibles sans autorisation supplémentaire |
| `school.students.sensitive.read` | Avec le droit de lecture scolaire : consulter informations sensibles, responsables légaux, contacts, pièces et réponses personnalisées | Modifier la fiche ; exporter sans le droit de gestion ; consulter les finances |
| `school.students.finance.read` | Avec `school.finance.read` : annuaire minimal de caisse, rattachements aux inscriptions, frais et soldes | Accès au dossier scolaire complet, adresses, téléphones, pièces, situation médicale |

Les anciennes permissions `school.students.read` et `school.students.manage` restent respectées pour les fonctionnalités scolaires historiques. Elles ne remplacent **jamais** la permission sensible explicite. L'API masque les champs sensibles et la liste des responsables légaux sans cette permission.

## Profils conseillés

- **Direction / Proviseur / Principal** : lecture scolaire + modification administrative + lecture sensible ; lecture financière distincte si le rôle possède également `school.finance.read`.
- **Secrétariat habilité** : lecture scolaire + modification administrative + lecture sensible, sans pouvoir financier par simple association.
- **Censeur / Direction des études** : lecture scolaire, éventuellement limitée à un cycle ; ni coordonnées familiales, ni documents ni paiement par défaut.
- **Vie scolaire / Professeur** : listes de classes et fonctions liées aux affectations ; pas de dossier sensible complet.
- **Comptable / Économe** : `school.students.finance.read` et `school.finance.read`, mais pas la fiche élève générale. L'économe conserve son flux de caisse, le comptable ses contrôles comptables.
- **Propriétaire / tutelle / organisme confessionnel** : aucun accès automatique au dossier simplement du fait du titre. Accorder séparément et auditer si nécessaire.

## Compatibilité et migration

La migration `0044_student_access_separation` est ciblée :
- Direction, principal, proviseur et secrétariat existants : conservent leurs droits, avec les nouveaux droits scolaires/sensibles nécessaires lorsqu'ils détenaient déjà **lecture + gestion**.
- Comptabilité et économe standards existants : la lecture générale est remplacée par l'annuaire financier lorsqu'ils n'ont pas le droit de gérer administrativement la fiche.
- Secrétariat pédagogique : lecture scolaire explicite, sans pièces ni contacts.
- Rôles personnalisés, parents et enseignants : permissions non modifiées. Si une organisation attend un accès sensible pour un rôle personnalisé, elle doit accorder le nouveau droit.
- Les écoles et les données élèves ne sont pas réécrites. Les changements de permissions des rôles concernés augmentent le numéro de révision.

Cette étape se base sur la PR #98 (gouvernance public / privé) pour l'ordre des migrations. Fusionner la PR #98 avant la présente évolution.

## Surfaces protégées

- `/students`, `/students/{id}` : détail minimisé sans droit sensible.
- `/students/{id}/dossier` : dossiers et coordonnées omis sans droit sensible ; finance séparée.
- `/students/{id}/guardians`, `/guardians-by-class` : droit sensible requis.
- `/overview/students` : lecture scolaire ou combinaison explicite des droits financiers ; aucun contact ni document en mode financier.
- `/overview/finance` : les identités/contacts des responsables sont absents sans droit sensible.
- `/finance/roster` : nouvelle API de caisse — nom, code, classe et identifiant d'inscription uniquement, protégée par les deux droits financiers.
- `/imports/students/export` : export CSV contenant les renseignements familiaux réservé aux gestionnaires également habilités aux données sensibles.
- Périmètres par cycles : les API déjà filtrées conservent leur contrôle ; aucune nouvelle route de finance n'est ouverte aux comptes limités par cycle.

## Tests

Scénarios : lecteur pédagogique, éditeur administratif, lecteur sensible, comptable sans fiche, absence de finance générale, anciens rôles, export, requêtes sur une autre école. Contrôler la migration, la suite Django, `makemigrations --check`, le build et les tests frontend. Vérifier manuellement les trois établissements pilotes et les rôles personnalisés avant activation en production.

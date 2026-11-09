# YEM — Jeu de démonstration pédagogique 2026–2027

## État du jeu réel (9 novembre 2026)

Les scripts ci-dessous ont été exécutés dans la **base YEM réelle** (Supabase), sur les trois établissements de test identifiés, sans suppression et sans modification des anciens dossiers. **Il s'agit de données entièrement fictives** ; elles ne doivent pas être confondues avec des pièces scolaires ou financières réelles.

- `scripts/yem_demo_seed_base_2026.sql` : 45 élèves fictifs, 54 responsables légaux (15 principaux + 3 secondaires par établissement), 23 nouvelles classes de test et six fiches de personnel sans compte de connexion par établissement ; trois années scolaires 2026–2027 (dont la préexistante) et trois périodes.
- `scripts/yem_demo_seed_pedagogy_2026.sql` : 84 enseignements associés à 84 affectations pédagogiques et 84 créneaux hebdomadaires ; notes pour 135 copies, et 90 marques de présence sur 56 séances, dont des absences fictives. Comprend les cinq anciennes classes « démo » du Lycée Privé 1 où certains de nos élèves avaient déjà été inscrits.
- `scripts/yem_demo_seed_reports_2026.sql` : 45 bulletins scolaires **brouillons**, chacun issu des notes des trois matières publiées dans le jeu de test. Le titre indique explicitement `DOCUMENT FICTIF`. PDF téléchargeable via la fonctionnalité existante.
- `scripts/yem_demo_fix_primary_years_2026.sql` : mise en conformité du primaire du complexe Les 8, avec cinq années (1re à 5e). Les anciennes classes CE1 et CE2 sont regroupées en deux divisions de la 3e année, sans réaffecter les élèves ni réécrire les notes ou les appels. Seules les anciennes classes fictives `DEMO26-` sont concernées.
- `scripts/yem_demo_correct_birthdates_2026.sql` : correction ponctuelle strictement limitée aux **45 élèves fictifs**, pour aligner leur âge simulé sur leur niveau (sans toucher aux élèves préexistants).

| Établissement | Préfixe élève | Élèves | Responsables | Classes nouvelles | Équipe fictive |
| --- | --- | ---: | ---: | ---: | ---: |
| Complexe scolaire Les 8 | `DEMO26-CES8-` | 15 | 18 | 9 | 6 |
| Lycée Privé 1 | `DEMO26-LP1-` | 15 | 18 | 7 (+ 5 classes démo préexistantes) | 6 |
| Lycée Privé 2 | `DEMO26-LP2-` | 15 | 18 | 7 | 6 |

**Convention des niveaux du primaire (modifiable par établissement) :** 1re année (ancienne CP1), 2e année (ancienne CP2), 3e année (anciens CE1 + CE2, deux divisions), 4e année (ancien CM1) et 5e année (ancien CM2). Les codes techniques du catalogue standard sont `1re-annee`, `2e-annee`, `3e-annee`, `4e-annee`, `5e-annee`. Dans **Structure académique → Niveaux**, l'établissement peut renommer un niveau et changer son ordre sans toucher à l'identifiant technique utilisé par les notes et barèmes.

**Navigation et tests manuels :**

1. Ouvrir YEM et choisir l'établissement à tester.
2. Choisir l'année scolaire **2026–2027**.
3. Dans **Élèves**, rechercher `DEMO26-CES8-`, `DEMO26-LP1-` ou `DEMO26-LP2-`. Ouvrir un dossier puis vérifier sa classe, ses responsables et les adresses fictives `@example.invalid`.
4. Dans **Classes et enseignements**, choisir une classe suffixée « (démo) » ; consulter les trois matières et les enseignants de test. Ces enseignants sont des **fiches de personnel, pas des comptes utilisateurs** : ils ne peuvent pas encore ouvrir une session.
5. Dans **Emplois du temps**, consulter les créneaux de la semaine. Un contrôle SQL a confirmé l'absence de collision de professeur dans les créneaux simulés.
6. Dans **Présences**, consulter les appels des **2 et 3 novembre 2026** ; comparer absences et présences.
7. Dans **Évaluations**, consulter le contrôle publié par matière et le second devoir brouillon ouvert à la saisie, sans modifier les notes de référence sauf si le test le demande.
8. Dans **Bulletins**, ouvrir un des 45 bulletins brouillons, examiner le résultat sur 20 et cliquer sur l'export PDF. **Ne pas le publier comme document officiel** : c'est une démonstration.

## Protection des données

- Les matricules fictifs commencent par `DEMO26-`; les noms sont inventés et les adresses mail se terminent par `@example.invalid` ; les numéros commencent par `000-`. Aucun SMS ni courriel n'est envoyé.
- Aucun vrai paiement, reçu de caisse ou règlement SingPay n'est simulé : le jeu de données n'ajoute pas de recettes fictives à la comptabilité.
- Les trois scripts de création sont **idempotents et insert-only** (UUID stables, `ON CONFLICT DO NOTHING`). Le script de correction des dates corrige uniquement la date de naissance des **45 profils fictifs préfixés `DEMO26-`**, avec leur marqueur `extra_fields.demo`, en incrémentant la révision. Il ne modifie aucun dossier réel. Ne pas les lancer sur d'autres établissements ni pour d'autres années.
- Les comptes enseignants et parents ne sont **pas** créés ; les titulaires fictifs ne disposent d'aucun accès de connexion.
- Pas de photo enregistrée : les modèles actuels `Student` et `StudentGuardian` ne disposent pas de champ média sécurisé. Ne pas mettre d'images de mineurs dans des champs JSON.
- La génération PDF utilise les données de note et le template scolaire actuel ; un nouveau brouillon peut aussi être recalculé depuis l'API classique. Les bulletins artificiels initiaux portent un titre « document fictif ».
- Les périodes sont créées jusqu'au 18 décembre 2026, alors que la simulation se situe en novembre 2026 : c'est volontaire, les bulletins restent en **brouillon**.
- La gestion de la clôture d'année (migrations 0036–0039) est un chantier distinct : le site peut être sur un commit plus ancien que `main`. Ce jeu a été préparé sur le schéma actuel et ne prétend pas valider une migration de production.

## Scripts et exploitation

Exécuter les fichiers dans cet ordre strict depuis une session d'administration **YEM uniquement**, après sauvegarde et sur un environnement autorisé :

1. `yem_demo_seed_base_2026.sql`
2. `yem_demo_seed_pedagogy_2026.sql`
3. `yem_demo_seed_reports_2026.sql`
4. `yem_demo_fix_primary_years_2026.sql` (uniquement pour convertir une ancienne version de démonstration primaire avec codes CP/CE/CM ; idempotent)
5. `yem_demo_correct_birthdates_2026.sql` (uniquement si une première version de la démo a déjà été insérée)

Les scripts sont vérifiés sur la base YEM existante, y compris la réexécution des trois scripts de création après conversion du primaire. L'ajout de données nouvelles est une opération réelle, donc doit être réservé aux environnements de démonstration et aux utilisateurs habilités.

Ne pas supprimer les dossiers fictifs avec un simple `DELETE` non révisé : des bulletins, des notes, des appels et des affectations sont rattachés. Prévoir une procédure de nettoyage transactionnel et protégée si besoin de les retirer plus tard.

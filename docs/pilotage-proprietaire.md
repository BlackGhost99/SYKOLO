# YEM — Pilotage du propriétaire d'un établissement

## Constat

Sur le rôle `proprietaire`, les permissions d'origine permettent la création ou l'attribution de comptes et la gestion des rôles, **mais pas** `school.finance.read` ni `school.students.read`. Le tableau de bord historique affiche ses statistiques financières seulement si l'utilisateur possède `school.finance.read` ; sinon il n'affiche pratiquement que les modules autorisés. Il est donc normal que l'écran soit vide techniquement, mais cela **ne répond pas au besoin métier** d'un propriétaire d'établissement.

## Fonctionnalité

Une synthèse propriétaire séparée, **strictement en lecture seule** :

- **Scolarité** : élèves effectivement inscrits, classes ouvertes, effectifs par cycle, capacités définies, activité d'évaluations, bulletins publiés, absences et retards, pour l'année sélectionnée.
- **Finances** : facturation, encaissements, impayés et montants échus, encaissé du mois et du jour, évolution mensuelle. Aucune somme entre monnaies différentes. Les paiements annulés sont exclus.
- **Admissions** : demandes reçues, en attente, admises, refusées, converties en inscriptions.
- **Personnel** : collaborateurs actifs, comptes liés, affectations aux classes de l'année et nominations actives. Aucune fiche RH individuelle exposée.
- **Activité** : 30 derniers jours d'événements d'audit regroupés par catégorie et par jour, **sans noms, sujets d'audit ni contenus individuels**.

Toutes ces valeurs sont spécifiques à l'établissement sélectionné par le compte, et les données annuelles sont isolées par année scolaire. Les effectifs et montants sont des valeurs réelles de la base, jamais des chiffres de démonstration.

## Règle de sécurité

La route `GET /api/v1/schools/{school_id}/owner/overview` ne vérifie pas seulement le nom du rôle.

Elle exige `owns_school(user, school)` :
- fondateur de l'organisation propriétaire de cette école ;
- titulaire du rôle `proprietaire` et du drapeau serveur `is_school_owner=True`, tous deux actifs dans l'école.

Un directeur, un comptable, un enseignant, un utilisateur portant uniquement le nom de rôle `proprietaire` sans titulaire vérifié ou un propriétaire désactivé **ne peut pas consulter l'API propriétaire**. L'accès à une école étrangère demeure interdit.

- Les comptes explicitement limités à un cycle sont bloqués sur cette vue générale.
- Les établissements `governance_mode=public`, lorsqu'ils sont disponibles après intégration de la gouvernance, ne peuvent pas recevoir ce pilotage privé. La supervision publique doit suivre le modèle de tutelle, distinct de la propriété privée.
- Une requête POST/PATCH/DELETE est refusée. Aucune permission de caisse, notes, admissions, RH ou consultation nominative n'est ajoutée au rôle propriétaire.
- L'API ne renvoie aucune donnée personnelle d'élève, parent ou salarié ; aucun matricule, nom individuel ou contenu d'audit.
- Les réponses utilisent `Cache-Control: no-store` pour réduire la persistance côté navigateur.

## Navigation

- Connexion en tant que propriétaire → **Tableau de bord** directement enrichi.
- Nouveau menu réservé au propriétaire : **Pilotage propriétaire**, avec six onglets.
- Le module « Comptes et droits » continue à fonctionner pour les titulaires autorisés.

Les comptes non propriétaires conservent leur tableau de bord d'origine.

## Limites et dépendances

Aucun schéma SQL n'est modifié : ce lot ne nécessite **aucune migration**. Les PR #98, #99 et #102 sont encore séparées ; les migrations des PR #98 et #102 devront être réconciliées si elles sont intégrées ensemble.

Tests à exécuter : tests frontend, compilation, `manage.py check`, `makemigrations --check`, migrations, tests Django, isolation multi-écoles et anti-fuite. Ne fusionner et ne déployer qu'après validation et vérification des services Render.

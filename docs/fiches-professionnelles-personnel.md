# YEM — Fiches professionnelles du personnel et des enseignants

Mise à niveau M3.2 (14 novembre 2026). **Cette fonction est distincte des fiches élèves et des dossiers RH privés.**

## Objectif

Tout agent (enseignant, proviseur, principal, secrétaire, surveillant, personnel technique, économat) enregistré par YEM dispose d'une **fiche professionnelle unique**, même si aucun compte YEM ne lui est associé.

La fiche est reliée aux informations déjà saisies et mises à jour dans les modules existants :

- Identification : matricule du personnel, nom et prénom, poste déclaré, date d'entrée, statut actif/archivé, existence d'un compte lié.
- Qualifications et activités : diplôme ou qualification, discipline/spécialité, statut professionnel (saisie libre adaptée au public, privé et confessionnel), volume de service, email et téléphone **professionnels**.
- Fonctions : nominations de l'organigramme, périmètre/cycle, dates de prise de poste et fin, caractère actuellement effectif.
- Affectations : année, cycle, classe, responsabilité, actif/archivé.

Les informations du formulaire unique et des modules académiques restent les sources de vérité pour les **fonctions** et **affectations** : pas de saisie parallèle et pas de réécriture des modules.

## Accès et responsabilités

| Compte | Annuaire du personnel | Fiche professionnelle d'un autre agent | Modification | Sa propre fiche |
|---|---|---|---|---|
| Direction (rôle standard avec droits de personnel) | Oui | Oui | Oui | Lecture |
| Secrétariat (rôle standard) | Oui | Oui | Non, sauf attribution explicite | Lecture |
| Responsable RH délégué | Selon droits attribués | `school.staff.dossier.read` | `school.staff.dossier.manage` **et** lecture | Lecture |
| Enseignant / personnel avec compte lié | Pas automatiquement | Non | Non | Oui, en lecture |
| Fondateur sans rôle de gestion du personnel | Non automatiquement | Non | Non | S'il dispose d'une fiche liée |
| Compte limité par cycle | Accès aux dossiers d'autrui bloqué en V1 | Bloqué | Bloqué | Lecture personnelle, affectations filtrées sur les cycles autorisés |

Les droits sont ajoutés au catalogue des rôles YEM, sans autorisation implicite découlant d'une fonction ou nomination :

- `school.staff.dossier.read` — consulter la fiche professionnelle d'un personnel de son établissement.
- `school.staff.dossier.manage` — modifier les champs professionnels autorisés, sous réserve du droit de lecture.
- `school.staff.read` continue à servir à la liste générale, **sans droit d'accès aux fiches détaillées**.

La migration donne les nouveaux droits aux **rôles standard de direction** qui possèdent déjà à la fois `school.staff.read` et `school.staff.manage`, ainsi qu'une lecture seule au **secrétariat standard** qui possédait déjà la lecture du personnel. Elle ne modifie pas les rôles personnalisés.

## Interfaces

- Personnel → Équipe de l'établissement : bouton « Consulter la fiche » uniquement pour les comptes autorisés.
- Fiche individuelle : informations professionnelles, fonctions, classes ; édition protégée par la révision et le serveur.
- Sécurité du compte → « Ma fiche professionnelle » : lecture de sa fiche lorsqu'un `StaffRecord.account` actif existe.

En cas de personnel sans compte, le dossier reste consultable par l'administration autorisée. Aucune création de compte n'est forcée.

## Sécurité et limites

- Le serveur vérifie toujours l'appartenance à l'établissement et les deux permissions de lecture/modification ; les rôles personnalisés peuvent les recevoir via le module de gestion des rôles.
- Les comptes limités à des cycles ne peuvent pas parcourir les dossiers d'autrui dans cette première étape. La lecture de leur propre fiche filtre fonctions et classes.
- Les changements sont tracés dans `SchoolAudit` : auteur, dossier concerné, noms des champs, révision ; pas les valeurs confidentielles.
- Tous les GET de dossier ont `Cache-Control: no-store`. Le refus des champs inconnus et le verrouillage des révisions évitent des modifications non autorisées.
- Aucune adresse privée, numéro privé, salaire, données de santé, numéro de pièce d'identité, diplôme numérisé, casier ou document de contrat n'est introduit dans la fiche professionnelle.
- Le statut d'emploi saisi dans la fiche est descriptif, pas une preuve de conformité réglementaire ou d'affectation ministérielle.
- La visibilité de dossiers d'autrui par cycle/équipe est **non livrée dans ce lot** : une future matrice de visibilité RH par cycle sera nécessaire.

## API

`GET /api/v1/schools/{school_id}/staff/{staff_id}/dossier` — dossier (lecture autorisée).
`PATCH /api/v1/schools/{school_id}/staff/{staff_id}/dossier` — actualisation des champs professionnels (lecture + édition).
`GET /api/v1/schools/{school_id}/staff/me/dossier` — dossier de l'employé connecté (lecture personnelle).

## Migration / intégration

Migration `0043_staff_professional_dossier`, dépend de `0042_admission_finance_scholarship`.

**Attention aux PR en cours :** la PR #98 sur la gouvernance utilise également un numéro de migration 0043. Si #98 est fusionnée avant ou après cette PR, résoudre les deux branches de migration par une migration de fusion Django explicite et vérifier `makemigrations --check` dans l'état fusionné. La PR #99 dépend de #98. Ne pas déployer cette PR en production avant la validation de ces dépendances.

Vérifier dans la CI : build React, tests frontend, `manage.py check`, `makemigrations --check`, `migrate`, et la suite complète Django. Recette avec compte direction, secrétaire, RH, enseignant avec/sans compte, fondateur et utilisateur limité à un cycle.

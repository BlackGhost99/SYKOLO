# YEM — Profils d'établissements et cycles gabonais

**Contexte :** déploiement initial à Libreville, Gabon. L'identité visuelle YEM (logo et vert officiel) est conservée. Les référentiels ci-dessous sont des **configurations proposées**, à faire valider école par école ; ils ne transposent pas automatiquement toutes les obligations d'un lycée public dans un établissement privé.

## Modèle métier

1. **Organisation** : personne morale ou fondateur, peut posséder plusieurs établissements.
2. **Établissement** : unité administrative isolée (nom, statut, type, cycles offerts).
3. **Cycles proposés** : maternelle, primaire, collège, lycée ; un groupe scolaire combine plusieurs cycles. Les identifiants de cycles du profil sont distincts des cycles pédagogiques `AcademicCycle` déjà personnalisables.
4. **Année / niveau / classe / filière** : déjà gérés séparément par les modèles scolaires ; ne pas fabriquer les mêmes classes pour les quatre types.
5. **Rôles** : modèles suggérés, éditables par école, non activés automatiquement sur un compte. Le responsable choisit les postes effectifs de son établissement.

| Type | Cycle(s) suggéré(s) | Responsabilité | Activités principales |
| --- | --- | --- | --- |
| Maternelle | maternelle | Direction maternelle, éducateurs, assistants | Éveil, bilans de développement, accueil, présence, cantine, garderie |
| Primaire | primaire | Direction primaire, instituteurs, suivi pédagogique | Classes de primaire, compétences et bulletins configurables, CEP, responsables |
| Collège | collège | Chef d'établissement / principal selon école, études, vie scolaire, surveillants | Enseignants par matière, emplois du temps, évaluations, conseils, BEPC, orientation |
| Lycée | lycée | Proviseur, censeur pédagogique, censeur vie scolaire, intendant | Filières, emplois du temps, évaluations, conseils, bac, suivi financier |
| Groupe scolaire | un ou plusieurs cycles explicitement choisis | Direction générale + responsables de cycle | Centralisation groupe avec adaptation indépendante par cycle |

Les fonctions de **comptabilité** (contrôle/rapprochement), **économat/caisse** (encaissement), **intendance** (gestion financière et matérielle), **secrétariat**, **direction**, **audit** doivent rester séparées par permissions, même si une petite école cumule matériellement certaines personnes.

## Implémenté dans la première étape de ce chantier

- Le profil `school_type`, `enabled_cycles` et `profile_revision` est conservé en base.
- Les établissements existants restent `a_configurer`, sans déduction automatique à partir du nom.
- Les créations via la plateforme et via les organisations acceptent le type ; les nouveaux formulaires obligent à choisir et, pour un groupe scolaire, à sélectionner les cycles.
- `GET /api/v1/schools/{id}/profile` / `PATCH` : validation serveur, contrôle d'accès, révision optimiste, audit et préservation des rôles existants.
- La console super-admin peut modifier un profil avec motif et MFA via l'action `profile`.
- Des rôles métier additionnels sont suggérés par type ; le choix reste propre à l'école.
- La création de comptes scolaires affiche les rôles réellement configurés au lieu d'une liste fixe.
- Migration `0016_school_profiles` non destructive.

## À implémenter avant de considérer l'adaptation des cycles comme complète

**Ne pas confondre les données du profil avec une contrainte métier déjà appliquée :** les API pédagogiques existantes restent à raccorder progressivement au profil.

### P0 — Isolation fonctionnelle par cycle
- Lier les cycles pédagogiques `AcademicCycle` aux cycles canoniques ci-dessus, avec compatibilité des cycles historiques, des années et des classes.
- Introduire des affectations *par cycle* pour directeurs, censeurs, enseignants, économes et responsables, et appliquer les vérifications **côté serveur** sur chaque requête. Actuellement `SchoolMember` associe un compte à un rôle unique à l'échelle de l'école.
- Ne jamais permettre à un responsable de cycle de lire/modifier des informations d'un autre cycle du groupe scolaire sans délégation explicite.
- Adapter les tableaux de bord et menus sans prétendre qu'un simple masquage frontend garantit les accès.

### P1 — Parcours pédagogiques distincts
- Maternelle : bilans d'éveil, présences, garderie et suivi des familles ; pas de bulletin de secondaire imposé.
- Primaire : enseignants par classe, bulletins/compétences adaptés, CEP, passage vers la 6e.
- Collège : matières, évaluations, conseils, BEPC, orientation/concours.
- Lycée : filières/séries, matières, salles, intervenants, bac, vie scolaire et conseils.
- Appliquer règles configurables établissement > cycle > niveau > classe, sans barèmes, coefficients ou décisions inscrits en dur.
- Admissions : directe, concours/test, orientation et affectation selon politiques existantes ; garder la décision humaine et les justificatifs contrôlés.

### P1 — Recettes, dépenses, comptabilité et économat
- Rôles distincts pour caisse, tarifs, budget, annulations, dépenses, stocks, audit ; séparation des tâches avec second approbateur si requis.
- Frais par cycle/niveau/classe/année ; échéanciers, cantine/garderie (maternelle/école), internat/transport/uniformes selon prestations réellement proposées.
- Réconciliation PSP / espèces / banque, clôtures de caisse et reçus consolidés ; les méthodes `mobile_money` présentes en V1 ne prouvent **pas** le succès d'un paiement en ligne.
- Comptabilité et règles légales à valider selon statut de l'établissement.

### P2 — Paramétrage et contrôles d'exploitabilité
- Tests multi-écoles et multi-cycles, y compris une organisation possédant des établissements indépendants et un groupe scolaire multi-cycle.
- UI de configuration fine par directeur de cycle, accès enseignants et parents limités, migrations avec conservation des anciennes données.
- Revue juridique des formulaires et documents au Gabon avant déploiement.

## Références gabonaises
- Journal officiel, loi n°21/2011 du 14 février 2012, organisation générale de l'éducation : https://journal-officiel.ga/2703-21-2011-/
- Journal officiel, décret n°0859/PR/MENESTFPRSCJS concernant le lycée général : https://journal-officiel.ga/2050-0859-pr-menestfprscjs/
- Journal officiel, décret n°0209/PR/MENFC du 4 août 2023, établissements privés : https://journal-officiel.ga/20272-0209-pr-menfc-/
- Ministère de l'Éducation nationale, personnels administratifs : https://education-nationale.gouv.ga/services-aux-usagers/les-administratifs/

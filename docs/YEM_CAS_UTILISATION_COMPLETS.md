# YEM — Catalogue des cas d'usage et scénarios de recette

Version de travail du 4 novembre 2026. Ces cas décrivent **le fonctionnement cible** et servent d'acceptation au développement. Ils ne prouvent pas que chaque parcours fonctionne aujourd'hui.

## 1. Règles communes

- Chaque **organisation** peut posséder plusieurs établissements.
- Chaque **établissement** possède un type administratif et la liste des cycles réellement ouverts. Un lycée peut aussi accueillir un collège.
- Chaque **cycle** a ses niveaux, classes, programmes, barèmes, personnels et règles.
- Le **compte** identifie la personne ; ses **fonctions**, **permissions**, **affectations** et **périmètres** déterminent ses actions. Une personne peut exercer plusieurs fonctions dans plusieurs écoles (cible).
- Le changement d'école ne permet jamais de voir les dossiers de l'école précédente sans autorisation.
- Les actes sensibles (droits, décisions, publications, annulations d'encaissements) sont audités et, selon le cas, motivés et approuvés.
- Les élèves et leurs responsables ont des accès séparés. Un lien parental exige vérification humaine.
- Aucune classification d'établissement ne supprime automatiquement les données académiques existantes.
- Le statut « paiement en ligne » ne signifie payé que si une confirmation du prestataire est reçue ; le choix « espèces » signifie paiement attendu sur place.

## 2. Acteurs

| Acteur | Périmètre |
| --- | --- |
| Super-admin YEM | Plateforme et provisionnement avec MFA |
| Propriétaire/promoteur | Ses écoles et leurs contrats/quotas ; pas forcément leur direction |
| Directeur maternelle / Directeur primaire | Son école ou unité pédagogique |
| Principal collège / Proviseur lycée | Son établissement, délégations sous contrôle |
| Directeur des études / Censeur pédagogique | Programmes, enseignants, planning, évaluations, résultats selon cycles |
| Censeur vie scolaire / Surveillant général / Surveillant | Présences, retards, discipline selon classes et délégations |
| Responsable d'atelier / Chef des travaux | Enseignements techniques, ateliers, matériel, stages |
| Secrétariat / Admissions | Dossiers, candidatures, inscriptions, parents |
| Intendant / Économe / Comptable / Caissier | Budgets, frais, caisse, justificatifs selon droits |
| Enseignant / Professeur principal | Cours affectés, notes, appel, suivi autorisé de classe |
| Parent/tuteur légal | Ses enfants vérifiés dans les différentes écoles |
| Élève | Ses seules informations ; portail encore à construire |
| Conseiller d'orientation | Parcours et décisions d'orientation autorisées |

## 3. Cycle de vie complet : cas UC-01 à UC-30

### UC-01 — Créer une organisation
**Acteur** : super-admin. Sélectionner « Organisations » > « Créer », définir propriétaire et nom. **Résultat** : organisation enregistrée, auditée, sans élèves fictifs. **Cas particulier** : nom déjà utilisé.

### UC-02 — Ouvrir un établissement
**Acteur** : super-admin. Choisir organisation, type (maternelle, primaire, collège, lycée général/technique, groupe scolaire), cycles réellement enseignés, responsable initial et accès. **Résultat** : école isolée, administrateur créé. **Exceptions** : catégorie absente, cycle incompatible, utilisateur déjà existant, limite contractuelle.

### UC-03 — Classer une école existante
**Acteur** : super-admin MFA. Ouvrir la fiche, définir type et cycles avec motif. **Résultat** : métadonnées changées et audit ; **aucune** classe, inscription, note ou facture supprimée. **Exceptions** : valeurs incohérentes, droits absents, changement concurrent.

### UC-04 — Organiser un groupe scolaire
**Acteurs** : promoteur, directions désignées. Créer les écoles/unité(s), attribuer leurs responsables, isoler les élèves, mutualiser éventuellement certains services sans partager automatiquement les droits. **Résultat cible** : collège et lycée administrés séparément avec une supervision de groupe.

### UC-05 — Première mise en service scolaire
**Acteur** : chef d'établissement. Vérifier les coordonnées, choisir les modules du cycle, régler calendrier, périodes et critères d'évaluation. **Résultat** : checklist de rentrée, aucune fonction inutile imposée.

### UC-06 — Nommer les responsables
**Acteurs** : promoteur habilité, chef d'établissement. Créer le compte ou rattacher un compte existant, créer fiche du personnel, fonction, dates, périmètre, délégation. **Résultat cible** : Principal, Proviseur, Censeur, Directeur des études, Surveillant général, etc. identifiés avec leur propre accueil. **Exceptions** : poste vacant, double fonction, délégation impossible.

### UC-07 — Modifier, remplacer ou suspendre une fonction
**Acteurs** : nominant habilité, direction, super-admin en cas de secours audité. Retirer un poste/une délégation sans supprimer l'historique. **Résultat cible** : perte immédiate des accès correspondant au poste, conservation des décisions antérieures.

### UC-08 — Créer année, cycles, niveaux et classes
**Acteur** : direction/gestionnaire académique habilité. Créer année, cycles, niveaux, filières facultatives, classes, capacités, périodes. **Résultat** : classes ouvertes. **Exceptions** : niveau hors cycle, année différente, capacité atteinte.

### UC-09 — Configurer programmes et matières
**Acteur** : directeur des études/censeur pédagogique/direction. Créer matières, coefficients et cours par classe et année, unités de programme, référentiel d'évaluation. **Résultat** : cours préparés, aucun professeur associé par défaut.

### UC-10 — Affecter les enseignants
**Acteur** : direction ou responsable pédagogique délégué. Vérifier compte et fiche du personnel ; affecter à l'année et aux classes ; rattacher aux cours. **Résultat** : chaque enseignant voit seulement ses cours autorisés. **Exceptions** : enseignement dans deux écoles, absence, suppléance, professeur principal, contrat terminé.

### UC-11 — Publier les emplois du temps
**Acteur** : planificateur habilité. Créer salles/créneaux, séances, dates de validité ; contrôler chevauchements enseignant, classe, salle. **Résultat** : emploi du temps visible aux enseignants, parents liés et, à terme, élèves. **Exceptions** : remplacement d'urgence, salle indisponible, vacances, journée exceptionnelle.

### UC-12 — Configurer admissions et capacités
**Acteur** : direction/admissions. Ouvrir inscriptions directes, examen de dossier, concours ou affectation, pièces demandées, dates, capacité et éventuelle liste d'attente. **Résultat cible** : règles par cycle/niveau, non globales à l'école.

### UC-13 — Inscription directe
**Acteurs** : parent et secrétariat. Choisir école, classe et procédure ; déposer dossier ; vérifier pièces et places ; accepter ; attribuer matricule ; créer inscription. **Résultat** : élève officiellement inscrit et responsable légal enregistré. **Exceptions** : doublon, classe pleine, annulation.

### UC-14 — Admission par concours
**Acteurs** : parent, commission d'admission, direction. Candidature, convocation, épreuves, résultat, décision et conversion en inscription selon places. **Résultat cible** : traçabilité du concours et des candidats admissibles/refusés. **Exceptions** : liste complémentaire, absent, recours, éligibilité externe.

### UC-15 — Affectation/orientation extérieure
**Acteurs** : secrétariat, direction. Enregistrer école d'origine, décision de l'autorité et référence ; vérifier éligibilité ; affecter dans une classe. **Résultat** : admission documentée. **Exceptions** : affectation contestée, document non valide, capacité.

### UC-16 — Réinscription et passage de classe
**Acteur** : direction/secrétariat. Réutiliser dossier historique, créer inscription de nouvelle année, appliquer décision du conseil. **Résultat cible** : un seul dossier élève par école, historique préservé. **Exceptions** : redoublement, départ, abandon, nouvelle école.

### UC-17 — Transfert d'établissement
**Acteurs** : écoles d'origine/destination, famille. Transmettre uniquement les données autorisées et pièces validées, avec consentement et contrôle. **Résultat cible** : nouvelle inscription, traçabilité ; aucune fusion automatique de dossiers entre écoles.

### UC-18 — Lier un compte parent
**Acteurs** : secrétariat et responsable habilité. Enregistrer responsable légal, créer compte parent, vérifier identité, autoriser le lien enfant-compte. **Résultat** : accès aux seuls enfants liés ; possibilité de révocation. **Exceptions** : deux représentants légaux, garde partagée, changement d'autorité.

### UC-19 — Choisir la méthode de paiement
**Acteurs** : parent, caissier. Parent choisit « en ligne » ou « espèces sur place ». **Résultat cible** : statut « en attente » tant que l'argent n'est pas réellement reçu. **Exceptions** : paiement partiel, échéancier, réduction, erreur de montant, retour de prestataire.

### UC-20 — Encaisser, rembourser et clôturer la caisse
**Acteurs** : caissier/comptabilité/intendant selon droits. Créer tarifs, affecter créances, enregistrer règlements, délivrer reçus, contrôler fin de journée, justifier annulations. **Résultat** : soldes par élève et caisse réelle rapprochée. **Règle** : paiements simulés exclus du chiffre d'affaires réel.

### UC-21 — Accueillir et surveiller les élèves
**Acteurs** : surveillants, éducateurs, censeur vie scolaire. Enregistrer appel, retards, absences, justificatifs et interventions. **Résultat** : dossier d'assiduité et suivi éducatif selon classe/cycle. **Exceptions** : correction d'appel après clôture, incident grave, sortie anticipée.

### UC-22 — Enseignement quotidien
**Acteur** : enseignant. Consulter cours, planning, classes affectées, progression, saisir présences et observations adaptées. **Résultat** : suivi de cours sans accès aux classes étrangères.

### UC-23 — Évaluations et devoirs
**Acteur** : enseignant. Créer évaluation, sélectionner période, barème, coefficient et type, saisir les résultats des élèves. **Résultat** : notes en brouillon, contrôles de cohérence. **Exceptions** : élève absent, dispensé, rattrapage, modification justifiée.

### UC-24 — Approche maternelle et primaire
**Acteurs** : éducateurs, instituteurs, direction. Suivre domaines d'acquisition, compétences, observations, activités et, si choisi, notes. **Résultat cible** : bilan adapté à l'âge, jamais un bulletin de lycée imposé à la maternelle.

### UC-25 — Contrôle pédagogique
**Acteurs** : directeur des études, censeur pédagogique, direction. Vérifier cours non réalisés, notes manquantes, moyennes anormales, respect des programmes. **Résultat cible** : circuit de correction puis validation déléguée.

### UC-26 — Produire les bulletins
**Acteurs** : responsable pédagogique/direction. Publier les évaluations autorisées, calculer bulletins par période, contrôler, publier, produire PDF A4. **Résultat** : bulletin officiel visible au parent autorisé. **Exceptions** : note manquante, rectificatif, publication prématurée.

### UC-27 — Conseil de classe et orientation
**Acteurs** : direction, enseignants et personnes habilitées. Préparer la réunion, consulter les résultats, délibérer, enregistrer passage/redoublement/orientation et clôturer. **Résultat** : décisions historisées, bulletins conservés.

### UC-28 — Familles : suivi pendant l'année
**Acteur** : parent vérifié. Choisir enfant et établissement, consulter inscriptions, emploi du temps, présences, factures, résultats publiés ; recevoir ultérieurement notifications. **Résultat** : confidentialité par enfant. **Exceptions** : aucun enfant encore lié, accès révoqué.

### UC-29 — Fin d'année et rentrée suivante
**Acteurs** : direction, secrétariat, finance, pédagogie. Clôturer périodes, archiver sans supprimer, passer à l'année suivante, reconduire ou adapter les classes/cours/équipes. **Résultat cible** : historique durable et réinscriptions contrôlées.

### UC-30 — Audit, sécurité et changement d'établissement
**Acteurs** : utilisateurs autorisés, super-admin. Journaliser modifications, vérifier MFA, isoler écoles et permissions, gérer départs/suspensions, surveiller les accès. **Résultat** : séparation des responsabilités et remontée des anomalies.

## 4. Matrice par catégorie

| Catégorie | Paramètres déterminants |
| --- | --- |
| Maternelle | Sections, acquisition des compétences, suivi éducatif, parents, activités |
| Primaire | Classes polyvalentes, compétences et/ou notes, évaluations par cycle, CEP |
| Collège | Principal, études, vie scolaire, matières, coefficients, BEPC, orientation |
| Lycée général | Proviseur, censeurs, séries/filières, programmes, BAC, orientation |
| Lycée technique | Direction, chefs de travaux, ateliers, spécialités, TP, stages |
| Groupe scolaire | Plusieurs cycles, délégations par unité, services éventuellement partagés |

## 5. État d'avancement : ne pas confondre API et parcours validé

**Présent dans le code** : organisations, écoles, rôles simples par école, années/cycles/classes, fiches personnel, affectations classe/cours, inscriptions, admissions avec routes, caisse manuelle, emplois du temps, appels, évaluations, bulletins PDF, conseils, portail parent lié.

**Ajout de cette PR** : classification administrative des écoles, cycles réellement enseignés, choix lors de la création et reclassification auditée des écoles existantes, sans migration destructrice.

**À développer/tester** : multi-fonctions et délégations limitées à un cycle, organigrammes opérationnels par type, tableaux de bord Censeur/Principal/Proviseur, concours complet, portail élève, recherche/inscription Android depuis le compte parent, prestataire de paiement confirmé, incidents de vie scolaire, clôture annuelle automatisée, notifications, tests complets par profil.

## 6. Recette de bout en bout MBELE

- [ ] Classifier le Lycée Privé MBELE « Lycée général » avec cycles « Collège » et « Lycée général », sans toucher aux six élèves déjà enregistrés.
- [ ] Vérifier la structure 6ème A, 5ème A, 4ème A, 3ème A et 2nde A et les cinq élèves fictifs.
- [ ] Créer un proviseur fictif, un censeur pédagogique, un censeur vie scolaire, un secrétaire, un comptable et des enseignants de test.
- [ ] Vérifier leurs droits dans des sessions distinctes avant de leur permettre la modification.
- [ ] Créer les cours et affecter les enseignants ; programmer l'emploi du temps.
- [ ] Faire l'appel et enregistrer des notes, avec une configuration adaptée par niveau.
- [ ] Publier les évaluations et un bulletin par classe ; ouvrir les PDF depuis des comptes parents fictifs.
- [ ] Vérifier que les cinq paiements **simulés** ne sont pas intégrés à la caisse réelle.
- [ ] Tester un transfert, une admission par concours, un refus et une réinscription.
- [ ] Tester le refus de toute opération hors école et hors cycle affecté.

**Critère global d'acceptation** : chaque acteur termine son parcours à partir de son interface et seules les informations correspondant à ses droits sont visibles.

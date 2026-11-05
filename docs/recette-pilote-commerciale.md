# YEM — Recette pilote P0 : école partenaire (issue #50)

**Statut : à réaliser avec un véritable établissement partenaire.** Les tests CI ne prouvent pas le succès métier de la recette. Commencer exclusivement avec des données synthétiques ou anonymisées tant que la protection et la restauration ne sont pas prouvées.

## Rôles participant à la recette
- Référent YEM : installation, suivi des anomalies, configuration et sécurité.
- Direction de l'école : organisation, année, décisions et approbations.
- Secrétariat : saisie et import des dossiers, admissions, inscriptions.
- Enseignant : cours, présence, notes, évaluations.
- Caissier/économe : encaissements, remise, fermeture de caisse, sans pouvoir d'approbation autonome.
- Comptable ou contrôleur : validation, rapprochement, refus et audit.
- Parent pilote : Android, compte vérifié, plusieurs enfants et écoles.
- Observateur indépendant : chronométrage, validation contradictoire des résultats.

## Scénarios et critères bloquants

| ID | Scénario | Preuve attendue |
|---|---|---|
| YEM-01 | Créer maternelle/école primaire/collège/lycée et groupe scolaire | Typologie, cycles et membres indépendants ; options selon établissement |
| YEM-02 | Attribuer rôles, cumul, postes vacants, délégations | Aucune permission financière apparue par cumul non autorisé ; audit |
| YEM-03 | Deux écoles avec utilisateurs et classes identiques | Aucune lecture ni écriture inter-écoles |
| YEM-04 | Créer une année, classes et capacités | Refus de dépassement, notamment en concurrence |
| YEM-05 | Importer fichier Excel A avec 10 élèves | En-têtes auto-proposés, mapping validé, 10 élèves, 0 doublon |
| YEM-06 | Importer fichier Excel B avec 10 élèves et champs différents | 10 autres élèves, aucune confusion d'école, dossiers incomplets signalés |
| YEM-07 | Fichier mauvais, doublons, réimport, quotas | Prévisualisation sans écriture, correction, idempotence, aucun import partiel |
| YEM-08 | Export CSV des élèves | Données école uniquement, caractères dangereux neutralisés, journal |
| YEM-09 | Admissions directes/concours/orientation | Validation humaine des justificatifs, places et statuts |
| YEM-10 | Responsables légaux et multi-enfants | Accès seulement après vérification du lien avec l'enfant |
| YEM-11 | Absences, retards, correction motivée | Historique et droits limités |
| YEM-12 | Cours, planning et salle occupée | Aucun conflit professeur/salle/classe accepté |
| YEM-13 | Notes, barèmes 10/20/100, coefficients et absences | Moyennes et pondérations conformes au règlement configuré |
| YEM-14 | Bulletin officiel PDF A4, publication, rectification | PDF lisible, original immuable, correction traçable |
| YEM-15 | Conseil de classe, délibérations | Décisions validées, procès-verbal consultable |
| YEM-16 | Tarifs, paiements manuels, reçus, paiements partiels | Montants justes, justificatifs numérotés, aucun double-enregistrement |
| YEM-17 | Rôles direction, caisse, comptable, approbateur | Séparation des tâches imposée à chaque opération sensible |
| YEM-18 | Clôture de caisse, remise, différence de solde | Contrôle indépendant, audit complet, aucun effacement |
| YEM-19 | Parent Android : installer la PWA, choisir école, candidater | Chargement et navigation accessibles, cycle et accès corrects |
| YEM-20 | Connexion interrompue et double clic | Pas de paiement accepté sans serveur, pas de notes silencieusement perdues |
| YEM-21 | SMTP réel, lien d'activation, oubli mot de passe | Message reçu, renvoi sécurisé, aucune divulgation de compte |
| YEM-22 | Notifications Web Push téléphone verrouillé | Aucune réussite avant test réel VAPID/permission/service worker |
| YEM-23 | Mobile Money Airtel/Moov | **NON EXÉCUTÉ** tant que contrat prestataire, clés et vérification officielle ne sont pas fournis |
| YEM-24 | Sauvegarder, restaurer sur environnement isolé | Script, horodatage, procès-verbal, restauration fonctionnelle ; issue #49 |
| YEM-25 | Révoquer personnel et parent, MFA, accès API | Accès interrompu partout, données privées non exposées |

Les cas YEM-21 à YEM-24 dépendent d'opérateurs, d'appareils réels ou de l'hébergeur. Ne pas simuler leur réussite en remplaçant la preuve par une case cochée.

## Mesures opérationnelles
Consigner pour chaque scénario : date, type d'école, rôles utilisés, plateforme, durée mesurée, données de test, résultat PASSED/FAILED/BLOCKED, capture non nominative et anomalie GitHub. Sur un pilote, mesurer en particulier le temps d'inscription d'un élève, d'importation de 10/100 dossiers, d'édition d'un bulletin et de fermeture de caisse.

## Protocole de sortie
1. Validation de la sécurité de la base et des sauvegardes restaurables.
2. Les scénarios P0 réussissent sur **deux profils d'école différents** au minimum, sans anomalie bloquante.
3. Responsable établissement et contrôleur YEM signent le PV de recette, avec restrictions commerciales visibles (par exemple pas de Mobile Money tant qu'inactif).
4. Former secrétariat/enseignants/caisse/parents sur les écrans réels.
5. Démarrage encadré, limitation des utilisateurs, procédure d'assistance et de retour arrière.
6. Reprise des données réelles uniquement avec consentements/autorités appropriés et politique de conservation.

## Test automatisé supplémentaire
Le test Django test_pilot_two_distinct_school_registers_ten_students_each vérifie la création de 20 élèves répartis entre deux écoles à colonnes CSV différentes. **Ce test est synthétique**, et ne se substitue pas aux deux fichiers Excel utilisateur ni à la validation terrain.

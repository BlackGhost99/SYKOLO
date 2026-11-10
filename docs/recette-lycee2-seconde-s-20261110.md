# Recette d'inscription directe — Lycée Privé 2 / Seconde S (10 novembre 2026)

## Objectif
Valider une chaîne réelle du point de vue métier, **sans confondre un paiement simulé avec un encaissement effectif** :
compte parent → profil enfant → catalogue → candidature directe → paiement de test → réception au secrétariat → vérification des pièces → décision proviseur → inscription officielle → matricule → accès parents, vie scolaire, études et enseignant affecté.

## État contrôlé en base YEM au 10/11/2026
- Lycée Privé 2 : actif ; année 2026–2027 en cours ; annuaire public publié ; espèces acceptées.
- Classe « Seconde S » absente ; « Seconde A (démo) » présente, sans filière.
- Aucun tarif de dossier, aucune passerelle de paiement configurés.
- Aucune candidature parent, aucun paiement parent enregistrés.
- Membres actifs : direction, propriétaire, proviseur, vie scolaire. Pas de comptes actifs identifiés pour secrétariat, études et professeur dans les membres du lycée.
- Rôles « vie_scolaire » et « etudes » ne possèdent pas school.students.read dans les permissions de ce lycée ; **ne pas accorder l'accès à tous les dossiers d'élèves** pour régler uniquement l'affichage d'une liste de classe.

## Test automatisé associé
`backend/institutions/test_lycee2_parent_journey.py` reproduit le dossier dans une **base Django temporaire** ; aucun compte, classe, élève ou paiement de production n'est créé.

Montant de test (non tarif commercial) : 2 500 FCFA ; passerelle PayCentral sandbox ; événement de confirmation signé fictif. La transaction doit rester marquée « Paiement SIMULÉ : aucune somme reçue », et `paid_confirmed` doit rester faux.

Le parcours exige une vérification indépendante de chaque pièce documentaire ; le secrétariat enregistre les références, le proviseur les contrôle et statue, puis le secrétariat convertit la candidature. Le matricule doit apparaître sur le dossier élève. L'association du parent au dossier doit être contrôlée par l'établissement après inscription.

## Préparation nécessaire pour le scénario interactif de production
1. Vérifier les sauvegardes et ne créer que des identités fictives clairement identifiées TEST.
2. Ouvrir volontairement au Lycée 2 une série de Seconde réellement souhaitée (« S », « S1 », « S2 » ou « SU » selon l'école) et une division ; laisser les classes de démonstration à part ou les archiver avec prudence.
3. Créer un **tarif fictif explicitement non exigible** dans une instance de test. Ne pas configurer de clé marchand réelle à seule fin d'une recette.
4. Préparer les comptes de test : parent, secrétariat, proviseur, études, vie scolaire, économe, enseignant. Les droits doivent rester limités à leur métier ; les actions du proviseur et du secrétariat ne doivent pas partager un compte.
5. Tester le portail parent avec les vraies interfaces PC et Android : statut d'activation (pilotage de l'activation e-mail), catalogue, profil enfant, dépôt direct, retour de suivi.
6. Contrôler la réception dans « Admissions », l'historique, la vérification de pièces, la décision, puis la conversion.
7. Contrôler le matricule unique, la classe et l'année, la fiche élève, le responsable légal vérifié, les écrans caisse/finances.
8. Contrôler la vue de chaque poste **à permissions minimales** : secrétariat (dossier + suivi), proviseur (validation + rapport), vie scolaire (liste de classe et présence), études (classe + scolarité), enseignant (seuls élèves des cours affectés), économat (frais et reçus), parents (leur enfant seulement), super-admin (audit sans encaissement).
9. Tester les refus : doublon, capacité atteinte, série archivée, documents non vérifiés, accès d'une autre école, paiement non signé, paiement sandbox faussement comptabilisé, renouvellement d'année.
10. Faire un contrôle manuel après déploiement ; une CI verte n'est pas une recette réelle navigateur/production.

## Points produits non résolus
- Il manque une vue restreinte des effectifs/présences pour la vie scolaire et une vue des classes/élèves pédagogiques pour les études. Éviter de leur attribuer en masse `school.students.read` qui ouvre les données personnelles du dossier entier.
- Les enseignants ont besoin d'une liste uniquement des élèves de leurs classes/cours affectés, sans accès aux dossiers des autres classes.
- La candidature et son paiement ne suffisent pas à rendre un élève inscrit ; l'admission formelle et la conversion restent deux décisions distinctes. Les paiements de candidature et les frais de scolarité sont séparés. Le suivi doit clarifier « en attente », « accepté », « inscrit », « paiements réels » versus « simulés ».
- La consultation par les parents de la fiche scolaire exige attribution du rôle parent **et** vérification du lien légal par un responsable de l'établissement.

**Interdiction :** ne pas injecter directement dans Supabase un paiement `success`, un matricule ou une appartenance d'école pour masquer un blocage d'API.

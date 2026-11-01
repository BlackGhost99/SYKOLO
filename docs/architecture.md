# Fondations et décisions

## Première tranche

L’atelier pédagogique permet de valider le vocabulaire et les paramètres avant d’introduire les dossiers scolaires. Aucun compte, élève, paiement, secret ou donnée institutionnelle partagé n’est stocké sur le serveur. Le transport HTTP reste séparé du domaine. Le même validateur et le même calcul fonctionnent dans le navigateur et dans l’API.

## Contrat de configuration v1

`schemaVersion`, `name`, `scale {kind,max}`, `precision`, `missing`, `bands [{min,label,value}]`, `report {showScore,showLabel}`, `notification {enabled,below,message}`.

Les bandes couvrent [0,100] par seuil inférieur inclus ; le seuil suivant est exclu. Le premier seuil est obligatoirement zéro. Le dernier couvre jusqu’à 100 inclus. Les seuils et libellés sont uniques. Les équivalences des catégories sont choisies par l’établissement dans leur bande. La note numérique est normalisée en pourcentage avant pondération ; chaque coefficient est strictement positif. Les seuils et alertes utilisent le résultat non arrondi. L’arrondi n’affecte que l’affichage chiffré. Une absence est exclue ou vaut zéro selon le profil ; si toutes les notes sont exclues, le résultat est absent.

La liste des types supportés et la version du schéma constituent des contrats techniques. Les maxima, seuils, libellés, coefficients, règles d’absence, options de bulletin et seuils de notification sont des données configurables. Les modèles résident dans un fichier distinct et sont clonés avant modification.

## Prochaine tranche : écoles, identité et accès

Introduire PostgreSQL, migrations et authentification avant de stocker des données réelles. Modèles prévus : organisation/fondateur, école, campus, année, cycle configurable, utilisateur, adhésion et permissions. Les rôles pressentis sont super administrateur, fondateur, directeur, comptable/économe, secrétaire, enseignant, parent et apprenant. Les permissions seront contrôlées côté serveur par action et périmètre, avec tests d’isolation inter-écoles. Le fondateur peut superviser plusieurs écoles ; ses droits ne seront pas assimilés automatiquement à ceux du directeur.

Les configurations institutionnelles devront être versionnées et publiées dans un périmètre école/année/cycle/classe. L’héritage et les dérogations devront être explicites. Un bulletin publié conservera un instantané de sa configuration et de ses résultats : modifier un profil ne doit jamais réécrire l’historique. Prévoir historique d’audit et concurrence optimiste. Le stockage local actuel sera remplacé par un adaptateur de persistance sans modifier le moteur.

## Modules suivants

1. Inscriptions : capacités et places, dossiers en ligne et au secrétariat, confirmation après paiement vérifié. Aucun dossier ne devient inscrit uniquement parce que les coordonnées sont saisies.
2. Évaluations : matières, compétences, catégories et coefficients configurables ; barèmes propres aux évaluations et conversion explicite.
3. Bulletins : modèles et sections configurables, périodes, signatures, publication, historique et exports.
4. Finances : facturation, reçus, rapprochements et prestataires de paiement idempotents.
5. Notifications : événements, destinataires, canaux, consentements et modèles configurables ; file transactionnelle, déduplication et journal d’envoi.

Ni grille tarifaire, ni pondération nationale, ni seuil de réussite universel n’est fixé à ce stade.

## Sécurité et exploitation de cette version

API de calcul sans état et sans CORS permissif ; schéma validé, limites de taille et de nombre d’entrées. Fichiers publics servis par liste explicite. Textes importés affichés par `textContent` ; CSP sans scripts inline, protections contre l’intégration en iframe. Avant ouverture à des données réelles, ajouter authentification, contrôle d’accès, limitation de débit, audit, sauvegardes et tests d’isolation. La présente API publique n’est pas un espace d’administration sécurisé.

## Validation et livraisons

Les tests couvrent échelles, pondérations, catégories, absences, seuils, arrondis, imports invalides et contrat HTTP. La CI exécute vérifications syntaxiques et tests sur chaque branche de module et PR. Render exécute aussi les tests pendant le build. La vérification de livraison exige un déploiement `live`, le SHA de fusion dans `/healthz`, le chargement de la page et un calcul API réussi.

# YEM — Module 14 : admissions et préinscriptions internes

Ce module prépare une inscription avant de créer le dossier officiel de l'élève (module 05). Une candidature peut provenir d'un guichet, d'une demande saisie par le personnel à la suite d'un contact en ligne, ou d'un autre canal librement codé. **Aucun formulaire de collecte publique n'est exposé** à ce stade : la création nécessite une session d'un membre autorisé, avec contrôle CSRF. La collecte en libre-service exigera sa propre authentification, anti-abus et politique de confidentialité.

## Cycle de vie

`submitted` → `review` → `accepted` ou `rejected` ; l'étape d'étude peut être sautée selon l'organisation. Une candidature acceptée peut ensuite passer à `enrolled` par conversion explicite. Une décision refusée ne peut pas être transformée en inscription. Acceptation et refus exigent une justification rédigée par un décideur autorisé ; toute transition produit un événement de suivi non modifiable.

Le personnel saisit le nom, le prénom et l'éventuelle naissance de l'élève, le contact de son responsable, l'année, la classe sollicitée, le canal de candidature et éventuellement la référence à une fiche élève existante. Le statut de décision est administratif et distinct des codes de délibération pédagogique, qui restent configurables au module 10.

## Gestion des capacités et intégration

La capacité d'une classe est celle configurée au module 04. L'API `/admissions/capacity/{classroom_id}` expose le nombre d'inscrits, les candidatures acceptées en attente et les places restantes pour l'inscription effective. Une décision favorable **ne réserve pas de place** : la capacité est revérifiée sous verrou transactionnel de classe, au moment où le personnel transforme la candidature en inscription. Cela évite de promettre une place indisponible si d'autres admissions ont été effectuées entre-temps.

La conversion appelle les mêmes contrôles que le module 05, crée le matricule et le dossier élève (ou utilise une fiche existante vérifiée), l'inscription de l'année, le responsable légal principal pour un nouvel élève, ainsi que l'événement d'inscription. Tout cela s'effectue dans une seule transaction : une défaillance ne doit laisser ni inscription ni fiche partielle. Un second appel de conversion renvoie la même inscription au lieu de la dupliquer.

Les éventuels frais scolaires ne sont **pas encaissés automatiquement** : l'établissement continue d'utiliser le registre du module 11, sans paiement réel externe dans cette version.

## Sécurité

Permissions distinctes : `school.admissions.read`, `school.admissions.manage`, `school.admissions.decide`, `school.admissions.enroll`. Direction : tous les droits ; secrétariat : lecture, saisie et inscription après décision, mais pas la décision ; enseignant/parent : aucun accès à ces dossiers par défaut. La conversion exige également `school.students.manage`.

Chaque requête est isolée par établissement. Les événements internes donnent une piste d'audit des étapes, avec acteur, motif et horodatage. Les dossiers restent privés, jamais dans la zone publique de démonstration. Pas de suppression physique via API.

## API

Préfixe `/api/v1/schools/{school_id}` :

- `GET/POST /admissions` — liste filtrable par année, classe, statut ; saisie
- `GET /admissions/{id}` — candidature
- `POST /admissions/{id}/decide` — `{revision,status,reason}`
- `POST /admissions/{id}/convert` — `{revision,enrolled_on,student_code}` ; matricule vide uniquement pour un élève déjà connu
- `GET /admissions/{id}/history` — historique
- `GET /admissions/capacity/{class_id}` — disponibilité informative

Les données de test sont fictives. Le module n'est pas une recette sur Render ni une admission libre-service.

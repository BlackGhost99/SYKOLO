# YEM — Module 14 : admissions et préinscriptions internes

Ce module prépare une inscription avant de créer le dossier officiel de l'élève (module 05). Une candidature peut provenir d'un guichet, d'une demande saisie par le personnel ou du **portail parent authentifié**. Les routes internes de création exigent les permissions du personnel et CSRF ; l'espace parent dispose de routes distinctes et n'autorise que la candidature d'un enfant appartenant au compte familial. La candidature ne donne ni accès à une fiche scolaire officielle ni droit automatique à une place.

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


## Extension 2026 — Voies d'admission, concours et orientation (module 1 de la feuille de route)

YEM sépare désormais trois voies de candidature : `direct` (inscription directe), `concours` (concours ou test) et `orientation` (affectation par une autorité ou établissement partenaire). Le champ `source` conserve le **canal de collecte** (guichet, téléphone, etc.) et ne désigne plus le type d'admission.

L'orientation peut résulter de l'admission au CEP / d'un concours, notamment pour des élèves orientés en sixième vers des établissements privés partenaires. **Une même candidature d'orientation peut exiger à la fois `concours_result` et `orientation_decision`** dans la configuration du niveau de sixième : cela représente sans ambiguïté le cas « concours réussi puis affectation ». Les références externes restent déclaratives jusqu'à leur contrôle par une personne habilitée. Aucune intégration automatique KEWA, Xgest ou gouvernementale n'est revendiquée.

### Règles configurables

Une `AdmissionPolicy` est définie pour une année scolaire et éventuellement un niveau précis. Elle contient les voies autorisées et des listes de codes de pièces obligatoires par voie. La portée `niveau` remplace celle de l'année lorsque définie. L'API impose une révision optimiste : une modification concurrente est rejetée en 409. La configuration est gérée uniquement par une personne habilitée à décider des admissions, et peut être différente dans chaque établissement.

À la création d'une candidature, la liste des pièces requises est **figée** dans `required_documents`. Changer la politique ultérieurement ne modifie pas rétroactivement les anciens dossiers. Pour les voies `concours` et `orientation`, les justificatifs `concours_result` et `orientation_decision` restent systématiquement obligatoires même si un administrateur supprime leur code de la grille personnalisée.

### Contrôle de l'éligibilité

L'éligibilité déclarée (`pending`, `eligible`, `ineligible`) est distincte du résultat administratif d'admission (`submitted`, `review`, `accepted`, `rejected`, `enrolled`). Le secrétariat peut enregistrer la référence de décision / concours, l'autorité qui a émis l'affectation et les références des justificatifs. Une direction autorisée contrôle chaque référence et attribue `verified` ou `rejected`, avec motif et trace horodatée.

Le passage à `accepted` est refusé si l'éligibilité n'est pas marquée `eligible`, si la référence est manquante ou si les pièces requises ne sont pas vérifiées. L'orientation exige en outre le nom de l'autorité compétente. **Même un concours déclaré réussi et un dossier admissible ne créent aucune inscription** : il faut ensuite appeler explicitement `convert`, qui revérifie année, capacité de la classe, matricule et restrictions multi-sociétés.

La saisie actuelle porte sur les références des documents consultés par le personnel ; **les fichiers sources ne sont pas téléchargés et ne sont pas conservés en clair** dans ce module. La gestion future des fichiers devra passer par un stockage privé, des contrôles antivirus, de type MIME, d'accès et de durée de conservation avant l'activation pour des dossiers d'enfants réels.

### Nouvelles API

Même préfixe `/api/v1/schools/{school_id}` :

- `GET /admissions/policy?year={uuid}&level={uuid}` — politique applicable et révision exacte de la portée demandée.
- `POST /admissions/policy` — `{year,level,revision,enabled_routes,required_documents}` ; décisionnaire uniquement.
- `POST /admissions` — champs historiques + `route`, `origin_school`, `route_reference`, `orientation_authority`.
- `GET/POST /admissions/{id}/documents` — consultation et ajout d'une référence `{revision,code,reference}`.
- `POST /admissions/{id}/documents/{document_id}/review` — `{revision,status,reason}`.
- `POST /admissions/{id}/eligibility` — `{revision,result,route_reference,orientation_authority,reason}`.
- `GET /admissions?route=concours|orientation|direct` — filtre de la liste.

### Sources et limites

Références contextuelles Gabon :
- Journal officiel, réglementation CEP et orientation en sixième : https://journal-officiel.ga/6388-448-pr-menestfprscjs-/
- AGP, lancement commission orientation 6e du 20 juillet 2026 : https://agpgabon.ga/gabon-education-lancement-des-travaux-de-la-commission-dorientation-en-6/
- AGP, résultats publiés le 8 août 2026 via KEWA : https://agpgabon.ga/gabon-orientation-en-6e-resultats-de-la-commission-disponibles/

La configuration est une capacité métier et ne remplace pas une décision publique officielle. Les formulaires ouverts aux familles, le téléversement des originaux et les imports vérifiés par API nationale restent des chantiers séparés, nécessitant des garanties de confidentialité et une validation administrative.

## M2.3 — Préparation explicite de la décision d'admission

Les réponses des candidatures (`GET /admissions`, `GET /admissions/{id}`) incluent désormais le champ `acceptance_blocker` : chaîne décrivant le blocage ou `null` lorsque les contrôles préalables sont satisfaits.

Pour l'admission directe, les pièces exigées sont définies par établissement, année et niveau. Pour un concours, un résultat éligible, une référence et le justificatif **vérifié par une personne habilitée** restent obligatoires. L'orientation exige également la référence et l'autorité compétente. Le secrétariat peut enregistrer les éléments sans se substituer au décideur.

L'interface explique le blocage et désactive le bouton **Accepter** lorsque le dossier n'est pas prêt. Il ne s'agit que d'une aide : **le serveur revérifie la condition dans la transaction de décision** ; aucune protection n'est déléguée à l'interface.

**Une admission favorable n'est pas une inscription définitive.** Paiement confirmé ou bourse approuvée, capacité de la classe et règles d'inscription sont contrôlés séparément lors de la conversion.

Tests : `institutions.test_admissions` (voie directe et concours) et `AdmissionRoutesPanel.test.jsx` (affichage et distinction inscription/paiement). Les vérifications techniques doivent précéder le déploiement.

## M2.4 — Réception administrative et décision séparées

- **Secrétariat (`school.admissions.manage`) :** crée les dossiers et enregistre les pièces, références et résultats déclaratifs. Peut déplacer une candidature de `submitted` (Déposée) vers `review` (En étude), avec une trace d'audit nominative. Ne peut jamais accepter ni refuser sans le droit de décision.
- **Direction / décideur (`school.admissions.decide`) :** vérifie ou rejette les justificatifs, puis accepte ou refuse la candidature avec motif. Les conditions de concours, d'orientation et de pièces obligatoires restent validées côté serveur sous verrou transactionnel.
- **Économe / caisse (`school.finance.receive`) :** confirme le règlement selon les règles financières, mais ne peut pas décider de l'admission.
- **Lecteur seul (`school.admissions.read`) :** consulte le dossier sans saisir, modifier ni valider les pièces ; les actions sont masquées dans l'interface, et les permissions continuent d'être contrôlées par le serveur.

Le point d'entrée de transition ne change pas : `POST /api/v1/schools/{school_id}/admissions/{id}/decide` avec `{revision,status,reason}`. Le droit nécessaire dépend **strictement du nouveau statut** : `review` exige `school.admissions.manage`, `accepted` et `rejected` exigent `school.admissions.decide`. Les changements sont soumis à une révision optimiste et à la machine à états, sans possibilité de rouvrir une décision finale. Les événements de suivi sont append-only ; `admission_review_started` distingue l'ouverture de l'étude d'une décision.

La séparation ne change pas les conditions de finalisation : **admission favorable ne signifie pas inscription officielle**, laquelle attend paiement confirmé ou bourse validée, capacité et année scolaire adaptées. Les essais réalisés avec les rôles réels en interface resteront à effectuer après déploiement.


## M2.5 — Relais Admissions → Finances et bourses proportionnelles

La règle du produit est **unique** : `Candidature déposée → En étude → Admission acceptée → Finances (paiement/bourse) → Inscription définitive → Matricule et classe`. Une classe demandée n'est **pas** une inscription. Le module Paiements prend le relais ; le secrétariat ne valide l'inscription qu'une fois les frais **exigibles à l'inscription** réglés ou entièrement couverts. La scolarité annuelle conserve ses échéances futures.

**Dossier guichet :** l'établissement peut créer une candidature directe sans compte parent. Son tarif d'inscription est figé sur le dossier et apparaît dans la caisse des admissions du module Finances. L'économe peut enregistrer les espèces réellement reçues sur la candidature elle-même, produire un reçu et transmettre la confirmation au secrétariat. Les dossiers parents restent reliés à leur propre compte et bénéficient des mêmes statuts.

**Bourse :** le responsable habilité active « Élève boursier », fournit la référence de décision officielle et choisit la portée `all` (inscription + scolarité), `admission` ou `tuition`. La couverture peut être **totale** (100 %) ou **partielle** (pourcentage de 1 à 99 ou montant fixe en FCFA). L'API conserve la part couverte et calcule exactement le solde d'inscription. Une couverture partielle ne constitue **jamais** un justificatif de règlement du reste dû ; la caisse/PayCentral/SingPay encaissent uniquement ce solde.

La prise en charge des échéances de scolarité est représentée séparément des reçus : chaque `FeeCharge` conserve le montant brut du barème et un `scholarship_discount`, et sa dette nette est `amount - scholarship_discount - payments_validés`. L'affectation de ces charges est automatique après création de l'inscription officielle. Les frais couverts entièrement ne créent aucune dette. Les bourses en pourcentage s'appliquent également aux nouvelles échéances ; pour un montant fixe, les allocations sont figées par tarif à l'approbation afin de ne pas dépasser la prise en charge officielle.

**Sécurité :** aucun paiement fictif n'est créé par une bourse. Une bourse ne peut pas remplacer une recette réelle non remboursée ni des opérations en ligne ouvertes ; inversement, une bourse couvrant totalement l'inscription interdit toute nouvelle demande de paiement. Un montant restant peut être payé en espèces ou en ligne avec le même numéro de candidature. Un dossier définitivement inscrit ne peut plus recevoir d'encaissement d'admission. La désactivation de nouvelles bourses ne révoque pas celles déjà validées.

**Tests requis :** guichet direct → caisse → reçu → inscription ; parent avec bourse partielle → calcul exact du reste → espèces ; bourse totale → zéro paiement ; scolarité avec charges nettes et plafonds ; règles de rôle secrétariat/direction/caissier ; non-régression du paiement en ligne ; migrations et Docker. Les opérations en ligne sont soumises à la confirmation signée du prestataire ; SingPay reste inactif jusqu'à certification de son contrat.

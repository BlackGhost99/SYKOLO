# YEM — espaces scolaires par année (2026–2027, 2027–2028…)

## Principe
Une **seule application par établissement** et des années scolaires isolées par les clés `AcademicYear`. Les classes, inscriptions, affectations de classe, cours, évaluations, bulletins, créneaux et emplois du temps sont déjà rattachés à une année. Les niveaux, cycles et fiches du personnel sont, eux, des **référentiels permanents** de l'école : ils ne doivent pas être dupliqués à chaque rentrée.

## Écran réel
Paramètres → Classes de l'établissement → Années et cycles → Années scolaires. Choisir une année affiche son calendrier (dates et périodes), ses classes, ses effectifs et ses totaux de notes/bulletins/affectations **selon les droits du compte**. La sélection d'une année passée est en lecture historique. Les classes et périodes éditées depuis l'onglet Structure académique sont filtrées par la sélection faite dans l'espace annuel.

## Préparer la rentrée suivante
L'école choisit **code**, **nom**, **date de début**, **date de fin**. Une proposition de décalage d'un an sert d'aide à la saisie et n'est **pas** une date officielle gabonaise. Les dates sont modifiables. Les années d'un même établissement ne peuvent pas se chevaucher dans ce parcours.

Il est possible de copier **uniquement les classes actives** (nom, niveau, filière, capacité) de l'année précédente. L'année créée possède de **nouveaux identifiants de classes** et repart avec :
- zéro inscription d'élève ;
- zéro affectation de professeur à une classe ;
- zéro évaluation ou bulletin ;
- zéro créneau ou emploi du temps ;
- zéro échéance/frais/encaissement ;
- aucune période prédéfinie.

Les trimestres/semestres sont ensuite ajoutés en choisissant leurs dates propres. Les enseignants existants sont conservés comme personnes, puis affectés aux classes de la **nouvelle année**. Les nouvelles personnes sont ajoutées avec le formulaire « Ajouter un collaborateur ».

## API
- `GET /api/v1/schools/<uuid>/academic/annual-snapshot?year=<uuid>` : années, résumé des classes et périodes, nombres filtrés par droits et cycles.
- `POST /api/v1/schools/<uuid>/academic/prepare-year` : champs `code`, `name`, `start_date`, `end_date`, `source_year` (UUID ou null), `copy_classes` (booléen) ; transaction unique, permission `school.academic.manage` et absence de restriction de cycle.

L'API ne convertit jamais l'année de référence en année suivante ni ne modifie les inscriptions du passé.

## Fonctions du personnel
Le formulaire « Ajouter un collaborateur » affiche désormais directement un menu « Choisir une fonction à ajouter ». Les fonctions proviennent de l'**organigramme**, distinct du catalogue de fonctions de connexion. Si le profil école est `non_classe` ou ne contient aucun cycle enseigné, un message explique explicitement qu'une classification est nécessaire dans la **console de la plateforme**, sans inventer un cycle à partir du nom « Lycée ».

Les nominations sont professionnelles, séparées des **permissions YEM**. Seules les fonctions de compte autorisées alimentent la liste de fonctions du compte créé.

## À contrôler sur l'établissement pilote
1. Vérifier que la fiche de l'établissement est classifiée (lycée général / collège / lycée technique / groupe) et que les cycles correspondants sont cochés dans la console plateforme. Si ce n'est pas fait, les postes ne s'afficheront pas.
2. Préparer 2027–2028 en copiant les classes actives de 2026–2027. Confirmer que les deux années ont des classes avec identifiants distincts.
3. Vérifier que les inscriptions, évaluations, bulletins, frais et paiements de 2026–2027 sont inchangés et **absents** de 2027–2028.
4. Ajouter les périodes et réaffecter les professeurs en 2027–2028, puis consulter de nouveau l'année historique.
5. Vérifier le périmètre d'un gestionnaire limité à un cycle : il ne peut ni préparer toute une nouvelle année ni voir les effectifs des cycles exclus.

**Sélection globale** : l'en-tête de l'établissement propose une année scolaire de travail. Le filtre est transmis aux vues élèves/finances, classes, évaluations, bulletins, absences, emplois du temps et affectations. Quand un module dispose d'un sélecteur d'année, celui-ci met à jour l'en-tête. Les cours, matières et autres référentiels de configuration demeurent gérés dans leurs modules métier ; les permissions et contrôles annuels côté serveur restent la source de vérité.

**Limite** : les données permanentes (identité des élèves, fiche du personnel, cycles, niveaux) appartiennent à l'établissement, pas à une année. Leur consultation peut rester globale tandis que leurs inscriptions, affectations et résultats sont filtrés par année. Les archivages bloquent la modification de classes/périodes historiques via l'API académique, mais il ne faut pas assimiler ce mécanisme à un gel réglementaire exhaustif de toutes les écritures de tous les modules.

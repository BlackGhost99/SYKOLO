# YEM — Import Excel/CSV adaptatif et sécurisé (P0)

## Objectif
Supprimer le CSV à colonnes fixes. Les écoles apportent leurs propres feuilles XLSX ou CSV, sélectionnent la feuille et la ligne d'en-tête, associent librement les colonnes aux champs YEM, y compris les questions personnalisées configurées sur leur fiche d'inscription.

## Interface
Élèves > Importer : sélectionner le fichier ; YEM affiche feuilles, colonnes, propositions de correspondance, exemples, année scolaire et modèles précédemment enregistrés. Le gestionnaire confirme ou corrige le mapping. Un aperçu sans aucune écriture affiche les erreurs ligne par ligne (validation, doublons, classes, quotas et capacité). L'utilisateur décide ensuite de confirmer le lot complet. Un modèle de correspondance peut être enregistré pour son établissement et réutilisé sur ses prochaines feuilles.

## Sécurité et contrôles
- Accès réservé au droit school.students.manage, avec session et CSRF.
- Fichiers de 3 Mio maximum, 500 élèves / 60 colonnes par lot. Import XLSX en lecture seule et sans macros ; volume décompressé limité. CSV UTF-8/Windows-1252.
- Aucun document n'est enregistré côté serveur : le fichier doit être retransmis pour la confirmation.
- Prévisualisation signée côté Django, limitée à 15 minutes, liée à l'école, à l'utilisateur, au hachage du fichier, aux correspondances, à l'année, à la feuille, à la ligne de titre et à la révision du formulaire.
- Au clic de confirmation : verrou exclusif de l'école, nouvelle validation de toutes les lignes, comparaison des doublons, quotas, capacités, puis transaction SQL tout ou rien. Aucun frais, paiement, compte parent ou justificatif d'identité n'est automatiquement créé.
- Les imports réussis conservent un identifiant de lot, un nombre d'élèves et une empreinte de référence (sans conserver les données brutes ou le fichier). Ré-import du même lot : réponse idempotente sans création supplémentaire. Audit par établissement.
- Tout champ étranger aux fiches de YEM doit d'abord être configuré dans Fiche d'inscription, avec type et droits adaptés ; aucune création silencieuse de champ sensible.
- Un élève homonyme ou déjà connu exige une résolution humaine, sans écraser un dossier ni ses finances.
- Les modèles enregistrés contiennent seulement les en-têtes et la correspondance, jamais de valeurs d'élèves.

## Limites connues et suites
Cette livraison couvre le référentiel élèves, un responsable principal et l'inscription facultative dans une classe existante. Les importations personnel, enseignants, historiques de bulletins, soldes financiers et rapprochements seront des modules séparés afin de préserver les permissions et les responsabilités financières. Pas d'import direct de documents médicaux, pas de rapprochement probabiliste automatique, pas de fusion automatique de doublons. Une matrice de fichiers anonymisés provenant de plusieurs écoles doit encore faire l'objet d'une recette.


## Export CSV (extension P0)
Les gestionnaires détenteurs du droit school.students.manage peuvent télécharger sur demande explicite un export CSV de leur école, facultativement limité à une année scolaire. Il comprend identité élève, classe et année, responsable légal principal et champs personnalisés visibles à l'école. L'export ne comprend pas les paiements, mots de passe, comptes parents ou justificatifs.

L'export est servi en téléchargement privé non mis en cache ; les champs texte qui pourraient être interprétés comme formules Excel sont neutralisés. Les opérations sont auditées, les fichiers restent sous la responsabilité de l'établissement et ne doivent pas être envoyés via des canaux non sécurisés. Limite 10 000 élèves par export, au-delà fractionner par année. L'API est POST /api/v1/schools/{school_id}/imports/students/export avec un corps JSON facultatif {"year":"uuid"}.

Un registre élève sans colonne parent/tuteur reste importable. L'aperçu signale chaque dossier familial incomplet ; aucune identité familiale fictive ni aucun droit d'accès parent n'est créé. Une colonne téléphone du tuteur sans nom de tuteur est bloquée pour éviter une perte de donnée silencieuse. L'école régularise ces informations ensuite.

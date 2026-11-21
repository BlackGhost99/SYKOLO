# YEM — Sorties B3 : demandes scolaires prioritaires

Référentiel : cahier des charges du Chantier B, sections 5–7, scénarios de recette n° 1 à 9, et phase B3.

## Périmètre réel livré par cette branche

Une demande de besoin pédagogique ou scolaire du personnel est conservée dans **`OperatingSchoolRequest`**. **Ce modèle n'est PAS un `OperatingExpense`** et ne peut ni engager un budget, ni modifier les encaissements, ni déclencher un paiement. Un document approuvé dans ce module signifie **« validé pour instruction budgétaire »** ; la conversion dans le circuit engagements/achats et la réception relèvent de B5.

Chaque demande possède :
- demandeur identifié automatiquement, rôle/fonction historisé(e), service, motif et objet ;
- année scolaire, catégorie et sous-catégorie, centre de coûts facultatif (pôle **S1 scolarité** uniquement) ;
- quantité, prix unitaire estimé facultatif, montant estimé, devise ;
- fournisseur ou bénéficiaire pressenti, urgence **normale / prioritaire / urgente**, date souhaitée ;
- référence de justificatif facultative (ne constitue PAS encore une pièce jointe électronique) ;
- clef d'idempotence, révision, date de soumission, auteur des contrôles et historique append-only.

Parcours : **brouillon → soumise → en examen → validée pour instruction budgétaire**, ou refus motivé et révision puis nouvelle soumission, ou annulation du demandeur. Une décision n'est pas un décaissement et n'entre pas dans les montants `committed` / `paid`.

## Droits

- `school.operating.request` : permission distincte de la lecture du grand livre et de la caisse. Modèles `enseignant` et `secretariat` en bénéficient ; migration additive de rattrapage des rôles correspondants déjà existants. Les autres fonctions personnalisées peuvent la recevoir via la gestion ordinaire des rôles.
- `school.operating.manage` : peut aussi créer ses propres demandes, sans approbation automatique.
- `school.operating.approve` : peut consulter toutes les demandes et enregistrer une revue **indépendante** de l'auteur.
- Un demandeur non contrôleur ne voit et ne modifie **que ses propres demandes** ; le contrôleur peut lire toutes les demandes de son établissement, mais pas celles d'un autre établissement.
- **Aucune permission de paiement, de gestion des budgets ou de visibilité des salaires n'est conférée par `school.operating.request`.**
- Le propriétaire supervise mais ne reçoit pas ce nouveau droit de mutation par son seul rôle réservé.

## API

Base `/api/v1/schools/{school_id}/operating/` :
- `GET school-requests/options` : catégories actives, centres scolaires actifs, urgences ; pas d'informations sur les budgets ni fournisseurs.
- `GET/POST school-requests` : liste filtrable/limitée, création de brouillon.
- `GET/PATCH school-requests/{id}` : détails/historique, correction par l'auteur si brouillon ou refusée.
- `POST school-requests/{id}/submit` : soumission unique.
- `POST school-requests/{id}/review` : examen / validation de principe / refus motivé par contrôleur indépendant.
- `POST school-requests/{id}/cancel` : annulation historisée par le demandeur.

Tous les changements exigent un CSRF, la permission adéquate, un verrou transactionnel et un numéro de révision. Aucun appel direct à SingPay, à l'encaissement des élèves, aux salaires ou à un règlement externe.

## Interface

- Espace école → « Dépenses et budgets » → « Mes demandes et autorisations » : formulaire responsive, file paginée, filtres d'état, détail, décisions et historique.
- **Espace professeur mobile/PWA** → Accès rapides → « Demandes de matériel ». Aucun accès aux budgets ou aux paiements n'est exposé.

## Tests de ce sous-lot

- Enseignant, secrétariat, fonction personnalisée autorisée, isolement de l'établissement et restrictions parent.
- Quantité × prix unitaire, montant, catégorie, date souhaitée, urgence, exercice clôturé.
- Personnes et montants : impossibilité pour un autre enseignant de lire, modifier ou soumettre le dossier.
- Interdiction d'auto-validation, transitions versionnées et verrouillées, refus motivé, annulation, historique conservé.
- Rejeu idempotent, absence d'`OperatingExpense`, d'engagement, de paiement ou de modification de la scolarité.
- Tests React des formulaires et de la revue.

## Limites conservées volontairement hors de B3

Le téléchargement de vraies pièces justificatives PDF/image, le contrôle antivirus et les documents signés relèvent de B8. La décision budgétaire finale, les délégations par seuil/montant, les achats et la transformation contrôlée d'une demande en engagement relèvent de B5. Les paiements et rapprochements réels relèvent de B6. Le niveau d'urgence n'autorise jamais une auto-approbation.

## Sécurité de livraison

Migration `0087_operating_school_requests.py` en attente de production, avec protections RLS PostgreSQL. Vérifier la validation de toute la branche intégrée avec les entrées, les migrations depuis `main`, l'absence de collisions migratoires et la sauvegarde chiffrée/restaurée de Supabase YEM **avant fusion dans `main`** : Render a le déploiement automatique actif.

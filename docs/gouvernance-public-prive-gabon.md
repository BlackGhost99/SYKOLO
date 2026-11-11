# YEM — Gouvernance des établissements au Gabon (public et privé)

> Préparation d'implémentation — 11 novembre 2026. Ce module est un **référentiel de paramétrage**, pas une certification de conformité ou une délégation réglementaire de pouvoirs.

## Architecture retenue

Un seul moteur YEM ; trois régimes de gouvernance indépendants du type et des cycles pédagogiques.

- \`public\` : collège, lycée général ou technique administré dans le cadre des autorités publiques. Pas de rôle « propriétaire » ; premier compte confié à un chef d'établissement. Aucune capacité d'encaissement, d'approbation financière, d'annulation ou de tarification sensible dans les **modèles de rôle par défaut** de ce secteur. Les habilitations financières requièrent ensuite un processus distinct, documenté et audité.
- \`prive_laique\` : fondateur/promoteur ou organisme gestionnaire distinct des équipes pédagogiques ; conservation des outils privés existants, mais séparation caisse, comptabilité, tarif et validation.
- \`prive_confessionnel\` : même socle scolaire que le privé, avec une autorité confessionnelle et des fonctions **facultatives** (référent interne, responsable pastoral / aumônier). Cette affiliation ne donne aucun accès automatique aux notes, finances ou dossiers élèves.

Les anciens établissements sont classés par défaut \`prive_laique\` **sans modifier les personnes, comptes, classes, paiements, nominations ou permissions existants**. Leur régime doit être confirmé lors du déploiement initial.

Cette catégorisation est **par établissement**, pas par utilisateur : un même logiciel gère différentes écoles de statuts distincts. Les modèles restent modifiables et les fonctions nominatives ne confèrent pas de permissions.

## Régime, organe, fonction, rôle et droit : 5 concepts différents

1. **Régime** : public / privé laïc / privé confessionnel (configuration du School).
2. **Organe** : Conseil d'administration, Conseil d'établissement, Conseil de classe, Conseil d'orientation, Conseil de discipline ; Conseil de perfectionnement pour le technique. Un organe peut décider collectivement : ce n'est pas une personne habilitée à encaisser.
3. **Fonction** : Proviseur, Principal, Directeur des études, Censeur pédagogique, Censeur vie scolaire, Intendant, Économe, Surveillant général, Enseignant, Chef de travaux, etc. Une personne peut cumuler plusieurs fonctions et plusieurs cycles.
4. **Rôle applicatif** : ensemble personnalisable de permissions YEM sur une école.
5. **Portée d'accès** : établissement, cycle académique, classe, période ; l'autorisation sur la ressource doit être contrôlée côté API. Les fonctions ne donnent pas de permission technique.

La direction d'un établissement public n'est pas automatiquement la présidence de son conseil d'administration. Le fondateur n'est pas automatiquement le proviseur. La tutelle confessionnelle n'est pas l'inspection publique.

## Table de décision pour les presets

| Fonction métier | Collège | Lycée général | Lycée technique | Privé | Public |
|---|---|---|---|---|---|
| Chef d'établissement | Principal | Proviseur | Proviseur | Sous autorité gestionnaire / fondatrice | Sous tutelle publique |
| Pédagogie | Directeur des études | Censeur pédagogique | Directeurs des études formation initiale et continue | Suivi et validation pédagogique | Suivi et validation pédagogique |
| Vie scolaire | Surveillant général / Conseiller | Censeur vie scolaire et surveillants | Direction des études vie scolaire, SG | Vie scolaire et familles | Vie scolaire et familles |
| Gestion | Intendant, Économe | Intendant, Économe | Intendant, Économe | Recettes d'écolage et budget selon autorisations | Gestion des crédits et procédures publiques |
| Technique et stages | Facultatif | Facultatif | Chef des travaux, départements, stages | Selon offre autorisée | Selon offre autorisée |
| Gouvernance | Conseils | Conseils | + Conseil de perfectionnement | Promoteur / organisme gestionnaire | Conseil avec présidence publique selon textes |

**Ces libellés sont des propositions de paramétrage YEM** et non des affirmations selon lesquelles chaque établissement doit disposer de tous ces postes. Les établissements à faible effectif peuvent cumuler les fonctions **si autorisé** et si l'application des droits respecte la séparation des tâches.

## Règles de sécurité

- La création d'un établissement **public** passe par le super-administrateur avec MFA et ne peut pas être rattachée à une organisation disposant de comptes fondateurs privés.
- Le rôle « propriétaire » n'est pas proposé ni créé pour les nouveaux établissements publics.
- Aucun modèle de rôle public livré par défaut n'accorde les cinq droits financiers sensibles (tarification, encaissement, reversement/annulation, approbation, dépôt).
- Un changement direct \`public ↔ privé\` est bloqué : il exige une migration administrative distincte, avec examen des membres, propriétaires et flux financiers.
- Un changement \`privé laïc ↔ privé confessionnel\` est audité avec motif ; si des comptes utilisent un rôle propre au confessionnel, ils doivent d'abord être réaffectés.
- Les nouveaux rôles de consultation de la tutelle et du confessionnel ne donnent **pas** d'office accès aux données nominatives des élèves.
- Les contrôles par cycle, les délégations et la double validation financière existants restent indépendants du régime.

## Ce que cette première livraison n'automatise pas

- La validation juridique d'une nomination ministérielle, d'un enseignant privé ou d'une autorisation d'ouvrir un cycle.
- Les décisions/votes exécutoires des conseils, les actes budgétaires publics, l'import du personnel de l'État et la paie.
- Le calcul automatique du quota légal des enseignants permanents, qui nécessite des statuts d'emploi fiables, une période d'observation et une validation de son champ juridique.
- La validation des tarifs privés par le ministère, pour laquelle il faudra enregistrer l'autorisation, l'année et les montants associés. Les tarifs d'école existants ne sont pas rendus légalement « approuvés » par simple saisie.
- La conversion d'un établissement réel public/privé existant sur une simple option de formulaire.

## Sources consultées

- Collèges : décret n°00509/PR/MENIC (03/06/2008) — https://www.journal-officiel.ga/7016-00509-pr-menic-/
- Lycées : décret n°00507/PR/MENIC (03/06/2008) — https://www.journal-officiel.ga/7013-00507-pr-menic-/
- LEG publics : décret n°0859/PR/MENESTFPRSCJS (28/10/2013) — https://www.journal-officiel.ga/2050-0859-pr-menestfprscjs/
- Lycées techniques : décret n°0858/PR/MENESTFPRSCJS (28/10/2013) — https://journal-officiel.ga/2048-0858-pr-menestfprscjs/
- Enseignement privé : loi n°21/84 (29/12/1984) — https://www.journal-officiel.ga/10389-21-84-/
- Code du travail, rectificatif JO 163 Bis 18/05/2022 : https://journal-officiel.ga/18784-022-2021/

## Vérifications avant mise en production

Tester la nouvelle création de trois collèges et trois lycées via la console MFA, vérifier les rôles proposés et l'absence de propriétaires publics ; tester un établissement mixte, les nominations multiples et le filtrage des cycles ; garantir l'absence de modification des permissions des comptes existants, tester les anciens tarifs/économat ; vérifier les migrations et la reprise des anciennes écoles. La formation utilisateur doit distinguer rôles applicatifs, fonctions, organes et statut juridique.

# YEM — Parcours unique d'ajout d'un collaborateur

## Pourquoi

La création de personnel était répartie entre quatre onglets : comptes, fiches, organigramme, rôles. Le parcours principal « Personnel → Ajouter un collaborateur » regroupe maintenant ces opérations sans supprimer les outils d'administration avancée.

## Parcours

1. **Identité** : matricule unique dans l'école, prénom, nom, poste.
2. **Fonctions** : zéro à vingt nominations par établissement/cycle, avec dates facultatives ; zéro à trente affectations année/classe/responsabilité.
3. **Accès YEM facultatif** : identifiant unique à l'école, email, mot de passe conforme à Django, rôle principal et rôles supplémentaires. Une fiche peut rester sans compte.
4. **Vérification** : récapitulatif et confirmation explicite du fait que les rôles applicatifs ne sont pas encore limités par cycle pour les complexes multicylces.

Le serveur expose :
- \`GET /api/v1/schools/{id}/staff/onboard\` : options autorisées pour l'école active.
- \`POST /api/v1/schools/{id}/staff/onboard\` : transaction unique de création.

Tous les objets (compte, appartenance à l'école, fiche, nominations, affectations) sont créés dans une seule transaction et un seul audit \`staff_onboarded\`. Les contraintes de matricule, comptes, quotas, années/classes, rôles, permissions, cycle et nominations s'appliquent côté serveur. Un échec revient en erreur sans enregistrement partiel.

## Qui peut faire quoi

- **Propriétaire de l'organisation** : enregistrer du personnel, créer ses comptes et gérer ses nominations dans son organisation ; cela ne lui attribue pas automatiquement les droits pédagogiques ou financiers de la direction sur son propre compte.
- **Gestionnaire du personnel** (\`school.staff.manage\`) : enregistrer des fiches. Il ne crée un accès YEM que s'il possède aussi \`school.members.write\`.
- **Nominations** : \`school.organization.manage\` requis pour un gestionnaire non propriétaire.
- **Rôles supplémentaires** : chacun doit provenir de l'établissement ; un gestionnaire non propriétaire ne peut transmettre des permissions qu'il ne possède pas et ne peut déléguer d'autorisations financières sensibles.
- **Compte non créé** : fiche et nominations professionnelles possibles sans nouvel identifiant.
- **Séparation financière** : pas de nouvelle permission sensible auto-attribuée ; les autres API financières conservent leur contrôle indépendant.

## Limites volontaires

- Les **fonctions d'organigramme** ne donnent aucun droit API. Les **rôles** confèrent actuellement les permissions à l'ensemble de l'établissement, pas au seul cycle nommé. L'interface le dit explicitement et demande confirmation pour créer un compte dans un groupe scolaire multi-cycles. Cette confirmation **n'est pas une restriction technique** : ne pas donner de rôle à portée globale à une personne censée être limitée à un cycle tant que les contrôles métier par cycle ne sont pas opérationnels.
- Un **départ ou remplacement** se traite encore dans les anciens modules (révocation des droits et comptes séparément de la suspension de nomination).
- Le parcours actuel crée un **nouveau** collaborateur ; les mises à jour de personnel existant restent dans les onglets avancés pour conserver leur historique et contrôles de concurrence.
- Le propriétaire ne remplace pas automatiquement le super-administrateur de la plateforme.

## Tests

\`python manage.py test institutions.test_staff_onboarding\` à exécuter avec la configuration Django de tests. Puis test manuel dans un complexe maternelle/primaire de démonstration : création sans compte, avec compte, double nomination, affichage dans l'organigramme, accès d'un compte nouvellement créé, refus d'un rôle financier non autorisé, rollback après matricule dupliqué et isolation entre deux établissements.

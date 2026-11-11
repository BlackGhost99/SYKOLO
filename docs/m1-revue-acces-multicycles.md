# YEM — M1 : revue des accès par cycle (établissements multicycles)

Date : 11 novembre 2026. Contrôle agrégé en lecture seule sur Supabase YEM.

## Constat réel, sans extraction de noms

- 3 établissements actifs, chacun avec 2 cycles configurés.
- 16 rattachements utilisateur/école actifs, tous avec `access_cycle_ids = NULL` (périmètre global hérité).
- 0 rôle principal d'une autre école, 0 rôle additionnel étranger, 0 périmètre de cycle malformé.
- Les comptes concernés couvrent la direction, le personnel administratif, pédagogique et certains profils parents ; **NULL n'est pas en soi une violation**, mais exige une décision explicite selon les responsabilités.

## Principe de mise en conformité

Ne jamais attribuer automatiquement un périmètre à partir du nom d'un poste. Le responsable de l'établissement, avec le propriétaire et une personne qui connaît réellement les fonctions, détermine pour chaque compte :
- accès école entière : direction générale et fonctions transversales légitimes ;
- accès à un ou plusieurs cycles réellement actifs ;
- révision ou désactivation d'un compte devenu inutile.

Les changements passent par **Paramètres → Droits généraux → Accès par cycle**, sont justifiés et audités. La liste signale désormais le nombre de comptes à accès global et les distingue visuellement. Ne pas appliquer de restriction sans recette : pour les comptes limités, certains modules métier renvoient encore 403 par sécurité (middleware fail-closed) ; cela empêche des fuites mais peut gêner un parcours si les routes ne sont pas encore adaptées.

## Critères de clôture de la revue

- [ ] Chaque compte global dont le propriétaire n'est pas implicitement responsable a été examiné, avec justificatif de maintien ou restriction.
- [ ] Les comptes à accès limité ont été testés sur leurs vrais parcours métiers (consultation et écritures selon rôle).
- [ ] Les anciens comptes inactifs/superflus sont désactivés conformément à la procédure.
- [ ] Aucun droit supplémentaire n'est octroyé par simple nomination dans l'organigramme.
- [ ] Le nombre de comptes globaux est revérifié après la recette, sans interpréter automatiquement tout compte global comme une anomalie.

Cette PR **ne change aucun droit** et n'applique aucune restriction automatique.

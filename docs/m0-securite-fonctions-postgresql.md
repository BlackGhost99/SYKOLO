# YEM — M0 : sécurité des fonctions PostgreSQL de clôture

Date : 11 novembre 2026.

## Constat vérifié

L'analyseur de sécurité Supabase du projet YEM signalait 39 fonctions `public.yem_closed_*` / `public.yem_immutable_year_closure` sans `search_path` fixé. Ces fonctions sont des triggers `SECURITY INVOKER` (pas `SECURITY DEFINER`). Leurs requêtes actuelles utilisent des noms de tables Django non qualifiés dans le schéma `public`.

## Correction sur branche, non déployée

La migration `0044_pin_year_guard_search_path.py` applique un `search_path` immuable `pg_catalog, public, pg_temp` aux fonctions `trigger` sans argument, dans le seul schéma `public` et uniquement pour les noms appartenant aux gardes YEM. Elle conserve les permissions et les corps des fonctions, évitant d'affaiblir le verrouillage des années clôturées. Elle refuse explicitement l'absence des fonctions attendues.

Supabase conseille un chemin vide (`search_path = ''`) avec références **entièrement qualifiées**. Une telle modification n'est **pas** substituable ici sans réécrire toutes les fonctions : elle empêcherait les gardes actuelles de résoudre les tables. Notre correctif fixe le chemin à des schémas attendus dans le périmètre de Django. Des tests doivent confirmer le comportement, et une réécriture future pourra qualifier tous les noms pour atteindre la recommandation stricte.

## Vérifications requises

1. Migrations `migrate` en CI PostgreSQL 17 et `makemigrations --check`.
2. `python backend/manage.py test institutions.test_m0_trigger_security` et régressions `institutions.test_annual` / tests de clôture existants.
3. Contrôle Supabase `function_search_path_mutable` **après** déploiement surveillé, jamais présenté comme corrigé avant.
4. Test de modification d'un dossier dans une année clôturée : doit rester bloqué après migration.
5. **Sauvegarde réelle chiffrée et restauration isolée** validées avant toute migration production.

## Compatibilité des branches

Cette migration prend le numéro `0044` après `0043_school_governance_mode` (PR #98 fusionnée).
La PR #99 propose aussi une migration `0044` ; sa branche devra être rebasée et sa migration renommée / chaînée à la suite de celle-ci. La PR #102 propose une autre migration `0043` ; elle devra être chaînée avec le nouveau graphe, puis validée avec les tests. **Ne pas fusionner ces migrations concurrentes sans réconciliation explicite.**

## Rappel

Ce correctif réduit un problème signalé par les diagnostics de PostgreSQL ; il ne remplace ni l'audit des 16 comptes à accès global ni la preuve de sauvegarde réelle. La CI reste synthétique. Aucune modification en direct n'est autorisée dans ce lot.

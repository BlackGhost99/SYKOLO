# YEM — Recette financière F7

Cette liste distingue tests automatisés, validation de production et recette réelle. Aucune ligne « à vérifier » n'est une certification.

| Lot | Contrôles de recette | Preuve attendue |
| --- | --- | --- |
| F1 | Rôles, isolation école, bourses, paiement partiel et multi-frais atomique, annulations, caisse, devises, échéances, concurrence | Suite Django/PostgreSQL et tests synthétiques; recette réelle par rôle |
| F2 | PDF commercial privé, contrat figé, reçu annulé, isolation et MFA | Tests API + UI; mentions légales à configurer |
| F3 | J-7/J/J+1/J+7/J+30, paiement/annulation, isolation et historique | Tests API + UI; alertes web seulement |
| F4 | Prorata, minimum, révision, replay, essai, conversion, stabilité facture originale | Tests API + UI; nouveaux cycles/avoirs hors périmètre |
| F5 | J+29 vs J+30, restriction manuelle, refus d'écriture, lectures autorisées, redirection, deux écoles, réactivation | Tests API + UI + adversariaux GET et CTE |
| F6 | Total contractuel, paiements non annulés, solde, échéances, anomalies historiques, calendrier civil, MFA | Tests API + UI; pas de résultat comptable |
| F7 | CI exacte sur HEAD, migrations sans dérive, RLS, déploiement backend et frontend même commit | CI et Render; contrôle SQL de production en lecture seule |

## Parcours réel à faire avant commercialisation

Sur une école de recette explicitement désignée et des personnes fictives, tester les parcours direction, propriétaire, économe, comptabilité, enseignant et parent dans les interfaces réelles. Créer des contrats et paiements uniquement dans un environnement de test isolé, valider PDF téléchargeables, notification du retard, bascule lecture seule, navigation et restauration. Les actions financières commerciales doivent rester distinctes de la caisse scolaire.

Valider SingPay avec le fournisseur et une procédure de rapprochement avant d'activer le paiement réel. Les paiements BWETEK en ligne restent à intégrer; les documents commerciaux attendent la configuration des mentions fiscales. Les sauvegardes réelles Supabase sont à valider avec l'offre retenue; un exercice synthétique n'est pas une preuve de restauration des données réelles. Les routes familles autonomes et callbacks déjà engagés sont distincts des API écoles. Le blocage sur écritures indirectes et la compatibilité des lectures historiquement mutantes doivent être éprouvés par rôle en recette. Les requêtes admises avant décision peuvent se terminer.

## F7 tests supplémentaires

Routes fictives disponibles uniquement dans le module de tests: lecture normale, GET mutante et CTE mutante, aucune donnée réelle. Le garde refuse WITH/EXPLAIN non audités dans la frontière lecture seule. Vérifie également l'indépendance de deux écoles et la réactivation. En production la transaction PostgreSQL read-only constitue une deuxième barrière. Aucune migration supplémentaire.

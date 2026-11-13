# YEM — M2.9 : recette multi-établissements (13 novembre 2026)

## Périmètre et principe

**Recette automatisée dans une base Django/PostgreSQL temporaire ; ne crée aucune
donnée dans Supabase, Render ni dans le lycée AWASSI réel.** Les identités,
les établissements et les frais affichés sont **fictifs**. Les charges de
scolarité dans les fixtures ne constituent **pas** des paiements encaissés.

Trois établissements sont montés indépendamment dans
`backend/institutions/test_m2_9_three_school_persona.py` :

| Établissement fictif | Année | Divisions | Élèves |
| --- | --- | --- | ---: |
| Lycée AWASSI (TEST M2.9) | 2026–2027 | Seconde S1 / S2 | 4 |
| Lycée Privé 2 (TEST M2.9) | 2026–2027 | Terminale C1 / C2 | 4 |
| Complexe scolaire Les 8 (TEST M2.9) | 2026–2027 | Quatrième année A / B | 4 |
| **Total** | | **6 classes, 3 écoles** | **12** |

Les trois établissements possèdent des rôles distincts de direction,
secrétariat et enseignant, des classes, des responsables légaux et des frais
de scolarité fictifs. Une famille utilise **un même compte parent dans deux
écoles**, tandis qu'une autre a un compte séparé dans le complexe.

## Vérifications exercées par de vraies routes HTTP

- **Année / classes / matricules :** 12 identités YEM uniques, 12 inscriptions
  annuelles, 12 responsables légaux, deux divisions par école, effectifs et
  places disponibles par établissement.
- **Isolation :** une direction ne consulte pas l'autre école, un enseignant
  n'accède qu'à sa classe affectée ; une liste pédagogique ne divulgue pas les
  données administratives, contacts ou finances.
- **Fiche élève :** direction habilitée, responsables légaux et solde
  scolaire visibles ; enseignant et parent sans droits de dossier refusés.
- **Familles :** attestation explicite par la direction, refus sans preuve,
  deux enfants visibles pour le parent multi-écoles (un dans chaque lycée),
  refus de consultation des autres enfants et révocation immédiate.
- **M2.7 :** répartition automatique entre deux divisions compatibles sans
  changer les matricules, l'inscription, la dette initiale ou les traces.
- **Bulletins :** publication fictive et contrôle du droit de consultation
  des bulletins par compte parent vérifié.

## Vérifications bout en bout complémentaires déjà présentes dans la CI

- `institutions.test_lycee2_parent_journey` : parent, dossier, décision,
  paiement de **bac à sable**, inscription, matricule et lecture parent.
- `institutions.test_demo_payment_journeys` : espèces, validation de
  l'encaissement au guichet, droits caisse/direction, cours, notes,
  publications et bulletin. Les fonds sont **fictifs dans la base de test**.
- `institutions.test_persona_preschool_primary` : deux cycles et
  rôles distincts sur un complexe, admission et suivi scolaire.
- `institutions.test_full_journey` : professeur, notes, bulletin,
  clôture / rectification et isolation inter-écoles.
- `institutions.test_m2_class_assignments` et
  `institutions.test_parent_portal` : concurrence, places,
  révocation parent, autres enfants et données privées.

## Commandes

`python backend/manage.py test institutions.test_m2_9_three_school_persona`

La CI GitHub exécute cette recette avec toute la suite :
`python backend/manage.py test pedagogy accounts institutions`.
Aucune migration de schéma ni création de ressource Render n'est nécessaire.

## Limites et blocages à ne pas masquer

Cette recette démontre des règles métier via API **sur des données
temporaires**. Elle ne prouve pas à elle seule la qualité de l'interface sur
un Android réel, la délivrance des mails, la connexion opérateur Airtel/Moov,
les performances d'import, l'encaissement physique réel ni le déploiement
Render / la migration Supabase en production. L'ouverture de **toutes les
classes du lycée AWASSI** et ses 300 élèves existants relèvent de la
vérification de sa base propre, et ne doivent pas être écrasés par ces
fixtures.

Pour la clôture de M2.9 en conditions réelles : vérifier le dernier déploiement
Render sur le bon workspace avec `/readyz`, confirmer la migration sur la
base attendue, puis tester visuellement les postes direction, secrétariat,
économat, enseignant et parent, avec données fictives et documents non réels.
Collecter captures non nominatives, succès / échecs et anomalies GitHub.

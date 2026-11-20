# YEM Intelligence — feuille de route

Suivi : [épique #225](https://github.com/BlackGhost99/SYKOLO/issues/225), [reprise financière #226](https://github.com/BlackGhost99/SYKOLO/issues/226).

## Objectif

Réduire la ressaisie lors de la migration d'un établissement et améliorer l'assistance métier. L'IA propose, le moteur métier vérifie, l'utilisateur habilité valide.

## Jalons et critères de sortie

| Jalon | Livrable | Critère de sortie |
|---|---|---|
| P0 — Socle local | Analyse indicative, résultat structuré, aucun appel externe | Tests de reconnaissance et absence d'écriture |
| P0 — Migration administrative | Correspondances, rapprochement matricule, ambiguïtés et prévisualisation | Tests Excel/CSV, isolation multi-écoles, idempotence |
| P0 — Reprise financière | Tarifs, échéances, historiques, bourses, soldes | Écritures auditées, validation distincte, absence de débit et de recette fictive |
| P1 — Orchestration IA | Interface fournisseur indépendante, sorties validées, quotas et coûts | Fournisseurs désactivés par défaut, tests avec réponses simulées, secrets serveur, consentement et données minimisées |
| P1 — Documents | Extraction OCR locale, provenance, validation | Recette sur documents anonymisés, fichiers sécurisés |
| P1 — Configuration école | Aide cycles, classes, rôles, tarifs, calendriers | Suggestions vérifiables et confirmables |
| P1 — Emplois du temps | Solveur de contraintes et suggestions | Aucun conflit, validation humaine |
| P2 — Pédagogie | Analyses et propositions | Aucune note inventée, contrôle professeur |
| P2 — Pilotage | Indicateurs, assistance décisionnelle | Traçabilité, incertitude et isolation |
| P2 — Assistant par rôle | Questions et réponses contextualisées | Contrôle des droits et actions sensibles non autonomes |

## Première livraison

L'assistant existant CSV/XLSX expose une analyse de colonnes sous la clé `intelligence` de la réponse inspect. Le moteur local déterministe repère des colonnes financières possibles (mois, paiements, soldes, bourses, etc.) et des colonnes sans correspondance automatique. Il conserve les suggestions administratives existantes. Les indices retournés désignent les colonnes, pas des transactions. Le frontend avertit que les frais et paiements ne sont pas importés. L'analyse ne lit pas les valeurs des lignes ; elle ne transmet aucune donnée ailleurs.

Cette brique n'est pas encore une IA générative ni un import financier : la détection par en-têtes est indicative et peut manquer des intitulés inhabituels. Aucun modèle externe, secret, quota payant, modification de base ou appel SingPay n'est ajouté. Les permissions, la prévisualisation signée et le commit de l'import administratif restent inchangés.

## Reprise financière

Voir #226. Distinguer zéro et valeur inconnue, ne pas déduire un paiement d'un intitulé, vérifier les frais applicables et les justificatifs. Ne jamais comptabiliser une recette ancienne dans la caisse du jour. Préserver l'historique, le rapprochement, les bourses, les droits et l'idempotence. Validation humaine avant import et tests sur fichiers fictifs, puis anonymisés.

## Gouvernance

Aucune donnée personnelle d'enfant envoyée à un service externe par défaut. Les fournisseurs et budgets devront être activés explicitement par la plateforme. Contrôles déterministes, isolation des établissements, audit et résistance aux instructions malveillantes dans les documents. Chaque jalon exige des tests et une PR validée avant déploiement.

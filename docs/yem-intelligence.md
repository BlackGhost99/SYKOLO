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

## Matricules locaux — #229

YEM Intelligence inspecte les matricules du registre d'une école (jusqu'à 10 000 codes pour la suggestion) et de la colonne Matricule reconnue dans un fichier d'import. Il détecte les compteurs numériques, zéros initiaux, préfixes ou suffixes fixes et présente jusqu'à huit séries candidates, sans modifier ni réserver de codes. Les identifiants permanents YEM ne sont pas interprétés comme séries locales. Les cas mixtes, les chiffres fixes ambigus et les petits échantillons exigent le choix du gestionnaire. Le moteur local n'appelle aucun fournisseur IA.

Pour un registre importé avec des lignes sans code, choisir et enregistrer la règle dans les paramètres Matricules avant le commit. Le générateur existant réserve les codes renseignés avant de numéroter les lignes vides. Pour une école déjà en activité, les paramètres proposent les séries de ses élèves et utilisent le compteur déjà réservé lorsqu'il est supérieur. La prévisualisation classique et l'enregistrement contrôlent l'ensemble du registre sous les verrous existants. Les propositions calculées sur le fichier seul ne sont pas des garanties de disponibilité ; elles ne modifient jamais la règle automatiquement. Les anciennes séries restent inchangées, aucune déduction automatique d'une année en cours ni réinitialisation annuelle.


## Passage des inscriptions à la reprise financière

Après confirmation de l'import des élèves et inscriptions, YEM propose à l'utilisateur habilité de reprendre le classeur quand une année est sélectionnée et que le fichier contient des colonnes financières possibles ou plusieurs feuilles. La transition reprend le fichier en mémoire, l'onglet, la ligne des en-têtes et l'année. La reprise financière relit le fichier sur demande et conserve ses propres permissions, correspondances, aperçu et double validation.

Le moteur local distingue les en-têtes évoquant un versement, un solde, une bourse ou un tarif. Les en-têtes ambigus, dont les noms de mois seuls, restent à qualifier. Les suggestions se limitent aux en-têtes et ne déclenchent aucun rapprochement automatique. La connexion d'un fournisseur externe et l'orchestration IA restent au jalon P1.

Le contrat du moteur d’analyse limite les résultats à une catégorie autorisée par colonne candidate. Le serveur reprend l’analyse déterministe locale si un conseiller simulé échoue ou retourne des catégories ou des indices inattendus. Le conseiller local est le seul raccordé au produit.


## Orchestrateur YEM Intelligence

Les écrans de migration et de paramétrage des matricules utilisent le même orchestrateur. La tâche financière peut être testée avec un adaptateur simulé. Celui-ci reçoit les indices candidats et un vocabulaire financier autorisé extrait des en-têtes. Les en-têtes complets, les valeurs du classeur et les matricules restent dans les tâches locales. Les catégories et les indices renvoyés sont validés avant affichage. Une réponse invalide ou une indisponibilité déclenche l'analyse déterministe et un journal technique sans données du classeur.

Le produit instancie l'orchestrateur avec ses traitements locaux. La vue d'ensemble BWETEK, réservée aux super-administrateurs authentifiés par MFA, affiche les tâches disponibles et l'état de raccordement. La gestion des fournisseurs, clés, quotas et budgets reste à intégrer.

### Adaptateurs fournisseurs

Les adaptateurs OpenAI, Gemini et Mistral sont disponibles pour les tests simulés. Le moteur utilisé par YEM continue de fonctionner localement. Chaque adaptateur accepte au plus 24 colonnes d’indices et de mots autorisés. Il demande une réponse JSON de taille bornée et refuse les indices ou catégories inattendus. Une erreur déclenche le repli local. Aucun accès réseau de fournisseur ne fait partie des tests.

Références des formats utilisés : [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [Gemini GenerateContent](https://ai.google.dev/api/generate-content) et [Mistral Chat Completions](https://docs.mistral.ai/api/endpoint/chat).

### Préparation du test Gemini dans BWETEK

La carte YEM Intelligence détecte la présence de YEM_GEMINI_API_KEY (ou GEMINI_API_KEY) et de YEM_GEMINI_MODEL dans le processus Django. Elle affiche un statut de préparation. Les valeurs restent côté serveur. Le bouton de simulation utilise des indices fictifs et une réponse injectée. La simulation vérifie le format et le repli local des colonnes ambiguës. La validité de la clé auprès de Google nécessite un essai réel, absent de ce parcours.

Le test réel hors production se lance avec `python backend/manage.py yem_test_gemini` depuis un environnement explicitement prévu à cet effet. Il émet une seule requête Gemini, avec deux colonnes fictives, et peut consommer du quota ou être facturé selon le projet Google. Le test échoue si le classement attendu est incorrect. Le moteur de l’application reste local pendant et après le test.

### Pilote Gemini en production

Le pilote s’active avec YEM_GEMINI_FREE_PILOT=true uniquement pour une clé liée à un projet Google sans facturation. La clé et le modèle doivent également être présents. Le bouton « Analyser les en-têtes avec Gemini » est proposé dans la reprise financière. L’inspection habituelle reste locale. Le compteur PostgreSQL réserve au plus 10 tentatives par jour UTC pour toute la plateforme, erreurs comprises. À la limite ou en cas d’indisponibilité, YEM affiche les suggestions locales. Gemini reçoit des indices de colonnes et des mots autorisés. Aucun paiement, solde ni association de tarif ne peut être modifié par ces suggestions.

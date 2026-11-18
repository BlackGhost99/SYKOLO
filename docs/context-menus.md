# Menus contextuels YEM

## Contrat

Le clic droit est réservé aux surfaces opt-in. Le clic gauche reste fonctionnel. Les trois points ouvrent le même menu sur écran tactile. La touche Menu ou Maj+F10 ouvre le menu, les flèches et Début/Fin déplacent le focus, Échap le ferme. Le menu se ferme aussi au clic extérieur, défilement extérieur, redimensionnement ou changement de droits. Les champs, liens et sélections de texte conservent le menu du navigateur.

`ContextTarget` reçoit des actions explicites de la forme `{id,label,run,write,disabled,hidden}`. `Table` accepte `rowActions(row,index)` et `rowKey(row,index)`. Les identifiants doivent suivre les objets métier, pas leur position dans la liste. `ContextReadOnly` est alimenté par le tableau de bord de l'établissement, y compris le mode enseignant, et masque les raccourcis d'écriture. Les API et leurs contrôles d'autorisation restent inchangés.

## Couverture

- Élèves : aperçu, fiche, modification du dossier et préparation du changement de classe et de l'encaissement.
- Inscriptions par classe, gestion des classes : liste, dossier, préparation de création, modification et duplication.
- Admissions : dossier sélectionné, historique et ouverture de la caisse existante lorsqu'applicable.
- Échéances, suivi financier, tarifs, reçus et impayés : consultation, préparation du règlement ou du motif d'annulation, sans validation automatique.
- Personnel et familles : fiche, rémunérations et dossier enfant ; paie et dépenses : détail, préparation des formulaires.
- Emploi du temps : modification/déplacement et préparation d'une copie avec choix volontaire du nouveau créneau et de l'enseignant.
- Notes et appel : accès à la saisie, statut préparé localement, historique des marques ; interfaces enseignant ordinateur et mobile.
- Cahier de textes : modification et duplication en nouveau brouillon avec date à vérifier ; pièces jointes non recopiées ; aucune publication automatique.
- Bulletins et documents commerciaux : ouverture du PDF authentifié ; documents commerciaux : téléchargement sur l'URL privée déjà validée.
- Calendrier, matières et programmes : modification encadrée, consultation du programme.
- Rattachements et messages : préparation d'un examen ou d'une réponse.
- Super-administration : gestion d'un établissement, accès au contrat depuis les finances commerciales et les relances.

Aucune nouvelle route, migration, dépendance ou modification de données. Les actions sensibles (validation financière, publication, décision d'admission, suppression, changement de droits, suspension) restent dans leurs flux explicites. Les formulaires, listes de sélection natives, consultation familiale sans action utile, tableaux statistiques et vues de démonstration ne sont pas interceptés globalement. Les options métier absentes ne sont pas simulées.

## Recette

Tests Vitest/jsdom : cible de ligne, déclenchement souris/clavier/tactile, retour du focus avec Échap, champs et liens natifs, restriction commerciale, état désactivé, fermeture extérieure, tri/filtre, changement de droits pendant l'ouverture, pas de soumission accidentelle.

Avant fusion : CI et build sur le SHA exact, non-régression React/Django et vérification manuelle des parcours desktop et mobile par rôle dans un établissement de test. Vérifier le déploiement Render et ne jamais réaliser une écriture financière ou scolaire réelle pour le test.

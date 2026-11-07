# YEM — démonstration interactive et application réelle

## Lien direct à présenter aux établissements

`https://yem-api.onrender.com/#/demo`

Cette URL ouvre une maquette interactive indépendante de toute authentification.
Pour revenir à l'application de production : bouton **Retour à YEM réel**.

## Contrat de séparation

- Une session authentifiée ou non n'est **pas chargée** lorsque la route
  `/#/demo` est active : le composant principal contourne volontairement
  `AuthPanel` et ses appels API.
- Les jeux de données fictifs sont codés dans `frontend/demo-data.js`.
  Ils ne représentent **aucune donnée réelle** d'un établissement gabonais.
- Toutes les actions sont des `useState` React, sans requête `fetch`,
  sans stockage permanent, sans intégration SingPay, sans SMS ou e-mail.
- Les mots « simulation » / « fictif » figurent sur la bannière et les
  reçus. Un reçu de démonstration n'a aucune valeur comptable.
- L'application réelle continue d'utiliser ses propres permissions,
  sa base de données, ses encaissements et ses procédures d'admission.
  La démonstration ne crée ni compte, ni facture ni élève réel.
- Le bouton **Réinitialiser** restitue les données d'exemple initiales.

Les maquettes PC d'origine restent disponibles à titre de références graphiques
sous « Maquettes PC (référence statique) ». Leur appel direct à l'API
`parents/children` a été supprimé pour qu'une page de référence ne
déclenche plus la lecture de données parentales.

## Scénario de présentation recommandé (10 à 15 minutes)

1. **Super-administrateur** — montrer les établissements fictifs ; cliquer
   « Explorer l'établissement ». Expliquer l'isolation des organisations
   et des établissements sans simuler des comptes de production.
2. **Direction** — sélectionner « Lycée Démonstration de Libreville »,
   consulter élèves / classes ; ajouter un élève puis modifier sa fiche.
   Les changements apparaissent directement dans la liste.
3. **Admissions** — ouvrir le dossier d'affectation d'Obame David :
   montrer d'abord le refus d'accepter sans justificatifs, puis simuler
   leur vérification, la décision « Accepter » et enfin « Inscrire ».
   Les étapes restent distinctes.
4. **Finances** — choisir une facture, simuler un paiement partiel ou total
   et ouvrir le reçu portant la mention « aucun argent transféré ».
   Aucune API SingPay n'est appelée.
5. **Maternelle / primaire** — changer l'établissement pour montrer des
   niveaux et fonctions différents ; en maternelle, les bulletins
   affichent un suivi par compétences.
6. **Parent d'élève** — parcourir plusieurs enfants dans des établissements
   différents, leurs frais, bulletins et absences ; créer une demande
   de préinscription fictive.

## Vérification technique

- Tests React sur `/#/demo` : aucun appel `fetch` ne doit être effectué.
- Tests de navigation entre les trois profils et parcours interactifs.
- Tests de créations locales, réinitialisation, concours/affectation,
  simulation financière et pédagogie maternelle.
- Le changement de l'application réelle ne doit pas importer les
  données de démonstration dans la base.
- Les classes, modèles Django, migrations et API réelles sont inchangés.

## Limites

La maquette expose des exemples illustratifs. Un bouton ouvrant une
simulation de paiement **ne garantit pas** l'activation des règlements
SingPay en production. Aucune donnée affichée ne doit être présentée comme
la statistique réelle d'une école. La démonstration n'est pas un environnement
de recette connecté à une copie de la base de données.

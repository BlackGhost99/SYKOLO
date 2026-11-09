# YEM — démonstration interactive pour rendez-vous établissements

## Deux accès à conserver

Sur l'accueil YEM : **Espace de gestion réel** et **Démonstration interactive · Présentation**.
L'ancien bouton « Maquettes PC (référence statique) » a été retiré de l'accueil ; il ne faut pas supprimer les composants et archives graphiques conservés dans le dépôt.

**Lien direct à ouvrir lors du rendez-vous :** https://yem-api.onrender.com/#/demo

La démonstration adopte les catégories de l'espace réel : tableau de bord, élèves, admissions, classes, finances, impayés, bulletins, absences, personnel, organigramme/rôles, matières, emplois du temps, années scolaires et paramètres. Les trois profils visiteurs restent accessibles : super-administrateur, direction et parents.

## Séparation stricte avec YEM réel

La route `/#/demo` ne monte ni l'authentification ni la connexion API réelle.
Toutes les données sont fictives et les interactions restent dans la mémoire de la page : aucun compte, SMS, WhatsApp, e-mail, paiement ou écriture PostgreSQL n'est effectué.
Les modifications affichées sont perdues au rechargement ; le bouton **Réinitialiser** rétablit les exemples.

Les simulations de recettes et de paiements sont explicitement étiquetées fictives. L'écran de paiement ne réalise aucun appel SingPay.

## Circuit de démonstration conseillé (10–15 minutes)

1. **Console plateforme** : ouvrir les établissements fictifs, créer un établissement, mentionner propriétaire/fondateur et isolation des écoles.
2. **Direction** : choisir le lycée, montrer le tableau de bord et le choix d'année scolaire 2025–2026 (archive), 2026–2027 et 2027–2028 (nouvelle année). Revenir en 2026–2027.
3. **Classes et matières** : générer plusieurs divisions et plusieurs matières d'un coup ; modifier ou supprimer une division.
4. **Personnel et organigramme** : ajouter un membre avec une ou deux fonctions, une affectation par cycle et un compte facultatif ; explorer les rôles du secondaire.
5. **Emploi du temps** : créer un cours, montrer qu'une salle/enseignant/classe déjà occupé déclenche un avertissement de conflit.
6. **Admissions** : vérifier les pièces, accepter, puis inscrire l'élève ; l'acceptation n'est pas l'inscription.
7. **Finances et impayés** : simuler un paiement partiel, afficher son reçu fictif puis préparer une relance sans la transmettre.
8. **Évaluations** : passer des notes sur 20 aux compétences ou aux lettres depuis les paramètres.
9. **Parents** : parcourir les enfants, leurs bulletins, frais et demandes de préinscription.

## Limites à expliquer sans ambiguïté

Il s'agit d'une **démonstration interactive autonome**, et non d'un clone vivant de la production. Les modules réels ont des permissions, des validations et des traitements serveur plus complets. Les contrôles représentés dans la démo sont des aperçus commerciaux, pas une preuve d'activation ou de conformité de chaque module réel.

Les données fictives de `frontend/demo-data.js` ne sont jamais injectées dans les API de production.

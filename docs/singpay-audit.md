# SingPay / YEM — audit et livraison préparatoire du 4 novembre 2026

## Décision de livraison

Branche `codex/singpay-school-direct`, base `7efe032b3dfd3b281a04af62a68061bf07a9c995`.
**PR en brouillon, aucune activation, fusion ou migration en production.**
La fondation technique est testable sans argent. Le contrat officiel publié ne décrit
pas l'authentification des callbacks ; la route webhook retourne donc 503 sans
lecture du corps, appel fournisseur ni mutation financière. L'API de configuration
refuse `enabled=true`. Ne pas contourner ce verrou par une modification de base.

## Preuves consultées

- [Swagger SingPay v1 officiel](https://client.singpay.ga/doc/reference/src/swagger.json),
  version 1.0.0, empreinte SHA-256
  `a06d0f0a4fd7f2133c338f375287907bdfa8d96d305c942e1d94757fddfc32b3`.
  La page officielle charge cette ressource depuis son HTML.
- [Étapes officielles d'intégration et GoLive](https://github.com/singpay-ga/singpay-doc/blob/main/Etape-d%27int%C3%A9gration.md).
- Gaboshop, commit observé `d47b881af54ffb1c3e5827763c7fe06eda1f2ff7` :
  [transport réel](https://github.com/BlackGhost99/Gaboshop/blob/d47b881af54ffb1c3e5827763c7fe06eda1f2ff7/payments/utils.py),
  [services et reversements](https://github.com/BlackGhost99/Gaboshop/blob/d47b881af54ffb1c3e5827763c7fe06eda1f2ff7/payments/services.py),
  [vérification serveur](https://github.com/BlackGhost99/Gaboshop/blob/d47b881af54ffb1c3e5827763c7fe06eda1f2ff7/payments/online_verification.py),
  [anciennes routes désactivées](https://github.com/BlackGhost99/Gaboshop/blob/d47b881af54ffb1c3e5827763c7fe06eda1f2ff7/payments/webhooks.py),
  `api/v1/payments.py`, `payments/configuration.py`,
  `docs/archive/PAYMENT_ENGINE_AUDIT.md` et documentation historique d'intégration.

Le code Gaboshop utilise **SingPay**, les en-têtes `x-client-id`,
`x-client-secret`, `x-wallet`, et les routes `/74/paiement`, `/62/paiement`.
Aucune équivalence avec un service nommé SimPay n'est supposée. La recherche
du terme SimPay n'a pas fourni d'intégration distincte dans le dépôt interrogé.
Les anciens documents ne prouvent pas l'état de production ; le code réel a été lu.

## Constats et choix

| Sujet | Observation vérifiée | Décision YEM |
| --- | --- | --- |
| Collecte | `paiement` accepte `portefeuille`, `disbursement`, `isTransfer` | Un portefeuille exclusif et une distribution appartenant à chaque école ; `isTransfer=false` |
| Destination | `disbursement` requis en production dans le Swagger | Aucun portefeuille collecteur YEM ; propriété et destination à faire valider par SingPay et l'école |
| Reversement | API `/transfer` documentée ; Gaboshop possède une logique de reversement plateforme et une restriction opérationnelle commentée « un transfert » | Aucun appel `/transfer` dans YEM ; ne pas généraliser le commentaire Gaboshop en règle officielle |
| Confirmation | GET par référence renvoie une transaction ; `status` décrit une étape et `result` le résultat | Exiger `Terminate` + `Success` et concordance exacte du montant XAF, référence, portefeuille, téléphone, identifiant, `isTransfer=false` |
| Callback | `callbackURL` publié, aucune signature décrite dans le Swagger audité | Refus systématique, aucun HMAC inventé ; validation officielle encore nécessaire |
| Idempotence prestataire | Référence marchande unique décrite, aucune garantie de déduplication explicite | Verrou en base et clé locale ; un seul POST ; timeout/erreur = `unknown`, recherche par référence, aucun rejeu du débit |
| Frais | Pas de tarif marchand exploitable dans ce contrat d'API | Barème contractuel de chaque école ; frais absorbés par école, taux en points de base + fixe, arrondi supérieur XAF ; net estimé distinct du net constaté |
| Test | GoLive et portefeuille de test distincts dans le guide | Ne jamais créditer une dette réelle depuis un portefeuille de test ; aucun essai réseau de paiement pendant ce chantier |

Les en-têtes et la destination réseau sont fixes. Les redirections HTTP sont refusées
pour ne pas transmettre les identifiants à un autre hôte. Le JSON est limité à 64 Kio,
le délai à 15 secondes ; aucune réponse brute ou téléphone ne figure dans le journal.
Les secrets marchands sont chiffrés avec le mécanisme existant de YEM et jamais renvoyés.
La clé de chiffrement doit être conservée dans un stockage de secrets sauvegardé.

## État YEM et concurrence

- Le répertoire principal de travail était sur `feat/rebrand-yem` (`023f49a`).
  Aucun changement sur cette branche ; nouveau worktree dans `artifacts/singpay-work`.
- `audit-main` était sur `codex/audit-direction-rights` (`6775f39`), un correctif
  de délégation indépendant. Il n'a été ni modifié ni incorporé arbitrairement.
- Main distant observé : `7efe032` (#42), après `aa84e0f` (#41),
  `2e8ce48` (#38, parents/PayCentral) et `4246a29` (#40, email).
- [PR #26](https://github.com/BlackGhost99/SYKOLO/pull/26) ouverte : fiche élève,
  inscription, migration historique `0014_student_information_sheet` ; ce numéro
  est déjà occupé dans main. Ne pas fusionner telle quelle.
- [PR #33](https://github.com/BlackGhost99/SYKOLO/pull/33) ouverte : profils,
  migration `0016_school_profiles`, déjà présente dans main ; revue propre nécessaire.
- Les listes des fichiers de ces deux PR ont été lues. Les points de recouvrement
  de ce chantier sont surtout `models.py` et `urls.py` (ajouts). Les modèles
  élèves, barèmes et migrations existantes restent inchangés.
- Ajouts `0023_singpay_school_direct` et `0024_singpay_settlement_evidence`,
  après `0022_finance_role_separation`. Recontrôler main et les nouvelles migrations
  avant toute fusion ; ne jamais renuméroter une migration déjà appliquée.

## Comportements livrés dans la branche

- Portefeuille unique par école ; configuration réservée au fondateur du groupe,
  avec justificatif de contrat, bénéficiaire, révision et audit ; aucune clé globale
  SingPay partagée entre écoles. Ce contrôle administratif ne prouve pas à lui seul
  la propriété légale du compte : recette marchande requise.
- Paiements d'un frais affecté (`FeeCharge`) : inscription ou mensualité selon
  le barème existant, XAF entiers, partiels à partir de 100 XAF et solde contrôlé.
  Un parent doit avoir un lien légal vérifié et encore actif dans cette école.
- Paiements de frais de dossier (`ParentAdmissionRequest`) séparés de la scolarité.
  Paiement complet du dossier, sans création automatique d'élève ou d'inscription.
  Les tentatives PayCentral existantes bloquent SingPay et inversement.
- Clé d'idempotence liée au parent, empreinte de requête, référence unique,
  instantané du bénéficiaire et des frais ; un paiement ouvert empêche un second débit.
- Lancement hors transaction réseau ; réponse d'initiation jamais créditrice.
  Un GET authentifié par référence fait le rapprochement. Seul le succès vérifié
  de production crée une écriture `FeePayment` à méthode réservée `singpay`.
- Les encaissements manuels ne peuvent usurper la méthode `singpay` ni annuler
  un reçu fournisseur. Un conflit de solde conserve l'argent reçu en état `review`,
  sans surcréditer l'élève. Un signal de remboursement conserve le reçu et exige
  une écriture compensatoire après revue ; aucun remboursement automatique implémenté.
- Événements append-only avec empreinte de la preuve ; reçu JSON parent autorisé
  uniquement après confirmation réelle. Le reçu n'atteste pas du règlement bancaire.
- Rapprochement documentaire du règlement au compte école : net, frais constatés,
  écart aux frais estimés et approbation par un agent distinct. Comptabilité/direction
  avec `school.finance.approve` ; le caissier n'a ni ce droit ni la configuration.
- Interface parent pour les frais et dossiers, bénéficiaire et coûts avant paiement,
  conservation de la même demande après erreur réseau, vérification et lien du reçu.

## API et exploitation de recette

Tous les chemins sont sous `/api/v1/`, session et CSRF requis pour les écritures :

- `schools/{school}/singpay/merchant` : GET / POST, fondateur uniquement.
  POST remplace un jeu complet d'identifiants ; `enabled` doit rester faux.
  Ne pas mettre les clés dans une URL, un ticket, un journal ou une capture.
- `parents/singpay/{charge|admission}/{id}/quote` : accès autorisé, solde et historique.
- `parents/singpay/{charge|admission}/{id}/pay` : montant, canal, téléphone,
  clé d'idempotence UUID et révision marchande ; fermé tant que non activé.
- `parents/singpay/payments/{intent}/refresh` : POST de vérification, jamais de débit.
- `parents/singpay/payments/{intent}/receipt` : GET du reçu réel autorisé.
- `schools/{school}/singpay/reconciliation` : GET des 250 derniers, POST `{intent}`.
- `schools/{school}/singpay/payments/{intent}/settlement` : POST référence de relevé,
  net reçu et frais constatés ; POST `{approve:true}` par un autre contrôleur.
- `parents/singpay/webhook` : POST **503**, volontairement fermé jusqu'à contrat établi.

`YEM_SINGPAY_ENABLED=false` par défaut, indépendant de `YEM_PAYMENTS_LIVE_ENABLED`.
Les tests peuvent ouvrir les garde-fous uniquement avec `override_settings` et faux
transport ; la procédure de production n'autorise pas à le faire pour l'instant.

## Conditions restantes avant activation et fusion

1. Obtenir la confirmation officielle SingPay sur authentification callback
   (signature/secret, timestamp, rejeu, enveloppe), idempotence, états terminaux,
   politique de remboursement, formats réels par Airtel et Moov, et statut du règlement.
2. Confirmer compte marchand et distribution de **chaque école**, bénéficiaire,
   mandat d'utilisation par YEM, contrat de frais, fonds de test et GoLive.
3. Implémenter le contrat callback authentifié confirmé, avec recherche serveur
   obligatoire, protection anti-rejeu et tests de contrat anonymisés. Ne pas copier
   une signature Gaboshop supposée officielle.
4. Compléter les opérations comptables de remboursement/avoir et la résolution
   supervisée des paiements reçus mais non affectés ; conserver les preuves.
5. Compléter la pagination au-delà de 250 et un rapprochement planifié avec
   limitation des appels et alertes. L'interface administrative de préparation
   marchande et de rapprochement documentaire est disponible selon les droits.
6. Recette PostgreSQL concurrente et CI complètes, essais prestataire explicitement
   autorisés par le titulaire du compte (aucun ici), contrôle des PR/migrations récentes.
7. Vérifier lien parent → dossier → paiement → reçu → solde et relevé marchand sur
   une école pilote ; tester doublons, échec, timeout, faux callback et remboursement.

## Render : constat et déploiement contrôlé

Espace `My Workspace` confirmé par l'utilisateur. Service `yem-api`
(`srv-dbkbfde1egvs739jacug`) relié à main, Docker, déploiement automatique désactivé.
Dernier déploiement observé `dep-dblobtt9fdbs73cbj1k0`, statut live,
commit `aa84e0fcb144330d4175201157152175614c058f` : main est plus récent.
Le site statique `yem-pc-preview` suit main automatiquement ; fusionner aurait donc
aussi un effet sur cet aperçu. Aucune mutation Render durant ce chantier.

Après levée des blocages : déploiement de recette isolé, sauvegarde/restauration
vérifiée, migration additive, contrôles de santé et non-régression parents/finance,
puis lancement manuel sur un SHA validé et suivi du déploiement jusqu'à `live`.
Activer séparément l'école pilote après recette contractuelle. Retour arrière du
code sans suppression des écritures ni inversion destructive des migrations.

## Validation

Les résultats exécutés et les limites de l'environnement sont rapportés dans la PR.
Ne pas confondre tests simulés réussis et certification financière du prestataire.

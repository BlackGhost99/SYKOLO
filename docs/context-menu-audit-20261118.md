# Audit et consolidation des menus contextuels YEM

18 novembre 2026 — dépôt confirmé : `BlackGhost99/SYKOLO`, produit YEM. Base finale : `0d9ee8ecb374c6263ad9c363d2bb2d6bc661a05a`, intégrant la PR #200. Le travail initial parallèle a été conservé localement, puis remplacé pour la livraison par une consolidation du moteur déjà fusionné : une seule architecture `ContextMenu`, aucune seconde implémentation.

## Étendue de la revue

L’[inventaire](context-menu-inventory.md) recense 85 fichiers JSX hors tests, 155 fichiers Python hors migrations/tests, 302 déclarations de routes (inclusions comprises), 57 fichiers de tests frontend et 71 de tests backend. Il fournit un lien pour chaque fichier et chaque route. Il s’agit d’un recensement complet et d’une revue approfondie des parcours prioritaires, pas d’une lecture humaine exhaustive de chaque ligne du dépôt ni d’une certification de sécurité.

Entrée réelle : `main.jsx → App → AuthPanel`, puis espaces établissement, familles ou plateforme. `SchoolDashboard` résout les capacités de `my-access`, les sections, les onglets et les paramètres de navigation. Les menus doivent utiliser ces capacités et les actions des écrans, sans inventer un routeur parallèle. Le mode démonstration reste isolé de l’API réelle.

## Architecture et corrections complémentaires

La PR #200 fournit `ContextTarget`, `ContextTrigger`, `ContextReadOnly`, ainsi que `Table.rowActions` et `rowKey`. Les descripteurs explicites `{id,label,run,write,disabled,hidden}` sont évalués avec les droits et états de l’écran ; les actions sensibles ne sont pas des mutations directes du menu. Le clic gauche et les formulaires actuels restent utilisables.

Cette consolidation apporte :

- Un seul menu ouvert, même quand le suivant s’ouvre au clavier sans clic extérieur.
- Un portail dans le dialogue modal courant : un menu ne doit pas être rendu sous la couche du dialogue ni hors de son périmètre de focus.
- Un verrou synchrone d’invocation et une référence à la liste courante des actions, pour refuser une ancienne action retirée/désactivée. Les clés d’idempotence serveur restent nécessaires ; ce verrou ne les remplace pas.
- Une invalidation des capacités avant peinture, afin qu’un effet initial différé ne ferme pas le premier menu ouvert sur une ligne nouvellement chargée.
- Un placement borné au `visualViewport`, un repli à l’ancre lorsque le navigateur ne transmet pas de coordonnées, et fermeture lors du zoom/déplacement du viewport. Le défilement interne au menu reste possible ; les événements dont la cible est `window` sont traités sans erreur de type DOM.
- Une relation `aria-controls`, des cibles tactiles de 44 px, une hauteur adaptée au viewport dynamique et exclusion des menus à l’impression.
- Un opt-out explicite `data-native-context`, en complément des champs, liens, contenu éditable et sélection de texte déjà préservés.
- Des menus sur les factures, reçus et reçus groupés de `FinancialDocuments`. Ils activent les liens originaux de `PdfLinks` via leurs références : même URL privée, même cible et même téléchargement, sans logique financière dupliquée.

Aucun endpoint, modèle, permission ou migration n’est ajouté ou modifié. Aucun paiement, note, dossier, compte ou paramètre de production n’a été modifié pendant les vérifications.

## Couverture / rendement

| Domaine | Parcours utiles couverts | Limites |
|---|---|---|
| Élèves / inscriptions | Aperçu, dossier, préparation modification, classe et encaissement | Profil et capacités existants ; caisse seulement avec permission et inscription. La direction n’obtient pas le droit de caisse par son titre. |
| Parents / familles | Dossier du bon enfant depuis la classe | Droits parents et données sensibles existants ; pas de recherche globale de contacts supplémentaires. |
| Personnel / RH | Fiche professionnelle et rémunérations si autorisées | Pas d’attribution de rôle, de paiement RH ni d’annulation au clic. |
| Classes | Liste des élèves, dossier, préparation gestion et duplication existante | Année/cycle et permission de gestion conservés ; pas de création implicite. |
| Finance / impayés | Consultation, préparation de formulaire, reçus et PDF | Aucun encaissement, remboursement, clôture ou envoi de relance automatique. |
| Cahier de textes | Modifier, dupliquer en brouillon avec date à vérifier | Cours affecté et `writable` serveur ; pièces jointes non recopiées et aucune publication automatique. |
| Emploi du temps | Préparer déplacement ou copie | Gestionnaire et année active pour le menu ; collisions/revisions vérifiées au serveur lors de la validation. |
| Absences | Accès à la saisie, préparation locale et historique | Pas de clôture ni de justification vérifiée automatique ; états clôturés et rôle de surveillance conservés. |
| Évaluations | Aller à la saisie sur desktop/mobile | Pas de publication ou d’enregistrement de note par simple ouverture de menu. |
| Documents / bulletins | Ouvrir/télécharger les documents authentifiés existants | État annulé affiché, pas de recalcul ni modification du registre. |
| Admissions | Dossier, historique et caisse existante applicable | Décision, bourse et inscription restent dans leurs flux explicites. |
| Calendrier / curriculum | Modification préparée, consultation du programme | Pas de mutation silencieuse ni de cycle déduit d’un libellé. |
| Notifications / échanges | Préparer examen et réponse | Aucun message envoyé par le menu lui-même. |
| Établissements / super-admin | Gérer le dossier, consulter le contrat | Pas de suspension, prise d’accès, changement de droits ou décision commerciale directe. |

Pour les fichiers non directement enrôlés dans l’inventaire : formulaires et sélecteurs natifs restent natifs ; les écrans utilisant des composants partagés peuvent bénéficier de leurs menus. Les tableaux statistiques et démos n’exigent pas de menu global. Les espaces familles et enseignant mobile conservent leur navigation tactile, avec le bouton … sur les composants pertinents ; aucun appui long obligatoire n’est introduit.

Exclusions intentionnelles : soumission d’import, transfert/inscription définitive, création réelle de paiement, approbation/annulation/dépôt/clôture financière, paiement RH ou dépense, publication de résultats/bulletins, décision d’admission/conseil, clôture d’année, attribution/suppression de droits, reset de compte/MFA, suspension d’établissement et restriction commerciale. Ces opérations restent dans leurs confirmations, formulaires, motifs, états, révisions et validations existants. Leur absence du menu ne doit pas être compensée par un appel API alternatif.

## Protections serveur examinées

- `services.school_access`, `has_permission` : appartenance active, établissement, rôles et délégations ; aucune élévation de droits ajoutée.
- `student_access` et vues `overview` : séparation profil, administratif, sensible et finances. Un menu ne doit pas récupérer de champs masqués.
- `SchoolSessionMiddleware` : session d’établissement et séparation des espaces famille/plateforme. `platform_only`, authentification et MFA existants conservés.
- `SchoolCycleBoundaryMiddleware` et `cycle_scope` : allowlist explicite des routes auditées et revalidation des cycles à chaque requête. Les modules non sécurisés pour les comptes limités restent refusés ; aucun élargissement pour rendre un raccourci disponible.
- Cahier : cours filtrés par cycle et affectation ; année/classe/cours actifs pour l’écriture ; familles limitées aux séances publiées de leurs enfants et de l’année choisie.
- Notes, présence et planning : cours/classe/affectation, permissions, états publié/clôturé, conflits de planning et révisions. Les menus préparent les actions et ne remplacent pas ces contrôles.
- Finances : transactions, verrous `select_for_update`, idempotence des paiements simples/groupés et séparation des fonctions caisse/approbation/annulation. Aucune validation rapide ajoutée.
- Années clôturées : gardes métier, triggers PostgreSQL et traduction du conflit en 409 inchangés.
- Abonnements : `CommercialWorkspaceBoundaryMiddleware` bloque les mutations et les écritures cachées dans les GET restreints. `ContextReadOnly` vient d’une décision commerciale explicite de `my-access`, et non d’une simple date d’expiration. Le serveur reste l’autorité même si l’état affiché du navigateur est périmé.

## Vérifications et limites

Tests locaux du moteur et des parcours : clavier, focus, liens et champs natifs, texte sélectionné, fermeture extérieure, plusieurs menus, fenêtre modale, positionnement viewport/zoom, filtre/tri, retrait d’action/droit, restriction commerciale et absence de soumission implicite. Les tests de composants couvrent secrétariat, caisse, direction sans délégation de caisse, abonnement restreint, fiche personnel autorisée/refusée, famille par classe, cahier modifiable/lecture seule et planning lecteur/gestionnaire/année archivée. Les mocks vérifient l’absence de POST métier dans les raccourcis d’ouverture/préparation.

Version consolidée : les 253 tests frontend passent (57 fichiers), dont 24 nouveaux tests de consolidation/parcours et les 8 tests initiaux du moteur. Le build Vite passe ; Django check ne signale aucun problème et aucune migration n’est détectée. Les 138 tests serveur ciblés passent sur cette version (SQLite de test). La CI complète PostgreSQL/Docker est à consulter dans la PR. Les tests serveur locaux utilisent une base SQLite de test isolée ; les triggers et verrous PostgreSQL ainsi que Docker nécessitent la CI Linux.

La tentative de recette visuelle a expiré dans l’outil navigateur sans observation. Aucune recette visuelle, lecteur d’écran, appareil tactile réel ou parcours de compte en production n’est déclarée réussie. Le bundle principal dépasse déjà 500 ko (avertissement Vite) ; `scrollTo` n’est pas implémenté par jsdom. Une recette manuelle sur un établissement de test reste à faire avant déploiement.

## Déploiement constaté

Render `My Workspace` a été confirmé explicitement par l’utilisateur. Le 17 novembre, les services `yem-api` et `yem-pc-preview` étaient `live` sur `40298e64a6f5a2d27c20d946bd305b482af38dca`. Les requêtes HTTP réelles `/healthz` et `/readyz` renvoyaient 200 (commit concordant, environnement production, PostgreSQL), ainsi que les pages d’accueil API/preview. Auto-déploiement API désactivé ; preview sur main automatiquement.

Nouvelle lecture le 18 novembre : `yem-api` est désormais live sur `0d9ee8ecb374c6263ad9c363d2bb2d6bc661a05a` (PR #200), déploiement terminé à 7 h 42 Africa/Lagos. `yem-pc-preview` reste sur `40298e6`. Le statut live ne prouve pas à lui seul les parcours UI ; les contrôles HTTP /healthz et /readyz ont de nouveau renvoyé 200 avec le commit API concordant. Cette consolidation n’est pas déployée. Aucun déploiement ni fusion n’a été déclenché par ce chantier ; la documentation historique disant qu’aucun service YEM n’existe est périmée.

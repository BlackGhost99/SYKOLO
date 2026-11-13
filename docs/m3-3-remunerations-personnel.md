# YEM — M3.3 : gestion privée des rémunérations et règlements déclarés

Ce lot prolonge la **fiche technique du personnel M3.2** sans y exposer
automatiquement de données salariales. Il reste distinct du module de
scolarité, des tarifs et des encaissements des familles.

## Fonctionnement

- Personnel → **Rémunérations (RH)**, uniquement avec le droit
  `school.payroll.read`, affiche les paies par collaborateur, année,
  mois et devise. La fiche technique individuelle comporte un historique
  des montants uniquement si l'utilisateur possède **aussi** le droit RH.
- Création d'une rémunération pour un mois : catégorie **mensuelle / heures /
  séances / forfait**, brut, retenues, net, devise ISO et observation. Ces
  montants sont saisis par un responsable, sans grille fixe imposée par YEM.
  Un collaborateur peut avoir plusieurs catégories durant un mois.
- L'enregistrement initial est un **brouillon**, modifiable sous contrôle de
  révision par un compte autorisé. Aucun paiement n'est permis à ce stade.
- Validation par un **autre compte** habilité. Le préparateur ne peut pas
  approuver sa propre paie, même avec plusieurs rôles ; le salarié concerné
  ne peut pas auto-préparer/auto-approuver.
- L'économe enregistre ensuite des **versements déjà effectués** et
  justifiés, partiels ou complets. Une transaction PostgreSQL verrouille
  la paie, contrôle le plafond du net à payer, et exige une clé UUID
  d'idempotence pour éviter les doublons en cas de renvoi réseau.
- Une correction d'encaissement s'effectue par **annulation historisée**
  avec motif (10 caractères minimum) et contrôleur différent du caissier
  initial. La ligne originale reste conservée ; aucun paiement n'est
  supprimé.
- Les années clôturées sont en lecture seule pour les actions de paie.
  Aucune somme d'une autre devise ou école n'est mélangée.

## Droits distincts

| Droit | Objet |
| --- | --- |
| `school.payroll.read` | Historique détaillé des rémunérations et versements |
| `school.payroll.manage` | Préparer / rectifier un brouillon |
| `school.payroll.approve` | Valider une paie préparée par autrui |
| `school.payroll.pay` | Déclarer un versement déjà exécuté |
| `school.payroll.reverse` | Annuler le versement d'un autre acteur |

Rôles standard sur une école privée : **direction** = consulter/valider ;
**comptabilité** = consulter/préparer/annuler indépendamment ;
**économe** = consulter/déclarer les versements. La direction n'obtient
pas l'écriture ni le pouvoir de s'auto-valider. Ces droits restent
personnalisables ; la migration ne les ajoute aux comptes existants que
si leur rôle standard conserve les permissions financières correspondantes.
Un rôle de secrétariat ou d'enseignement n'obtient aucun accès salarial.
Pour une école publique, les mutations financières sont exclues des rôles
par défaut par la politique de gouvernance.

## API / sécurité

- `GET /api/v1/schools/{school}/payroll/staff` — identités minimales pour
  l'interface RH
- `GET/POST /api/v1/schools/{school}/payroll/runs` — paies par année/employé
- `GET/PATCH /api/v1/schools/{school}/payroll/runs/{id}`
- `POST /api/v1/schools/{school}/payroll/runs/{id}/approve`
- `POST /api/v1/schools/{school}/payroll/runs/{id}/payments`
- `POST /api/v1/schools/{school}/payroll/payments/{id}/void`

La migration `0051_payroll_ledger` dépend de `0050_staff_professional_dossier`.
Les tables PostgreSQL sont placées sous RLS ; l'accès Data API
`anon` / `authenticated` est révoqué. Les endpoints exigent
l'authentification Django, l'établissement autorisé, le droit exact
et un CSRF valide. `SchoolAudit` conserve identifiants, acteurs et
étapes de traitement, **sans y écrire les montants des salaires**.

## Limites, à ne pas confondre avec des paiements bancaires

**Cette fonction n'effectue aucun transfert d'argent** et n'affirme pas
qu'un prestataire de paiement a confirmé une opération. Elle conserve les
déclarations de paiements manuels et références physiques fournies par
l'établissement. Aucun prélèvement bancaire, aucune fiche fiscale
personnalisée, aucun calcul automatique de cotisations sociales,
d'imposition, d'heures supplémentaires ou de conformité OHADA/Gabon
n'est inclus.

La comptabilisation générale des dépenses, les budgets, fournisseurs,
achats et le rapprochement bancaire demeurent un chantier financier
distinct du salaire brut/net. Le tableau de bord de cette paie ne doit
pas être assimilé à un compte de résultat.

## Vérification avant production

CI : `manage.py check`, `makemigrations --check`, migration PostgreSQL,
tests `institutions.test_payroll` et suite Django/React, construction
Docker, test de démarrage et contrôle de la configuration Render.

**Ne pas déployer sur Supabase YEM sans sauvegarde réelle chiffrée et
restauration prouvée sur une base isolée.** La réussite d'une sauvegarde
synthétique en CI n'est pas une sauvegarde des vrais dossiers. Aucune
simulation de paie ne doit être enregistrée dans le lycée réel.

# YEM — Chantier A, A6b : ventes extrascolaires indépendantes

**État :** conception du registre définitif ; le lot A6b1 fournit seulement des estimations, sans vente et sans paiement.

## 1. Principes non négociables

- Les **frais scolaires** et les **prestations extrascolaires** ont des registres et justificatifs distincts. Les ventes d'uniformes, repas et services ne sont jamais comptées comme paiements de scolarité, ni ajoutées à un total « recettes » sans préciser leur nature.
- Les **sorties** (dépenses, fournisseurs, personnel, budgets) appartiennent au **chantier B**. Leurs tables, rôles, migrations et fichiers `operating_*` restent hors périmètre. Les achats des fournisseurs peuvent être liés ultérieurement, uniquement par un contrat d'interface partagé et validé.
- Le catalogue A6a est une **configuration de tarifs**, pas un stock, un compte de caisse ou une preuve d'encaissement. A6b1 calcule un **devis indicatif** sans le persister, et son total ne doit figurer dans aucun indicateur de recettes.
- Une recette extrascolaire n'est comptabilisée comme entrée réellement reçue que sur preuve d'un **paiement manuel déclaré** ou du règlement **confirmé de façon authentifiée** par un prestataire. « Vente », « facturé », « encaissé » et « certifié » sont des notions différentes.

## 2. Contrat A6b1 — devis non enregistré

`POST /api/v1/schools/{school_id}/finance/extras/quote`

Exemple requête :

```json
{
  "academic_year": "uuid-annee-de-la-meme-ecole-ou-null",
  "items": [{"id": "uuid-article", "quantity": 2}]
}
```

Réponse : ligne par article avec identifiants, famille B01–B08, libellé, variante, unité, quantité, **prix serveur**, sous-total, devise, total, révision du catalogue, horodatage et `state="estimation_non_enregistree"`. Les attributs `recorded_sale`, `recorded_payment`, `stock_reserved`, `payable` restent faux.

**Garde-fous** : `school.finance.read`, isolation école/année, IDs UUID, quantité entière de 1 à 1 000, maximum 30 lignes, doublons interdits, produit actif requis, même devise, Decimal exact, aucun prix envoyé par le navigateur accepté. Les calculs n'écrivent ni transaction, ni historique, ni dette, ni stock.

## 3. Registre futur A6b2 — à implémenter après coordination des migrations B

Les modèles futurs seront **propres aux entrées** (noms indicatifs, sans créer les tables dans A6b1) :

| Objet | Rôle |
| --- | --- |
| `ExtraSale` | Numéro établissement unique, acheteur (parent ou tiers), année facultative, statut brouillon / confirmé / annulé / avoir, devise, date, créateur, révision et clé d'idempotence |
| `ExtraSaleLine` | Article catalogue référencé, **snapshot immuable** du code, de la famille, du libellé, de l'unité, de la variante, du prix et de la quantité, montant exact à la validation |
| `ExtraSalePayment` | Versement manuel, devise, montant, méthode « Espèces » (une seule méthode), référence, date, auteur, date d'annulation éventuelle, preuve associée, clé d'idempotence |
| `ExtraSaleAdjustment` | Avoir ou annulation contrepassée ; conservation des originaux, motif, auteur et historique de validation indépendante |
| `ExtraStockMovement` (si activé) | Entrées de stock physiques / sorties liées à une vente ; mouvements réversibles par contrepassation, stocks négatifs refusés et services non stockables |

**Migrations :** le chantier B possède déjà une suite non fusionnée `0082` à `0085`. Ne créer ou réserver une nouvelle migration de ventes **qu'après** la fusion et la vérification de la tête des migrations du B. Ne pas modifier les modèles de dépenses, ne pas introduire une branche parallèle `0082`–`0085` et ne pas déployer une migration manuelle sur Supabase.

## 4. Opérations et permissions à développer

1. Créer une vente brouillon à partir de l'estimation et **revérifier la version de prix** lors de la confirmation.
2. Confirmer la vente dans une transaction SQL ; calculer les lignes et les stocks à partir des snapshots plutôt que du catalogue mutable.
3. Enregistrer des paiements **partiels** et afficher `total_facturé`, `total_reçu`, `solde_dû`, `trop_perçu_à_vérifier` séparément. Un règlement ne peut ni effacer la dette d'une autre vente, ni être attribué à une autre école ou devise.
4. Émettre les pièces PDF : devis, facture, reçu partiel, reçu final, avoir ; école et acheteur visibles selon les droits, identifiant et statut clairement indiqués.
5. Prévoir `school.finance.read`, `school.finance.manage`, `school.finance.receive`, `school.finance.reverse`, et validation indépendante pour annulation ou remboursement. Le propriétaire reste sur ses synthèses agrégées.
6. Prévenir les doubles validations (verrou SQL + idempotence + audit), les paiements futures-datés, la simulation traitée comme recette réelle et les paiements SingPay non confirmés.
7. Synchroniser les **synthèses sans double comptage** : `Scolarité`, `Autres frais scolaires`, `Extrascolaire`, `Autres produits` et `Autres entrées de trésorerie`. Jamais d'addition de devises différentes ni de ventes simplement facturées aux encaissements.
8. Ajouter tests de non-régression sur entrées/sorties, isolation multi-écoles, concurrents, stocks insuffisants, paiements partiels, annulations et historique de prix.

## 5. Critères de recette minimaux

- Un repas à 2 500 XAF × 2 = 5 000 XAF, sans flottants.
- Modifier ensuite son prix à 3 000 XAF ne modifie **pas** les lignes d'une vente déjà confirmée.
- Facture 20 000 XAF, acompte 5 000 XAF, solde 15 000 XAF ; la caisse déclare 5 000 XAF, pas 20 000 XAF.
- Une école étrangère ne peut lire ni modifier cette vente ou son reçu.
- Une vente d'uniformes ne paie pas les frais mensuels de scolarité.
- Un article archivé, une devise différente et une année étrangère ne peuvent être facturés.
- Une tentative de paiement répétée ne crée pas une seconde entrée.
- Les transactions de remboursement conservent toujours la trace de la recette originale.

**Condition de passage à A6b2 :** branche de dépenses B fusionnée et migrations cohérentes, plus validation des comptes de paiement et du modèle de stock avec l'équipe métier. Aucun modèle de ventes ni déploiement n'est affirmé comme opérationnel par ce document.

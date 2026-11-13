# YEM — M3.1 : cohérence des soldes après bourses partielles

## Anomalie corrigée

Les frais de scolarité créés après validation d'une bourse partielle conservent
leur **montant brut** et le montant de **prise en charge**. La fiche technique
de l'élève utilisait correctement le solde net, mais les vues de synthèse
`overview/students`, `overview/classes`, `overview/finance` et les totaux du
relevé `finance/enrollments/{id}/statement` utilisaient encore le montant brut.
Un établissement pouvait ainsi voir une créance artificiellement gonflée.

**Exemple de recette (base de test temporaire, aucun encaissement réel)** :

| Indicateur | Valeur |
| --- | ---: |
| Frais de scolarité bruts | 60 000 XAF |
| Bourse validée (40 %) | 24 000 XAF |
| Montant dû à la famille | 36 000 XAF |
| Encaissement de test ultérieur | 10 000 XAF |
| Solde net après paiement | 26 000 XAF |

## Règle métier

- `brut = FeeCharge.amount` reste conservé pour la traçabilité.
- `prise_en_charge = FeeCharge.scholarship_discount` reste séparée d'un paiement.
- `facturé_net = brut - prise_en_charge`.
- `restant_dû = facturé_net - paiements_non_annulés`.
- Arriérés et montants exigibles se calculent sur la dette nette.
- Les totaux sont isolés par devise et année, sans paiement fictif associé à la bourse.

Le résumé `finance/summary` calculait déjà la dette nette. Il charge
maintenant directement la colonne de remise dans sa requête pour éviter
des accès différés supplémentaires à la base.

## Vérification

Test de régression dans
`institutions.test_admission_finance_scholarships.EnrollmentFinancialConditionsTests.test_partial_percentage_makes_cash_due_and_tuition_net_without_fake_payment`.

Le scénario exerce : décision de bourse, facture générée,
consultation caissier, fiche finance par élève, tableau de bord global,
résumé des classes, relevé individuel, résumé comptable et encaissement
partiel de test. Toutes les vues doivent rester alignées avant et après
le paiement.

Ces corrections n'ajoutent aucune migration, ne modifient pas les
écritures historiques et ne touchent ni aux interfaces Professeur/Parents
ni aux droits des utilisateurs. Le déploiement de production reste
**manuel** et nécessite tests CI réussis, surveillance et contrôle ciblé
des chiffres sur un établissement autorisé.

Suite du chantier #30 : dépenses, budget, paie et suivi des fournisseurs,
à développer comme modules séparés avec droits et contrôle indépendant.

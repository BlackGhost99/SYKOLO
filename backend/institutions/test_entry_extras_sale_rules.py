"""A6b2 pre-ledger tests: amounts remain independent of tuition and expenses."""
from datetime import date
from uuid import uuid4

from django.test import SimpleTestCase

from .entry_extras_sale_rules import (
    ExtrasSaleRuleError,
    snapshot_sale_lines,
    summarize_sale_payments,
)


class SaleRulesTests(SimpleTestCase):
    def setUp(self):
        self.school_id, self.year_id = str(uuid4()), str(uuid4())
        self.sale_id = str(uuid4())
        self.lunch, self.bus, self.euro = str(uuid4()), str(uuid4()), str(uuid4())
        self.catalog = [
            {"id": self.lunch, "code": "CANTINE", "group": "B03", "kind": "produit",
             "label": "Repas midi", "variant": "normal", "unit": "repas",
             "unit_price": "2500.00", "currency": "XAF",
             "academic_year": self.year_id, "active": True},
            {"id": self.bus, "code": "BUS", "group": "B04", "kind": "service",
             "label": "Transport", "variant": "", "unit": "mois",
             "unit_price": "15000.00", "currency": "XAF",
             "academic_year": None, "active": True},
            {"id": self.euro, "code": "LIVRE", "group": "B02", "kind": "produit",
             "label": "Livre", "variant": "", "unit": "unité",
             "unit_price": "20.00", "currency": "EUR",
             "academic_year": None, "active": True},
        ]

    def make_snapshot(self, selected=None, revision=1, catalog=None, expected=1):
        return snapshot_sale_lines(
            school_id=self.school_id, academic_year=self.year_id,
            catalog_revision=revision, expected_revision=expected,
            catalog_items=self.catalog if catalog is None else catalog,
            selections=selected or [{"id": self.lunch, "quantity": 2},
                                    {"id": self.bus, "quantity": 1}],
        )

    def payment(self, amount, *, status="settled", proof="manual_declared",
                day=date(2026, 11, 20), reversed=False, school=None, sale=None,
                currency="XAF"):
        return {
            "id": str(uuid4()), "sale_id": sale or self.sale_id,
            "school_id": school or self.school_id, "currency": currency,
            "amount": amount, "paid_on": day, "status": status,
            "proof_level": proof, "reversed": reversed,
        }

    def summary(self, payments, *, total="20000.00"):
        return summarize_sale_payments(
            sale_id=self.sale_id, school_id=self.school_id,
            currency="XAF", sale_total=total, payments=payments,
            as_of=date(2026, 11, 21),
        )

    def test_price_snapshot_remains_immutable_after_catalog_changes(self):
        initial = self.make_snapshot()
        self.assertEqual(initial["total"], "20000.00")
        self.assertEqual([x["line_total"] for x in initial["lines"]],
                         ["5000.00", "15000.00"])
        self.assertEqual(initial["lines"][0]["unit_price"], "2500.00")
        self.assertEqual(initial["status"], "snapshot_prepared_not_posted")
        updated = [dict(x) for x in self.catalog]
        updated[0]["unit_price"] = "3000.00"
        next_sale = self.make_snapshot(revision=2, expected=2, catalog=updated)
        self.assertEqual(next_sale["total"], "21000.00")
        self.assertEqual(initial["total"], "20000.00")
        self.assertEqual(initial["lines"][0]["unit_price"], "2500.00")
        with self.assertRaises(ExtrasSaleRuleError):
            self.make_snapshot(revision=2, expected=1, catalog=updated)

    def test_partial_payments_avoid_fake_revenue_or_cross_balancing(self):
        first = self.summary([
            self.payment("5000.00"),
            self.payment("2000.00", proof="provider_confirmed"),
            self.payment("9000.00", status="pending"),
            self.payment("3500.00", day=date(2026, 11, 22)),
            self.payment("1000.00", reversed=True),
        ])
        self.assertEqual(first["billed"], "20000.00")
        self.assertEqual(first["received_declared"], "5000.00")
        self.assertEqual(first["received_provider_confirmed"], "2000.00")
        self.assertEqual(first["received_total"], "7000.00")
        self.assertEqual(first["pending_not_revenue"], "12500.00")
        self.assertEqual(first["outstanding"], "13000.00")
        self.assertEqual(first["overpayment_review"], "0.00")
        self.assertTrue(first["contains_manual_declarations"])
        self.assertFalse(first["only_provider_confirmed_receipts"])
        empty = self.summary([])
        self.assertFalse(empty["only_provider_confirmed_receipts"])
        self.assertEqual(empty["received_total"], "0.00")

    def test_overpayment_stays_in_review_without_offset_to_other_sale(self):
        result = self.summary([
            self.payment("20000.00"),
            self.payment("2500.00", proof="provider_confirmed"),
        ])
        self.assertEqual(result["outstanding"], "0.00")
        self.assertEqual(result["overpayment_review"], "2500.00")

    def test_cannot_mix_currency_or_school_or_sale(self):
        other_school, other_sale = str(uuid4()), str(uuid4())
        for entry in (
            self.payment("1000.00", currency="EUR"),
            self.payment("1000.00", school=other_school),
            self.payment("1000.00", sale=other_sale),
            self.payment("5.00", proof="none"),
            self.payment("5.00", status="reported"),
        ):
            with self.assertRaises(ExtrasSaleRuleError):
                self.summary([entry])
        repeated = self.payment("1000.00")
        with self.assertRaises(ExtrasSaleRuleError):
            self.summary([repeated, repeated])

    def test_rejects_float_and_invalid_quantities_and_multicurrency(self):
        for invalid_quantity in (True, 0, -1, 1001, 1.5, "2"):
            with self.assertRaises(ExtrasSaleRuleError):
                self.make_snapshot([{"id": self.lunch, "quantity": invalid_quantity}])
        with self.assertRaises(ExtrasSaleRuleError):
            self.make_snapshot([{"id": self.lunch, "quantity": 1},
                                {"id": self.euro, "quantity": 1}])
        with self.assertRaises(ExtrasSaleRuleError):
            self.make_snapshot([{"id": self.lunch, "quantity": 1}] * 2)
        with self.assertRaises(ExtrasSaleRuleError):
            self.make_snapshot([{"id": self.lunch, "quantity": 1}], expected=True)
        for amount in (1000.0, "-1.00", "1e4", "NaN", "", "1.001"):
            with self.assertRaises(ExtrasSaleRuleError):
                self.summary([self.payment(amount)])
        with self.assertRaises(ExtrasSaleRuleError):
            self.make_snapshot(catalog=[
                {**self.catalog[0], "unit_price": "-100.00"}])

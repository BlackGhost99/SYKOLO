"""M3.4 tests: financial separation, budget caps, tenant isolation and audit."""
import json
import uuid
from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .academic_models import AcademicYear
from .models import Organization, School, SchoolRole, SchoolMember, SchoolAudit
from .operating_models import OperatingSupplier, OperatingBudget, OperatingExpense, OperatingExpensePayment
from .services import ROLE_TEMPLATES


class OperatingLedgerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        org = Organization.objects.create(name="M3.4 fictif - recettes")
        self.school = School.objects.create(organization=org, name="Lycée test M3.4",
                                            school_type="lycee_general", education_cycles=["lycee_general"])
        self.other = School.objects.create(organization=org, name="Autre lycée test M3.4",
                                           school_type="lycee_general", education_cycles=["lycee_general"])
        for school in (self.school, self.other):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=list(permissions))
        self.users = {}
        for role in ("direction", "comptabilite", "econome", "secretariat", "enseignant", "parent"):
            person = User.objects.create_user(username="m34-" + role, password="Yem-test-operating-2026!")
            SchoolMember.objects.create(school=self.school, user=person,
                                        role=SchoolRole.objects.get(school=self.school, code=role))
            self.users[role] = person
        self.outsider = User.objects.create_user(username="m34-outsider", password="Yem-test-operating-2026!")
        self.year = AcademicYear.objects.create(school=self.school, code="2026-2027", name="2026-2027",
                                                start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
                                                status="current")
        self.other_year = AcademicYear.objects.create(school=self.other, code="2026-2027", name="2026-2027",
                                                      start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
                                                      status="current")
        self.client = Client(enforce_csrf_checks=True)
        self.base = "/api/v1/schools/" + str(self.school.pk) + "/operating/"
        self.login("comptabilite")

    def login(self, who):
        self.client.force_login(self.users.get(who, who) if isinstance(who, str) else who)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def get(self, route, params=None):
        return self.client.get(self.base + route, params or {})

    def post(self, route, payload):
        return self.client.post(self.base + route, json.dumps(payload),
                                content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def patch(self, route, payload):
        return self.client.patch(self.base + route, json.dumps(payload),
                                 content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def supplier(self):
        response = self.post("suppliers", {
            "name": "Fournitures Gabon TEST", "contact": "Agence fictive",
            "phone": "000", "email": "achats@example.test",
        })
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def budget(self, amount="100000.00", category="Entretien"):
        response = self.post("budgets", {
            "year": str(self.year.pk), "category": category,
            "currency": "XAF", "ceiling": amount,
        })
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def expense(self, budget_id, supplier_id, amount="60000.00", invoice="FAC-TEST-001"):
        response = self.post("expenses", {
            "budget": budget_id, "supplier": supplier_id,
            "amount": amount, "label": "Réparation tables fictives",
            "invoice_reference": invoice, "expense_on": "2026-11-10",
        })
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def approved_budget(self):
        supplier = self.supplier()
        budget = self.budget()
        self.assertFalse(budget["approved"])
        self.assertEqual(self.post("budgets/"+budget["id"]+"/approve", {
            "revision": budget["revision"],
        }).status_code, 403)
        self.login("direction")
        response = self.post("budgets/"+budget["id"]+"/approve", {
            "revision": budget["revision"],
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["approved"])
        self.login("comptabilite")
        return supplier, response.json()

    def approve_expense(self, expense):
        self.login("direction")
        response = self.post("expenses/"+expense["id"]+"/approve", {
            "revision": expense["revision"],
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.login("comptabilite")
        return response.json()

    def pay(self, expense_id, amount="20000.00", key=None):
        return self.post("expenses/"+expense_id+"/payments", {
            "amount": amount, "method": "especes", "reference": "CAISSE-TEST-2026",
            "paid_on": "2026-11-12", "idempotency_key": key or str(uuid.uuid4()),
        })

    def test_budget_and_expense_independent_approvals_with_partial_receipts(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        self.assertEqual(expense["status"], "draft")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/approve", {
            "revision": expense["revision"],
        }).status_code, 403)
        expense = self.approve_expense(expense)
        self.assertEqual(expense["status"], "approved")
        # 60 000 XAF are already committed before any payment.
        overview = self.get("summary", {"year": str(self.year.pk)}).json()
        self.assertEqual(overview["totals"]["XAF"], {
            "ceiling": "100000.00", "committed": "60000.00",
            "paid": "0.00", "remaining": "40000.00",
        })
        self.login("econome")
        key = str(uuid.uuid4())
        first = self.pay(expense["id"], key=key)
        self.assertEqual(first.status_code, 201, first.content)
        again = self.pay(expense["id"], key=key)
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(first.json()["id"], again.json()["id"])
        self.assertEqual(self.pay(expense["id"], amount="90000.00").status_code, 409)
        item = self.get("expenses/"+expense["id"]).json()
        self.assertEqual(item["expense"]["status"], "partially_paid")
        self.assertEqual(item["expense"]["balance"], "40000.00")
        self.assertEqual(self.post("payments/"+first.json()["id"]+"/void", {
            "reason": "Annulation incorrecte",
        }).status_code, 403)
        self.login("comptabilite")
        voided = self.post("payments/"+first.json()["id"]+"/void", {
            "reason": "Justificatif de règlement erroné",
        })
        self.assertEqual(voided.status_code, 200, voided.content)
        self.assertTrue(voided.json()["voided"])
        self.assertEqual(self.get("expenses/"+expense["id"]).json()["expense"]["balance"], "60000.00")
        self.assertEqual(OperatingExpensePayment.objects.count(), 1)
        self.assertNotIn("60000", str(list(SchoolAudit.objects.filter(school=self.school).values_list("details", flat=True))))
        self.assertTrue(SchoolAudit.objects.filter(event="operating_expense_disbursed").exists())
        self.assertTrue(SchoolAudit.objects.filter(event="operating_expense_payment_voided").exists())

    def test_overspend_rejected_and_draft_versions(self):
        supplier, budget = self.approved_budget()
        first = self.expense(budget["id"], supplier["id"], "75000.00")
        second = self.expense(budget["id"], supplier["id"], "30000.00", "FAC-TEST-002")
        self.approve_expense(first)
        self.login("direction")
        rejected = self.post("expenses/"+second["id"]+"/approve", {"revision": second["revision"]})
        self.assertEqual(rejected.status_code, 409, rejected.content)
        self.assertFalse(OperatingExpense.objects.get(pk=second["id"]).approved_at)
        self.login("comptabilite")
        edited = self.patch("expenses/"+second["id"], {
            "revision": 1, "amount": "25000.00",
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(self.patch("expenses/"+second["id"], {
            "revision": 1, "amount": "12000.00",
        }).status_code, 409)
        self.login("direction")
        approval = self.post("expenses/"+second["id"]+"/approve", {
            "revision": edited.json()["revision"],
        })
        self.assertEqual(approval.status_code, 200, approval.content)
        self.assertEqual(self.get("summary") .json()["totals"]["XAF"]["remaining"], "0.00")
        self.assertEqual(self.post("expenses/"+first["id"]+"/approve", {
            "revision": first["revision"],
        }).status_code, 409)

    def test_supplier_versions_and_tenant_guards(self):
        supplier = self.supplier()
        updated = self.patch("suppliers/"+supplier["id"], {
            "revision": supplier["revision"], "phone": "01234",
        })
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(self.patch("suppliers/"+supplier["id"], {
            "revision": 1, "name": "Fausse modification",
        }).status_code, 409)
        self.assertEqual(self.post("budgets", {
            "year": str(self.other_year.pk), "category": "Énergie",
            "currency": "XAF", "ceiling": "20000.00",
        }).status_code, 404)
        # A valid UUID from another school must not widen a year-scoped GET.
        self.assertEqual(self.get("budgets", {"year": str(self.other_year.pk)}).status_code, 404)
        self.assertEqual(self.get("expenses", {"year": str(self.other_year.pk)}).status_code, 404)
        self.login("secretariat")
        self.assertEqual(self.get("suppliers").status_code, 403)
        self.assertEqual(self.get("budgets").status_code, 403)
        self.assertEqual(self.post("expenses", {}).status_code, 403)
        self.login("enseignant")
        self.assertEqual(self.get("summary").status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.get("summary").status_code, 404)
        self.login("comptabilite")
        self.assertEqual(self.client.get(
            "/api/v1/schools/"+str(self.other.pk)+"/operating/suppliers",
        ).status_code, 404)

    def test_invalid_expense_and_closed_year_fail_closed(self):
        supplier, budget = self.approved_budget()
        self.assertEqual(self.post("expenses", {
            "budget": budget["id"], "supplier": supplier["id"],
            "label": "Achat", "invoice_reference": "FACTURE-1",
            "expense_on": "2024-01-01", "amount": "1000.00",
        }).status_code, 422)
        expense = self.expense(budget["id"], supplier["id"])
        self.year.status = "closed"
        self.year.save(update_fields=["status"])
        self.assertEqual(self.post("budgets", {
            "year": str(self.year.pk), "category": "Énergie",
            "currency": "XAF", "ceiling": "10000.00",
        }).status_code, 409)
        self.assertEqual(self.post("expenses", {
            "budget": budget["id"], "supplier": supplier["id"],
            "label": "Achat", "invoice_reference": "FACTURE-2",
            "expense_on": "2026-11-10", "amount": "1000.00",
        }).status_code, 422)
        self.login("direction")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/approve", {
            "revision": expense["revision"],
        }).status_code, 409)
        self.login("econome")
        self.assertEqual(self.pay(expense["id"]).status_code, 409)

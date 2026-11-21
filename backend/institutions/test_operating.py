"""M3.4 tests: financial separation, budget caps, tenant isolation and audit."""
import json
import uuid
from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .academic_models import AcademicYear
from .models import Organization, School, SchoolRole, SchoolMember, SchoolAudit
from .operating_models import (OperatingSupplier, OperatingBudget, OperatingExpense,
                               OperatingExpensePayment, OperatingExpenseCategory,
                               OperatingExpenseDecision, OperatingClassificationOption)
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
        self.category = OperatingExpenseCategory.objects.create(
            school=self.school, code="materiel", name="Matériel", suggested_pole="school",
        )
        self.subcategory = OperatingExpenseCategory.objects.create(
            school=self.school, parent=self.category, code="laboratoire", name="Laboratoire",
        )
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

    def expense(self, budget_id, supplier_id, amount="60000.00", invoice="FAC-TEST-001", pole="school"):
        response = self.post("expenses", {
            "budget": budget_id, "supplier": supplier_id, "activity_pole": pole,
            "category_ref": str(self.category.pk),
            "subcategory_ref": str(self.subcategory.pk),
            "cost_center": "Pédagogie" if pole == "school" else "Activité annexe",
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

    def submit_expense(self, expense):
        self.login("comptabilite")
        response = self.post("expenses/"+expense["id"]+"/submit", {
            "revision": expense["revision"],
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def approve_expense(self, expense):
        submitted = self.submit_expense(expense)
        self.login("direction")
        response = self.post("expenses/"+expense["id"]+"/approve", {
            "revision": submitted["revision"],
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.login("comptabilite")
        return response.json()

    def pay(self, expense_id, amount="20000.00", key=None):
        return self.post("expenses/"+expense_id+"/payments", {
            "amount": amount, "method": "especes", "reference": "CAISSE-TEST-2026",
            "paid_on": "2026-11-12", "idempotency_key": key or str(uuid.uuid4()),
        })

    def test_workflow_submission_is_mandatory_and_roles_independent(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        self.login("econome")
        self.assertEqual(self.pay(expense["id"]).status_code, 409)
        self.login("direction")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/approve", {
            "revision": expense["revision"],
        }).status_code, 409)
        sent = self.submit_expense(expense)
        self.assertEqual(sent["status"], "submitted")
        self.assertEqual(self.get("summary").json()["totals"]["XAF"]["committed"], "0.00")
        self.login("comptabilite")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/approve", {
            "revision": sent["revision"],
        }).status_code, 403)
        self.assertEqual(self.post("expenses/"+expense["id"]+"/submit", {
            "revision": sent["revision"],
        }).status_code, 409)
        self.login("direction")
        ok = self.post("expenses/"+expense["id"]+"/approve", {"revision": sent["revision"]})
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()["workflow_state"], "approved")
        self.assertEqual(self.get("summary").json()["totals"]["XAF"]["committed"], "60000.00")
        self.assertEqual([x["action"] for x in self.get("expenses/"+expense["id"]).json()["decisions"]],
                         ["submitted", "approved"])

    def test_workflow_rejection_requires_reason_and_new_revision(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        sent = self.submit_expense(expense)
        self.login("direction")
        bad = self.post("expenses/"+expense["id"]+"/reject", {
            "revision": sent["revision"], "reason": "Non",
        })
        self.assertEqual(bad.status_code, 422, bad.content)
        refused = self.post("expenses/"+expense["id"]+"/reject", {
            "revision": sent["revision"], "reason": "Facture à compléter avant achat",
        })
        self.assertEqual(refused.status_code, 200, refused.content)
        self.assertEqual(refused.json()["status"], "rejected")
        self.assertEqual(self.get("summary").json()["totals"]["XAF"]["committed"], "0.00")
        self.login("comptabilite")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/submit", {
            "revision": refused.json()["revision"],
        }).status_code, 409)
        edited = self.patch("expenses/"+expense["id"], {
            "revision": refused.json()["revision"], "invoice_reference": "FACTURE-REV-02",
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(edited.json()["workflow_state"], "draft")
        sent2 = self.submit_expense(edited.json())
        self.login("direction")
        grant = self.post("expenses/"+expense["id"]+"/approve", {"revision": sent2["revision"]})
        self.assertEqual(grant.status_code, 200, grant.content)
        steps = self.get("expenses/"+expense["id"]).json()["decisions"]
        self.assertEqual([x["action"] for x in steps],
                         ["submitted", "rejected", "revised", "submitted", "approved"])
        self.assertEqual(steps[1]["reason"], "Facture à compléter avant achat")
        self.assertEqual(OperatingExpensePayment.objects.count(), 0)

    def test_workflow_isolation_permissions_and_stale_revisions(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        self.login(self.outsider)
        self.assertEqual(self.post("expenses/"+expense["id"]+"/submit", {
            "revision": expense["revision"],
        }).status_code, 404)
        self.assertEqual(self.post("expenses/"+expense["id"]+"/reject", {
            "revision": expense["revision"], "reason": "Refus depuis une autre école",
        }).status_code, 404)
        self.login("secretariat")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/submit", {
            "revision": expense["revision"],
        }).status_code, 403)
        sent = self.submit_expense(expense)
        self.assertEqual(self.post("expenses/"+expense["id"]+"/submit", {
            "revision": sent["revision"],
        }).status_code, 409)
        self.assertEqual(self.patch("expenses/"+expense["id"], {
            "revision": sent["revision"], "amount": "1000.00",
        }).status_code, 409)
        self.assertEqual(self.post("expenses/"+expense["id"]+"/reject", {
            "revision": sent["revision"], "reason": "Refus par son propre compte",
        }).status_code, 403)
        self.login("direction")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/reject", {
            "revision": sent["revision"] - 1, "reason": "Version trop ancienne pour refus",
        }).status_code, 409)
        self.assertEqual(OperatingExpenseDecision.objects.filter(school=self.school).count(), 1)

    def test_expense_queue_counts_filters_and_pagination_are_exhaustive(self):
        supplier, budget = self.approved_budget()
        draft = self.expense(budget["id"], supplier["id"], "10000.00", "F-QUE-01")
        submitted = self.expense(budget["id"], supplier["id"], "10000.00", "F-QUE-02")
        approved = self.expense(budget["id"], supplier["id"], "10000.00", "F-QUE-03")
        self.submit_expense(submitted)
        self.approve_expense(approved)
        result = self.get("expenses", {"limit":"1", "offset":"0"})
        self.assertEqual(result.status_code, 200, result.content)
        data = result.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["expenses"]), 1)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["workflow_counts"]["draft"], 1)
        self.assertEqual(data["workflow_counts"]["submitted"], 1)
        self.assertEqual(data["workflow_counts"]["approved"], 1)
        page2 = self.get("expenses", {"limit":"1", "offset":"1"}).json()
        self.assertEqual(page2["total"], 3)
        self.assertTrue(page2["has_more"])
        page3 = self.get("expenses", {"limit":"1", "offset":"2"}).json()
        self.assertFalse(page3["has_more"])
        seen = {
            data["expenses"][0]["id"],page2["expenses"][0]["id"],page3["expenses"][0]["id"],
        }
        self.assertEqual(seen, {draft["id"], submitted["id"], approved["id"]})
        awaiting = self.get("expenses", {"workflow_state":"submitted", "limit":"50"}).json()
        self.assertEqual(awaiting["total"], 1)
        self.assertEqual(awaiting["expenses"][0]["id"], submitted["id"])
        # Counts refer to all states before applying the selected state filter.
        self.assertEqual(awaiting["workflow_counts"]["approved"], 1)
        for params in ({"limit":"0"}, {"limit":"101"}, {"offset":"-1"},
                       {"offset":"n/a"}, {"workflow_state":"paid"}):
            with self.subTest(params=params):
                self.assertEqual(self.get("expenses", params).status_code, 422)
        self.login("enseignant")
        self.assertEqual(self.get("expenses", {"workflow_state":"submitted"}).status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.get("expenses", {"workflow_state":"submitted"}).status_code, 404)

    def test_summary_includes_more_than_200_approved_budgets(self):
        """Les totaux des sorties ne doivent pas être tronqués par la liste affichée."""
        from django.utils import timezone

        approved_at = timezone.now()
        OperatingBudget.objects.bulk_create([
            OperatingBudget(
                school=self.school, year=self.year, category=f"Catégorie {index:03d}",
                currency="XAF", ceiling="1000.00",
                proposed_by=self.users["comptabilite"],
                approved_by=self.users["direction"], approved_at=approved_at,
            )
            for index in range(205)
        ])
        result = self.get("summary")
        self.assertEqual(result.status_code, 200, result.content)
        payload = result.json()
        self.assertEqual(len(payload["budgets"]), 205)
        self.assertEqual(payload["totals"]["XAF"]["ceiling"], "205000.00")
        self.assertEqual(payload["totals"]["XAF"]["committed"], "0.00")
        self.assertEqual(payload["totals"]["XAF"]["paid"], "0.00")
        self.assertEqual(payload["totals"]["XAF"]["remaining"], "205000.00")

    def test_activity_pole_required_and_invalid_values_rejected(self):
        supplier, budget = self.approved_budget()
        payload = {
            "budget": budget["id"], "supplier": supplier["id"],
            "category_ref": str(self.category.pk),
            "amount": "10000.00", "label": "Consommables",
            "invoice_reference": "FAC-POLE-001", "expense_on": "2026-11-10",
        }
        self.assertEqual(self.post("expenses", payload).status_code, 422)
        self.assertEqual(self.post("expenses", {**payload, "activity_pole": "recette"}).status_code, 422)
        self.assertEqual(self.post("expenses", {**payload, "activity_pole": "unclassified"}).status_code, 422)
        self.assertEqual(OperatingExpense.objects.count(), 0)

    def test_poles_independent_of_budget_category_and_payment_aggregation(self):
        supplier, budget = self.approved_budget()
        school = self.expense(budget["id"], supplier["id"], "40000.00", "FAC-S-001", pole="school")
        extra = self.expense(budget["id"], supplier["id"], "30000.00", "FAC-E-001", pole="extraschool")
        self.assertEqual(school["activity_pole"], "school")
        self.assertEqual(extra["activity_pole"], "extraschool")
        self.approve_expense(school)
        self.approve_expense(extra)
        self.login("econome")
        self.assertEqual(self.pay(school["id"], "10000.00").status_code, 201)
        self.assertEqual(self.pay(school["id"], "5000.00").status_code, 201)
        self.assertEqual(self.pay(extra["id"], "20000.00").status_code, 201)
        self.login("comptabilite")
        report = self.get("summary").json()
        self.assertEqual(report["by_activity_pole"]["XAF"]["school"], {
            "committed": "40000.00", "paid": "15000.00", "unpaid": "25000.00",
        })
        self.assertEqual(report["by_activity_pole"]["XAF"]["extraschool"], {
            "committed": "30000.00", "paid": "20000.00", "unpaid": "10000.00",
        })
        self.assertEqual(report["totals"]["XAF"]["committed"], "70000.00")
        self.assertEqual(report["totals"]["XAF"]["paid"], "35000.00")
        filtered = self.get("expenses", {"activity_pole": "school"}).json()
        self.assertEqual([row["id"] for row in filtered["expenses"]], [school["id"]])
        self.assertEqual(self.get("expenses", {"activity_pole": "recettes"}).status_code, 422)

    def test_legacy_unclassified_draft_can_be_classified_before_approval(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"], pole="school")
        # Simulates an existing pre-B2 draft migrated to "unclassified".
        OperatingExpense.objects.filter(pk=expense["id"]).update(activity_pole="unclassified")
        self.login("direction")
        refused = self.post("expenses/" + expense["id"] + "/approve", {"revision": expense["revision"]})
        self.assertEqual(refused.status_code, 409, refused.content)
        self.login("comptabilite")
        updated = self.patch("expenses/" + expense["id"], {
            "revision": expense["revision"], "activity_pole": "common",
            "cost_center": "Administration", "accounting_nature": "Entretien",
        })
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["activity_pole"], "common")
        self.assertEqual(updated.json()["cost_center"], "Administration")
        self.assertEqual(updated.json()["accounting_nature"], "Entretien")
        submitted = self.submit_expense(updated.json())
        self.login("direction")
        approved = self.post("expenses/" + expense["id"] + "/approve", {
            "revision": submitted["revision"],
        })
        self.assertEqual(approved.status_code, 200, approved.content)

    def test_historical_approved_expenses_remain_visible_without_forced_allocation(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"], "25000.00")
        self.approve_expense(expense)
        # Existing approved transactions may have no defensible historical pole.
        OperatingExpense.objects.filter(pk=expense["id"]).update(activity_pole="unclassified")
        report = self.get("summary").json()
        self.assertEqual(report["by_activity_pole"]["XAF"]["unclassified"]["committed"], "25000.00")
        self.assertEqual(report["by_activity_pole"]["XAF"]["unclassified"]["paid"], "0.00")

    def test_catalog_is_school_owned_and_requires_permissions(self):
        created = self.post("categories", {"code": "transport", "name": "Transport",
                                            "suggested_pole": "extraschool"})
        self.assertEqual(created.status_code, 201, created.content)
        root = created.json()
        child = self.post("categories", {"code": "carburant", "name": "Carburant",
                                         "parent": root["id"]})
        self.assertEqual(child.status_code, 201, child.content)
        self.assertEqual(child.json()["parent"], root["id"])
        self.assertEqual(len(self.get("categories").json()["categories"]), 4)
        duplicate = self.post("categories", {"code": "transport", "name": "Autre"})
        self.assertIn(duplicate.status_code, [409, 422])
        self.assertEqual(self.post("categories", {"code": "nested", "name": "Troisième niveau",
                            "parent": child.json()["id"]}).status_code, 409)
        foreign = OperatingExpenseCategory.objects.create(
            school=self.other, code="foreign", name="Autre école",
        )
        self.assertEqual(self.post("categories", {"code": "probe", "name": "Hors école",
                            "parent": str(foreign.pk)}).status_code, 404)
        self.login("secretariat")
        self.assertEqual(self.get("categories").status_code, 403)
        self.assertEqual(self.post("categories", {}).status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.get("categories").status_code, 404)

    def test_snapshot_survives_category_rename_and_archive(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        self.assertEqual(expense["expense_category"], "Matériel")
        self.assertEqual(expense["expense_subcategory"], "Laboratoire")
        revised = self.patch_category(self.category, {"name": "Équipements éducatifs"})
        self.assertEqual(revised.status_code, 200, revised.content)
        subrevised = self.patch_category(self.subcategory, {"name": "Sciences"})
        self.assertEqual(subrevised.status_code, 200, subrevised.content)
        previous = self.get("expenses/"+expense["id"]).json()["expense"]
        self.assertEqual(previous["expense_category"], "Matériel")
        self.assertEqual(previous["expense_subcategory"], "Laboratoire")
        self.assertEqual(self.patch_category(self.category, {"active": False}).status_code, 409)
        self.assertEqual(self.patch_category(self.subcategory, {"active": False}).status_code, 200)
        self.assertEqual(self.patch_category(self.category, {"active": False}).status_code, 200)
        self.assertEqual(self.post("expenses", {
            "budget": budget["id"], "supplier": supplier["id"],
            "category_ref": str(self.category.pk), "activity_pole": "school",
            "amount": "3000.00", "label": "Autre matériel",
            "invoice_reference": "FAC-ARCHIVE", "expense_on": "2026-11-10",
        }).status_code, 422)
        self.assertEqual(self.get("expenses/"+expense["id"]).json()["expense"]["expense_category"], "Matériel")

    def test_legacy_draft_without_catalog_can_be_reclassified(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        OperatingExpense.objects.filter(pk=expense["id"]).update(
            category_ref=None, subcategory_ref=None,
            category_label_snapshot="", subcategory_label_snapshot="",
        )
        self.login("direction")
        refused = self.post("expenses/"+expense["id"]+"/approve", {"revision": expense["revision"]})
        self.assertEqual(refused.status_code, 409, refused.content)
        self.login("comptabilite")
        updated = self.patch("expenses/"+expense["id"], {
            "revision": expense["revision"], "category_ref": str(self.category.pk),
            "subcategory_ref": str(self.subcategory.pk),
        })
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["expense_category"], "Matériel")
        submitted = self.submit_expense(updated.json())
        self.login("direction")
        approved = self.post("expenses/"+expense["id"]+"/approve", {
            "revision": submitted["revision"],
        })
        self.assertEqual(approved.status_code, 200, approved.content)

    def patch_category(self, category, data):
        category.refresh_from_db()
        return self.patch("categories/"+str(category.pk), {"revision": category.revision, **data})

    def test_non_supplier_government_expense_uses_existing_budget_and_controls(self):
        supplier, budget = self.approved_budget()
        before = OperatingSupplier.objects.filter(school=self.school).count()
        response = self.post("expenses", {
            "budget": budget["id"], "activity_pole": "common",
            "category_ref": str(self.category.pk),
            "beneficiary_type": "government",
            "beneficiary_name": "Administration fiscale TEST",
            "beneficiary_reference": "DOSSIER-INTERNE-TEST",
            "label": "Frais administratifs fictifs", "amount": "15000.00",
            "invoice_reference": "JUST-ADM-01", "expense_on": "2026-11-10",
        })
        self.assertEqual(response.status_code, 201, response.content)
        expense = response.json()
        self.assertIsNone(expense["supplier"])
        self.assertEqual(expense["supplier_name"], "")
        self.assertEqual(expense["beneficiary_type"], "government")
        self.assertEqual(expense["beneficiary_name"], "Administration fiscale TEST")
        self.assertEqual(OperatingSupplier.objects.filter(school=self.school).count(), before)
        submitted = self.submit_expense(expense)
        self.login("direction")
        approved = self.post("expenses/"+expense["id"]+"/approve", {"revision": submitted["revision"]})
        self.assertEqual(approved.status_code, 200, approved.content)
        self.login("econome")
        paid = self.pay(expense["id"], "5000.00")
        self.assertEqual(paid.status_code, 201, paid.content)
        self.login("comptabilite")
        report = self.get("summary").json()
        self.assertEqual(report["totals"]["XAF"]["committed"], "15000.00")
        self.assertEqual(report["totals"]["XAF"]["paid"], "5000.00")
        self.assertEqual(report["by_activity_pole"]["XAF"]["common"]["unpaid"], "10000.00")
        self.assertEqual(self.get("expenses/"+expense["id"]).json()["expense"]["beneficiary_name"],
                         "Administration fiscale TEST")

    def test_beneficiary_validation_and_school_isolation(self):
        supplier, budget = self.approved_budget()
        base = {
            "budget": budget["id"], "activity_pole": "common",
            "category_ref": str(self.category.pk),
            "label": "Paiement fictif", "amount": "8000.00",
            "invoice_reference": "JUST-02", "expense_on": "2026-11-10",
        }
        cases = [
            {**base, "beneficiary_type": "supplier"},
            {**base, "beneficiary_type": "government"},
            {**base, "beneficiary_type": "staff", "beneficiary_name": " "},
            {**base, "beneficiary_type": "unknown", "beneficiary_name": "Un nom"},
            {**base, "beneficiary_type": "government", "beneficiary_name": "Trésor",
             "supplier": supplier["id"]},
            {**base, "beneficiary_type": "supplier", "supplier": supplier["id"],
             "beneficiary_name": "Faux nom fournisseur"},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.post("expenses", case).status_code, 422)
        foreign = OperatingSupplier.objects.create(school=self.other, name="Fournisseur étranger")
        invalid = self.post("expenses", {
            **base, "beneficiary_type": "supplier", "supplier": str(foreign.pk),
        })
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(OperatingExpense.objects.count(), 0)
        self.login("secretariat")
        self.assertEqual(self.post("expenses", {
            **base, "beneficiary_type": "individual", "beneficiary_name": "TEST",
        }).status_code, 403)

    def test_draft_beneficiary_switch_preserves_original_audit_and_approved_lock(self):
        supplier, budget = self.approved_budget()
        expense = self.expense(budget["id"], supplier["id"])
        self.assertEqual(expense["beneficiary_type"], "supplier")
        self.assertEqual(expense["beneficiary_name"], "Fournitures Gabon TEST")
        switched = self.patch("expenses/"+expense["id"], {
            "revision": expense["revision"],
            "beneficiary_type": "staff", "beneficiary_name": "Employé TEST",
            "beneficiary_reference": "REF-HORS-PAIE",
        })
        self.assertEqual(switched.status_code, 200, switched.content)
        changed = switched.json()
        self.assertIsNone(changed["supplier"])
        self.assertEqual(changed["beneficiary_type"], "staff")
        self.assertEqual(changed["beneficiary_name"], "Employé TEST")
        self.assertEqual(self.patch("expenses/"+expense["id"], {
            "revision": expense["revision"], "beneficiary_name": "Modif obsolète",
        }).status_code, 409)
        submitted = self.submit_expense(changed)
        self.login("direction")
        self.assertEqual(self.post("expenses/"+expense["id"]+"/approve", {
            "revision": submitted["revision"],
        }).status_code, 200)
        self.login("comptabilite")
        self.assertEqual(self.patch("expenses/"+expense["id"], {
            "revision": changed["revision"]+1, "beneficiary_name": "Tentative rétroactive",
        }).status_code, 409)
        self.assertEqual(self.get("expenses/"+expense["id"]).json()["expense"]["beneficiary_name"],
                         "Employé TEST")
        self.assertEqual(OperatingSupplier.objects.filter(school=self.school).count(), 1)

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
        submitted_second = self.submit_expense(second)
        self.login("direction")
        rejected = self.post("expenses/"+second["id"]+"/approve", {"revision": submitted_second["revision"]})
        self.assertEqual(rejected.status_code, 409, rejected.content)
        self.assertFalse(OperatingExpense.objects.get(pk=second["id"]).approved_at)
        refused = self.post("expenses/"+second["id"]+"/reject", {
            "revision": submitted_second["revision"], "reason": "Budget insuffisant, demande à corriger",
        })
        self.assertEqual(refused.status_code, 200, refused.content)
        self.login("comptabilite")
        edited = self.patch("expenses/"+second["id"], {
            "revision": refused.json()["revision"], "amount": "25000.00",
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(self.patch("expenses/"+second["id"], {
            "revision": refused.json()["revision"], "amount": "12000.00",
        }).status_code, 409)
        second_submitted = self.submit_expense(edited.json())
        self.login("direction")
        approval = self.post("expenses/"+second["id"]+"/approve", {
            "revision": second_submitted["revision"],
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

    def test_default_catalog_preview_is_read_only_and_full_import_idempotent(self):
        preview = self.get("catalog-defaults")
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["total_families"], 20)
        self.assertEqual(preview.json()["total_subcategories"], 211)
        self.assertEqual(OperatingExpenseCategory.objects.filter(school=self.school).count(), 2)

        chosen = ["b%02d" % n for n in range(1, 21)]
        installed = self.post("catalog-defaults", {
            "families": chosen, "include_subcategories": True,
        })
        self.assertEqual(installed.status_code, 200, installed.content)
        self.assertEqual(installed.json()["created_families"], 20)
        self.assertEqual(installed.json()["created_subcategories"], 211)
        self.assertEqual(
            OperatingExpenseCategory.objects.filter(school=self.school).count(), 233,
        )
        self.assertFalse(OperatingExpenseCategory.objects.filter(school=self.other).exists())
        again = self.post("catalog-defaults", {
            "families": chosen, "include_subcategories": True,
        })
        self.assertEqual(again.status_code, 200, again.content)
        self.assertTrue(again.json()["idempotent"])
        self.assertEqual(OperatingExpenseCategory.objects.filter(school=self.school).count(), 233)

    def test_default_catalog_preserves_customized_names_and_archives(self):
        selected = {"families": ["b07"], "include_subcategories": True}
        self.assertEqual(self.post("catalog-defaults", selected).status_code, 200)
        root = OperatingExpenseCategory.objects.get(school=self.school, code="b07")
        self.assertEqual(root.name, "Matériel pédagogique")
        root.name = "Équipements de formation personnalisés"
        root.save(update_fields=["name"])
        child = OperatingExpenseCategory.objects.filter(school=self.school, parent=root).first()
        child.active = False
        child.save(update_fields=["active"])
        again = self.post("catalog-defaults", selected)
        self.assertEqual(again.status_code, 200, again.content)
        self.assertTrue(again.json()["idempotent"])
        root.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(root.name, "Équipements de formation personnalisés")
        self.assertFalse(child.active)
        self.assertEqual(OperatingExpenseCategory.objects.filter(school=self.school, parent=root).count(), 10)

    def test_default_catalog_refuses_conflicts_without_partial_write(self):
        OperatingExpenseCategory.objects.create(
            school=self.school, parent=self.category,
            code="b08", name="Ancien sous-catalogue personnalisé",
        )
        response = self.post("catalog-defaults", {
            "families": ["b07", "b08"], "include_subcategories": True,
        })
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(OperatingExpenseCategory.objects.filter(school=self.school, code="b07").exists())
        self.assertFalse(OperatingExpenseCategory.objects.filter(school=self.school, code__startswith="b07_").exists())

    def test_default_catalog_is_permissioned_and_selection_is_validated(self):
        initial = OperatingExpenseCategory.objects.filter(school=self.school).count()
        for bad in ([], ["b00"], ["b07", "b07"], "b07", [1]):
            self.assertEqual(self.post("catalog-defaults", {"families": bad}).status_code, 422)
        self.assertEqual(self.post("catalog-defaults", {
            "families": ["b07"], "include_subcategories": "true",
        }).status_code, 422)
        self.assertEqual(OperatingExpenseCategory.objects.filter(school=self.school).count(), initial)
        self.login("direction")
        self.assertEqual(self.get("catalog-defaults").status_code, 200)
        self.assertEqual(self.post("catalog-defaults", {"families": ["b07"]}).status_code, 403)
        self.login("enseignant")
        self.assertEqual(self.get("catalog-defaults").status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.client.get(
            "/api/v1/schools/"+str(self.school.pk)+"/operating/catalog-defaults",
        ).status_code, 404)

    def test_b2_poles_are_virtual_editable_and_versioned(self):
        self.assertEqual(OperatingClassificationOption.objects.count(), 0)
        payload = self.get("classification").json()
        self.assertEqual(len(payload["poles"]), 5)
        self.assertEqual(payload["centers"], [])
        self.assertEqual(OperatingClassificationOption.objects.count(), 0)
        modified = self.patch("classification/poles/school", {
            "revision": 0, "label": "Enseignement personnalisé",
        })
        self.assertEqual(modified.status_code, 200, modified.content)
        self.assertEqual(modified.json()["revision"], 1)
        self.assertEqual(self.patch("classification/poles/school", {
            "revision": 0, "label": "Concurrent",
        }).status_code, 409)
        self.assertEqual(self.get("classification").json()["poles"][0]["label"], "Enseignement personnalisé")
        self.assertFalse(OperatingClassificationOption.objects.filter(school=self.other).exists())

    def test_b2_cost_center_and_nature_preserve_historical_labels(self):
        center = self.post("classification", {
            "kind": "cost_center", "code": "college", "name": "Collège",
            "activity_pole": "school",
        })
        self.assertEqual(center.status_code, 201, center.content)
        nature = self.post("classification", {
            "kind": "accounting_nature", "code": "entretien",
            "name": "Charge d'entretien",
        })
        self.assertEqual(nature.status_code, 201, nature.content)
        supplier, budget = self.approved_budget()
        payload = {"budget": budget["id"], "supplier": supplier["id"],
            "category_ref": str(self.category.pk), "activity_pole": "school",
            "cost_center_ref": center.json()["id"],
            "accounting_nature_ref": nature.json()["id"],
            "amount": "12000.00", "label": "Achat local",
            "invoice_reference": "DEVIS-123", "expense_on": "2026-11-10"}
        expense = self.post("expenses", payload)
        self.assertEqual(expense.status_code, 201, expense.content)
        self.assertEqual(expense.json()["cost_center"], "Collège")
        self.assertEqual(expense.json()["accounting_nature"], "Charge d'entretien")
        self.assertEqual(expense.json()["activity_pole_label"], "Scolarité")
        edited = self.patch("classification/"+center.json()["id"], {
            "revision": 1, "name": "École secondaire",
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(
            self.get("expenses/"+expense.json()["id"]).json()["expense"]["cost_center"], "Collège"
        )
        self.assertEqual(self.patch("classification/"+center.json()["id"], {
            "revision": 2, "activity_pole": "extraschool",
        }).status_code, 409)
        foreign = OperatingClassificationOption.objects.create(
            school=self.other, kind="cost_center", code="foreign", name="Autre",
        )
        payload["cost_center_ref"] = str(foreign.pk)
        self.assertEqual(self.post("expenses", payload).status_code, 404)
        payload["cost_center_ref"] = center.json()["id"]
        payload["activity_pole"] = "extraschool"
        self.assertEqual(self.post("expenses", payload).status_code, 422)

    def test_b2_archived_classification_blocks_new_requests_not_history(self):
        center = self.post("classification", {
            "kind": "cost_center", "code": "cantine", "name": "Cantine",
            "activity_pole": "school",
        }).json()
        supplier, budget = self.approved_budget()
        payload = {"budget": budget["id"], "supplier": supplier["id"],
            "category_ref": str(self.category.pk), "activity_pole": "school",
            "cost_center_ref": center["id"], "amount": "1200.00",
            "label": "Approvisionnement", "invoice_reference": "DEVIS-124",
            "expense_on": "2026-11-10"}
        expense = self.post("expenses", payload)
        self.assertEqual(expense.status_code, 201, expense.content)
        archived = self.patch("classification/"+center["id"], {
            "revision": center["revision"], "active": False,
        })
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertEqual(self.post("expenses", payload).status_code, 422)
        self.assertEqual(self.post("expenses/"+expense.json()["id"]+"/submit", {
            "revision": expense.json()["revision"],
        }).status_code, 422)
        self.assertEqual(
            self.get("expenses/"+expense.json()["id"]).json()["expense"]["cost_center"], "Cantine"
        )

    def test_b2_classification_permissions_and_shape_validation(self):
        self.assertEqual(self.post("classification", {
            "kind": "accounting_nature", "code": "nature", "name": "Nature",
            "activity_pole": "school",
        }).status_code, 422)
        self.assertEqual(self.post("classification", {
            "kind": "pole", "code": "school", "name": "Faux axe",
        }).status_code, 422)
        self.login("direction")
        self.assertEqual(self.get("classification").status_code, 200)
        self.assertEqual(self.post("classification", {
            "kind": "cost_center", "code": "forbidden", "name": "Interdit",
        }).status_code, 403)
        self.login("enseignant")
        self.assertEqual(self.get("classification").status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.client.get(
            "/api/v1/schools/"+str(self.school.pk)+"/operating/classification",
        ).status_code, 404)


"""B3 acceptance: school staff requests are not approved budget expenses."""
import json
import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicYear
from .models import Organization, School, SchoolRole, SchoolMember
from .operating_models import OperatingExpenseCategory, OperatingExpense, OperatingBudget
from .operating_request_models import OperatingSchoolRequest, OperatingSchoolRequestEvent
from .services import ROLE_TEMPLATES


class SchoolExpenseRequestTests(TestCase):
    def setUp(self):
        User = get_user_model()
        org = Organization.objects.create(name="B3 établissement fictif")
        self.school = School.objects.create(
            organization=org, name="Lycée démonstration B3",
            school_type="lycee_general", education_cycles=["lycee_general"],
        )
        self.other = School.objects.create(
            organization=org, name="Autre lycée B3",
            school_type="lycee_general", education_cycles=["lycee_general"],
        )
        for school in (self.school, self.other):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(
                    school=school, code=code, label=label, permissions=list(permissions),
                )
        self.accounts = {}
        for code in ("enseignant", "secretariat", "direction", "comptabilite", "parent"):
            user = User.objects.create_user(
                username="req-b3-" + code, password="Yem-test-school-request-2026!",
            )
            self.accounts[code] = user
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=code),
            )
        self.other_teacher = User.objects.create_user(
            username="req-b3-other-teacher", password="Yem-test-school-request-2026!",
        )
        SchoolMember.objects.create(
            school=self.school, user=self.other_teacher,
            role=SchoolRole.objects.get(school=self.school, code="enseignant"),
        )
        self.external = User.objects.create_user(
            username="req-b3-foreign", password="Yem-test-school-request-2026!",
        )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
            status="current",
        )
        self.foreign_year = AcademicYear.objects.create(
            school=self.other, code="2026-2027", name="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
            status="current",
        )
        self.root = OperatingExpenseCategory.objects.create(
            school=self.school, code="b07", name="Matériel pédagogique",
            suggested_pole="school",
        )
        self.child = OperatingExpenseCategory.objects.create(
            school=self.school, parent=self.root, code="b07_manuels", name="Manuels",
        )
        self.foreign_root = OperatingExpenseCategory.objects.create(
            school=self.other, code="b07", name="Matériel pédagogique",
        )
        self.client = Client(enforce_csrf_checks=True)
        self.base = "/api/v1/schools/" + str(self.school.pk) + "/operating/"
        self.login("enseignant")

    def login(self, role):
        user = self.accounts.get(role, role) if isinstance(role, str) else role
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def get(self, tail, params=None):
        return self.client.get(self.base + tail, params or {})

    def post(self, tail, payload):
        return self.client.post(
            self.base + tail, json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def patch(self, tail, payload):
        return self.client.patch(
            self.base + tail, json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def payload(self, **overrides):
        return {
            "year": str(self.year.pk), "service": "Pédagogie",
            "reason": "Manuels nécessaires au cours de mathématiques",
            "description": "Manuels scolaires de terminale",
            "category": str(self.root.pk), "subcategory": str(self.child.pk),
            "quantity": "2.00", "estimated_unit_price": "6000.00",
            "estimated_amount": "12000.00", "currency": "XAF",
            "beneficiary_name": "Librairie pressentie",
            "urgency": "high", "desired_on": "2026-12-02",
            "supporting_reference": "DEVIS-TEST-B3-001",
            "idempotency_key": str(uuid.uuid4()),
            **overrides,
        }

    def created(self, **overrides):
        r = self.post("school-requests", self.payload(**overrides))
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_teacher_submits_school_request_without_access_to_budget(self):
        row = self.created()
        self.assertEqual(row["status"], "draft")
        self.assertEqual(row["requester"], str(self.accounts["enseignant"].pk))
        self.assertEqual(row["requester_function"], "Enseignant")
        self.assertEqual(row["urgency"], "high")
        self.assertEqual(row["quantity"], "2.00")
        self.assertEqual(row["estimated_amount"], "12000.00")
        self.assertFalse(row["budget_committed"])
        self.assertFalse(row["money_transferred"])
        self.assertEqual(self.get("budgets").status_code, 403)
        self.assertEqual(self.get("expenses").status_code, 403)
        self.assertFalse(OperatingBudget.objects.exists())
        self.assertFalse(OperatingExpense.objects.exists())
        res = self.post("school-requests/"+row["id"]+"/submit", {
            "revision": row["revision"],
        })
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["status"], "submitted")
        self.assertEqual(OperatingSchoolRequestEvent.objects.count(), 1)

    def test_administrative_staff_can_request_without_finance_power(self):
        self.login("secretariat")
        row = self.created(
            service="Secrétariat", description="Papier pour examens",
            reason="Impression des convocations",
        )
        self.assertEqual(row["requester_function"], "Secrétariat")
        self.assertEqual(self.get("budgets").status_code, 403)

    def test_custom_school_role_can_request_without_approving(self):
        User = get_user_model()
        custom = User.objects.create_user(
            username="req-b3-custom", password="Yem-test-school-request-2026!",
        )
        role = SchoolRole.objects.create(
            school=self.school, code="agent_labo", label="Responsable laboratoire",
            permissions=["school.view", "school.operating.request"],
        )
        SchoolMember.objects.create(school=self.school, user=custom, role=role)
        self.login(custom)
        created = self.created(service="Laboratoire")
        self.assertEqual(created["requester_function"], "Responsable laboratoire")
        self.assertEqual(self.post("school-requests/"+created["id"]+"/review", {
            "revision": created["revision"], "decision": "approved",
        }).status_code, 403)

    def test_independent_review_does_not_book_financial_commitment(self):
        row = self.created()
        submitted = self.post("school-requests/"+row["id"]+"/submit", {
            "revision": row["revision"],
        }).json()
        teacher_role = SchoolRole.objects.get(school=self.school, code="enseignant")
        teacher_role.permissions = list(teacher_role.permissions) + ["school.operating.approve"]
        teacher_role.save(update_fields=["permissions"])
        self.assertEqual(self.post("school-requests/"+row["id"]+"/review", {
            "revision": submitted["revision"], "decision": "in_review",
        }).status_code, 403)
        self.login("direction")
        in_review = self.post("school-requests/"+row["id"]+"/review", {
            "revision": submitted["revision"], "decision": "in_review",
        })
        self.assertEqual(in_review.status_code, 200, in_review.content)
        approved = self.post("school-requests/"+row["id"]+"/review", {
            "revision": in_review.json()["revision"], "decision": "approved",
        })
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(approved.json()["status"], "approved")
        self.assertEqual(approved.json()["budget_committed"], False)
        self.assertEqual(OperatingExpense.objects.count(), 0)
        self.assertEqual(OperatingBudget.objects.count(), 0)
        self.assertEqual(OperatingSchoolRequestEvent.objects.count(), 3)
        self.assertEqual(self.post("school-requests/"+row["id"]+"/review", {
            "revision": in_review.json()["revision"], "decision": "approved",
        }).status_code, 409)

    def test_reject_and_personal_revision_are_audited(self):
        row = self.created()
        submitted = self.post("school-requests/"+row["id"]+"/submit", {
            "revision": row["revision"],
        }).json()
        self.login("direction")
        refused = self.post("school-requests/"+row["id"]+"/review", {
            "revision": submitted["revision"], "decision": "rejected",
            "reason": "Justificatif trop imprécis pour autoriser le besoin",
        })
        self.assertEqual(refused.status_code, 200, refused.content)
        self.assertEqual(refused.json()["status"], "rejected")
        self.login("enseignant")
        edited = self.patch("school-requests/"+row["id"], {
            "revision": refused.json()["revision"],
            "reason": "Devis de manuels du second trimestre maintenant joint",
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(edited.json()["status"], "draft")
        history = self.get("school-requests/"+row["id"]).json()["history"]
        self.assertEqual([e["action"] for e in history], [
            "submitted", "rejected", "revised"
        ])

    def test_no_other_staff_member_can_read_or_modify_my_requests(self):
        row = self.created()
        self.login(self.other_teacher)
        self.assertEqual(self.get("school-requests").json()["total"], 0)
        self.assertEqual(self.get("school-requests/"+row["id"]).status_code, 404)
        self.assertEqual(self.patch("school-requests/"+row["id"], {
            "revision": row["revision"], "reason": "Modification hostile",
        }).status_code, 404)
        self.assertEqual(self.post("school-requests/"+row["id"]+"/submit", {
            "revision": row["revision"],
        }).status_code, 404)
        self.login("direction")
        self.assertEqual(self.get("school-requests").json()["total"], 1)
        self.assertEqual(self.get("school-requests", {"mine":"1"}).json()["total"], 0)

    def test_invalid_price_quantity_school_and_closed_year_rejected(self):
        self.assertEqual(self.post("school-requests", self.payload(
            quantity="0", estimated_unit_price=None,
        )).status_code, 422)
        self.assertEqual(self.post("school-requests", self.payload(
            estimated_amount="15000.00",
        )).status_code, 422)
        self.assertEqual(self.post("school-requests", self.payload(
            category=str(self.foreign_root.pk),
        )).status_code, 404)
        self.assertEqual(self.post("school-requests", self.payload(
            year=str(self.foreign_year.pk),
        )).status_code, 404)
        self.assertEqual(self.post("school-requests", self.payload(
            requester=str(self.accounts["direction"].pk),
        )).status_code, 422)
        self.year.status = "closed"
        self.year.save(update_fields=["status"])
        self.assertEqual(self.post("school-requests", self.payload()).status_code, 422)
        self.assertEqual(OperatingSchoolRequest.objects.count(), 0)

    def test_idempotency_prevents_duplicate_submission_and_pole_separation(self):
        data = self.payload(urgency="critical")
        first = self.post("school-requests", data)
        self.assertEqual(first.status_code, 201, first.content)
        second = self.post("school-requests", data)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(second.json()["idempotent"])
        self.assertEqual(OperatingSchoolRequest.objects.count(), 1)
        self.assertEqual(OperatingSchoolRequest.objects.first().category.school_id, self.school.pk)
        self.login("parent")
        self.assertEqual(self.get("school-requests").status_code, 403)
        self.assertEqual(self.post("school-requests", self.payload()).status_code, 403)
        self.login(self.external)
        self.assertEqual(self.get("school-requests").status_code, 404)

    def test_cancel_does_not_generate_payment_or_delete_trace(self):
        row = self.created()
        cancelled = self.post("school-requests/"+row["id"]+"/cancel", {
            "revision": row["revision"],
        })
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertEqual(self.post("school-requests/"+row["id"]+"/submit", {
            "revision": cancelled.json()["revision"],
        }).status_code, 409)
        self.assertFalse(OperatingExpense.objects.exists())
        self.assertEqual(OperatingSchoolRequestEvent.objects.count(), 1)

"""Tariff support does not grant billing, receipt or gateway authority."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .finance_models import FeeCharge, FeeSchedule
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES


class PlatformTariffInterventionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("platform-tariff-test")
        self.director = User.objects.create_user("director-tariff-test")
        self.tarifier = User.objects.create_user("tarifier-tariff-test")
        org = Organization.objects.create(name="Tariff support tests")
        self.school = School.objects.create(organization=org, name="School A")
        self.other = School.objects.create(organization=org, name="School B")
        for school in (self.school, self.other):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        SchoolMember.objects.create(school=self.school, user=self.director,
            role=SchoolRole.objects.get(school=self.school, code="direction"))
        SchoolMember.objects.create(school=self.school, user=self.tarifier,
            role=SchoolRole.objects.get(school=self.school, code="tarification"))
        self.year = AcademicYear.objects.create(school=self.school, code="2026-2027", name="2026-2027",
            start_date="2026-09-07", end_date="2027-07-10")
        cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        self.level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="1e", name="Première année")
        self.base = f"/api/v1/schools/{self.school.pk}/"
        self.client.force_login(self.admin)
        self.set_mfa(True)

    def set_mfa(self, verified):
        session = self.client.session
        session["mfa_verified"] = verified
        session.save()

    def open_school(self, school):
        return self.client.post(f"/api/v1/platform/schools/{school.pk}/admin-access")

    def post(self, path, data):
        return self.client.post(self.base + path, json.dumps(data), content_type="application/json")

    def test_configure_both_tariffs_without_billing_authority(self):
        self.assertEqual(self.client.get(self.base + "admission-fees").status_code, 404)
        self.assertEqual(self.open_school(self.school).status_code, 200)
        access = self.client.get(self.base + "my-access").json()
        self.assertTrue(access["platform_tariff_intervention"])
        self.assertNotIn("school.finance.manage", access["permissions"])
        self.assertNotIn("school.finance.receive", access["permissions"])
        self.assertEqual(self.client.get(self.base + "finance/schedules?choices=1").status_code, 200)
        fee = self.post("admission-fees", {"year": str(self.year.pk), "level": str(self.level.pk),
            "revision": 0, "amount_xaf": 15000, "active": True})
        self.assertEqual(fee.status_code, 200, fee.content)
        schedule = self.post("finance/schedules", {"year": str(self.year.pk), "classroom": None,
            "code": "scolarite-test", "label": "Scolarité", "amount": "25000", "currency": "XAF"})
        self.assertEqual(schedule.status_code, 201, schedule.content)
        path = self.base + "finance/schedules/" + schedule.json()["id"]
        modified = self.client.patch(path, json.dumps({"revision": 1, "amount": "26000"}),
                                     content_type="application/json")
        self.assertEqual(modified.status_code, 200, modified.content)
        self.assertEqual(self.post("finance/charges", {}).status_code, 403)
        self.assertEqual(self.post("finance/payments", {}).status_code, 403)
        self.assertEqual(self.post("admission-gateway", {}).status_code, 403)
        for event in ("platform_admin_school_access", "admission_fee_updated",
                      "fee_schedule_created", "fee_schedule_updated"):
            self.assertTrue(SchoolAudit.objects.filter(school=self.school, actor=self.admin, event=event).exists())

    def test_requires_current_mfa_and_school_context(self):
        self.assertEqual(self.open_school(self.school).status_code, 200)
        self.set_mfa(False)
        self.assertFalse(self.client.get(self.base + "my-access").json()["platform_tariff_intervention"])
        self.assertEqual(self.client.get(self.base + "admission-fees").status_code, 403)
        self.assertEqual(self.client.get(self.base + "finance/schedules?choices=1").status_code, 403)
        self.set_mfa(True)
        self.assertEqual(self.open_school(self.other).status_code, 200)
        self.assertFalse(self.client.get(self.base + "my-access").json()["platform_tariff_intervention"])
        self.assertEqual(self.client.get(self.base + "admission-fees").status_code, 403)

    def test_existing_school_roles_unchanged(self):
        self.client.force_login(self.director)
        self.assertFalse(self.client.get(self.base + "my-access").json()["platform_tariff_intervention"])
        self.assertEqual(self.client.get(self.base + "admission-fees").status_code, 403)
        self.assertEqual(self.client.get(self.base + "finance/schedules?choices=1").status_code, 403)
        self.client.force_login(self.tarifier)
        self.assertEqual(self.client.get(self.base + "admission-fees").status_code, 200)
        self.assertEqual(self.client.get(self.base + "finance/schedules?choices=1").status_code, 200)

    def monthly_payload(self):
        rooms = [AcademicClass.objects.create(school=self.school, year=self.year, level=self.level,
            code=code, name=code.upper()) for code in ("a", "b")]
        return {"year": str(self.year.pk), "classrooms": [str(room.pk) for room in rooms],
                "amount": "25000", "first_month": "2026-10", "last_month": "2027-02", "due_day": 31}

    def test_monthly_generation_is_atomic_and_idempotent(self):
        payload = self.monthly_payload()
        path = "finance/schedules/monthly"
        self.assertEqual(self.open_school(self.school).status_code, 200)
        first = self.post(path, payload)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["created"], 10)
        self.assertEqual(first.json()["due_dates"][-1], "2027-02-28")
        retry = self.post(path, payload)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(retry.json()["unchanged"], 10)
        self.assertEqual(FeeSchedule.objects.filter(school=self.school).count(), 10)
        changed = self.post(path, {**payload, "amount": "30000"})
        self.assertEqual(changed.status_code, 409, changed.content)
        self.assertEqual(FeeSchedule.objects.filter(school=self.school, amount=25000).count(), 10)
        self.assertFalse(FeeCharge.objects.filter(school=self.school).exists())
        self.assertTrue(SchoolAudit.objects.filter(school=self.school, actor=self.admin,
            event="monthly_fee_schedules_generated").exists())

    def test_monthly_generation_rejects_outside_year_or_duplicate_class(self):
        payload = self.monthly_payload()
        self.assertEqual(self.open_school(self.school).status_code, 200)
        path = "finance/schedules/monthly"
        self.assertEqual(self.post(path, {**payload, "first_month": "2026-08"}).status_code, 422)
        self.assertEqual(self.post(path, {**payload, "classrooms": payload["classrooms"] * 2}).status_code, 422)
        self.assertEqual(self.post(path, {**payload, "classrooms": [str(self.other.pk)]}).status_code, 422)
        self.assertFalse(FeeSchedule.objects.filter(school=self.school).exists())
        self.client.force_login(self.director)
        self.assertEqual(self.post(path, payload).status_code, 403)
        self.client.force_login(self.tarifier)
        self.assertEqual(self.post(path, payload).status_code, 201)

    def test_monthly_generation_rejects_overlap_with_existing_general_tariff(self):
        payload = self.monthly_payload()
        self.assertEqual(self.open_school(self.school).status_code, 200)
        self.assertEqual(self.post("finance/schedules", {"year": str(self.year.pk),
            "classroom": None, "code": "scolarite-octobre", "label": "Scolarité octobre",
            "amount": "25000", "currency": "XAF", "due_date": "2026-10-05"}).status_code, 201)
        self.assertEqual(self.post("finance/schedules/monthly", payload).status_code, 409)
        self.assertEqual(FeeSchedule.objects.filter(school=self.school).count(), 1)

    def test_change_deadline_rejects_outside_year_and_stale_revision(self):
        payload = self.monthly_payload()
        self.assertEqual(self.open_school(self.school).status_code, 200)
        self.assertEqual(self.post("finance/schedules/monthly", payload).status_code, 201)
        row = FeeSchedule.objects.filter(school=self.school).order_by("due_date").first()
        path = self.base + "finance/schedules/" + str(row.pk)
        def patch(data):
            return self.client.patch(path, json.dumps(data), content_type="application/json")
        self.assertEqual(patch({"revision": row.revision, "due_date": "2026-08-15"}).status_code, 422)
        self.assertEqual(patch({"revision": row.revision, "due_date": "2026-10-15"}).status_code, 200)
        self.assertEqual(patch({"revision": row.revision, "due_date": "2026-10-16"}).status_code, 409)
        row.refresh_from_db()
        self.assertEqual(row.due_date.isoformat(), "2026-10-15")
        self.year.status = AcademicYear.STATUS_CLOSED
        self.year.save(update_fields=["status"])
        self.assertEqual(patch({"revision": row.revision, "due_date": "2026-10-20"}).status_code, 409)

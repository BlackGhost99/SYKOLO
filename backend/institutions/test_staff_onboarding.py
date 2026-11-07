"""Tests du parcours unique : atomicité, droits et isolation par école."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
    Organization, OrganizationMember, School, SchoolAppointment,
    SchoolLogin, SchoolMember, SchoolRole,
)
from .services import ROLE_TEMPLATES
from .staff_models import StaffRecord


class StaffOnboardingTests(TestCase):
    password = "YEM-Onboarding-Tests-2026!owl"

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("founder-onboarding", password=self.password)
        self.org = Organization.objects.create(name="Complexe scolaire")
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role="founder")
        self.school = School.objects.create(
            organization=self.org, name="Complexe Les Etoiles",
            school_type="groupe_scolaire", education_cycles=["prescolaire", "primaire"],
        )
        self.other = School.objects.create(
            organization=self.org, name="Autre école",
            school_type="maternelle", education_cycles=["prescolaire"],
        )
        for school in (self.school, self.other):
            for code, label, perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=perms)
        self.url = f"/api/v1/schools/{self.school.pk}/staff/onboard"
        self.client.force_login(self.owner)

    def payload(self, code="P-001", account=False):
        return {
            "staff": {"staff_code": code, "first_name": "Marie", "last_name": "Obame",
                      "position": "Directrice"},
            "account": {
                "username": "directrice-marie", "email": "marie@example.test",
                "password": self.password, "role": "direction", "additional_roles": [],
            } if account else None,
            "appointments": [
                {"function_code": "directeur_maternelle", "cycle_code": "prescolaire"},
                {"function_code": "directeur_primaire", "cycle_code": "primaire"},
            ],
            "class_assignments": [],
            "ack_school_wide_permissions": True,
        }

    def send(self, data, url=None):
        return self.client.post(url or self.url, data=json.dumps(data),
                                content_type="application/json")

    def test_founder_creates_staff_and_two_appointments_without_account(self):
        opts = self.client.get(self.url)
        self.assertEqual(opts.status_code, 200)
        self.assertTrue(opts.json()["can_create_account"])
        self.assertTrue(opts.json()["can_appoint"])
        r = self.send(self.payload())
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(r.json()["account_created"])
        self.assertEqual(StaffRecord.objects.filter(school=self.school).count(), 1)
        self.assertEqual(SchoolAppointment.objects.filter(school=self.school).count(), 2)

    def test_staff_number_is_generated_only_when_missing(self):
        generated = self.send(self.payload(code=""))
        self.assertEqual(generated.status_code, 201, generated.content)
        self.assertRegex(generated.json()["staff"]["staff_code"], r"^P-[0-9A-F]{32}$")
        existing = self.send(self.payload(code="0007"))
        self.assertEqual(existing.status_code, 201, existing.content)
        self.assertEqual(existing.json()["staff"]["staff_code"], "0007")

    def test_one_transaction_creates_login_staff_and_functions(self):
        data = self.payload(account=True)
        response = self.send(data)
        self.assertEqual(response.status_code, 201, response.content)
        staff = StaffRecord.objects.get(school=self.school)
        self.assertIsNotNone(staff.account_id)
        member = SchoolMember.objects.get(school=self.school, user=staff.account)
        self.assertEqual(set(member.function_codes), {"directeur_maternelle", "directeur_primaire"})
        self.assertTrue(SchoolLogin.objects.filter(
            school=self.school, user=staff.account, username=data["account"]["username"],
        ).exists())
        self.assertTrue(staff.account.check_password(self.password))
        self.assertEqual(SchoolAppointment.objects.filter(staff=staff).count(), 2)

    def test_multicycle_account_requires_explicit_acknowledgement(self):
        data = self.payload(account=True)
        data["ack_school_wide_permissions"] = False
        response = self.send(data)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(StaffRecord.objects.exists())
        self.assertFalse(SchoolLogin.objects.exists())

    def test_duplicate_appointments_and_wrong_cycle_are_rejected_atomically(self):
        data = self.payload(account=True)
        data["appointments"].append(data["appointments"][0].copy())
        self.assertEqual(self.send(data).status_code, 422)
        self.assertFalse(StaffRecord.objects.exists())
        self.assertFalse(SchoolLogin.objects.exists())
        data = self.payload(account=True)
        data["appointments"][0]["cycle_code"] = "college"
        self.assertEqual(self.send(data).status_code, 422)
        self.assertFalse(StaffRecord.objects.exists())
        self.assertFalse(SchoolLogin.objects.exists())

    def test_duplicate_matriule_does_not_create_second_account(self):
        self.assertEqual(self.send(self.payload()).status_code, 201)
        response = self.send(self.payload(account=True))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(StaffRecord.objects.count(), 1)
        self.assertEqual(SchoolLogin.objects.count(), 0)

    def test_other_school_user_cannot_create_staff(self):
        user = get_user_model().objects.create_user("teacher-b", password=self.password)
        role = self.other.roles.get(code="enseignant")
        SchoolMember.objects.create(school=self.other, user=user, role=role)
        self.client.force_login(user)
        self.assertIn(self.client.get(self.url).status_code, (403,404))
        self.assertIn(self.send(self.payload()).status_code, (403,404))
        self.assertFalse(StaffRecord.objects.exists())

    def test_manager_cannot_grant_director_or_finance_roles(self):
        manager = get_user_model().objects.create_user("manager-onboarding", password=self.password)
        role = SchoolRole.objects.create(school=self.school, code="gestion_equipe",
            label="Gestion d'équipe", permissions=[
                "school.view","school.staff.manage","school.members.write",
                "school.organization.manage",
            ])
        SchoolMember.objects.create(school=self.school, user=manager, role=role)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        data = self.payload(account=True)
        self.assertEqual(self.send(data).status_code, 403)
        self.assertFalse(StaffRecord.objects.exists())

    def test_account_role_and_staff_are_isolated_per_school(self):
        data = self.payload(account=True)
        self.assertEqual(self.send(data).status_code, 201)
        self.assertFalse(SchoolMember.objects.filter(school=self.other).exists())
        self.assertFalse(StaffRecord.objects.filter(school=self.other).exists())
        self.assertFalse(SchoolLogin.objects.filter(school=self.other).exists())

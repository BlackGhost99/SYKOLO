"""M1: creation d'un compte scolaire avec un perimetre de cycles explicite."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from institutions.academic_models import AcademicCycle
from institutions.models import Organization, OrganizationMember, School, SchoolMember, SchoolRole


class M1NewAccountCycleScopeTests(TestCase):
    password = "MotDePasseYEM-valide-2026!"

    def setUp(self):
        User = get_user_model()
        self.founder = User.objects.create_user(
            username="founder-m1-scope", password=self.password,
        )
        org = Organization.objects.create(name="Groupe test M1")
        OrganizationMember.objects.create(
            organization=org, user=self.founder, role="founder",
        )
        self.school = School.objects.create(
            organization=org, name="Groupe deux cycles",
            school_type="groupe_scolaire", education_cycles=["primaire", "college"],
        )
        self.foreign = School.objects.create(
            organization=org, name="Autre école", school_type="primaire",
            education_cycles=["primaire"],
        )
        self.primary = AcademicCycle.objects.create(
            school=self.school, code="primaire", name="Primaire",
        )
        self.secondary = AcademicCycle.objects.create(
            school=self.school, code="college", name="Collège",
        )
        self.other_cycle = AcademicCycle.objects.create(
            school=self.foreign, code="primaire", name="Primaire externe",
        )
        self.role = SchoolRole.objects.create(
            school=self.school, code="enseignant", label="Enseignant",
            permissions=["school.view", "school.academic.read"],
        )
        self.client.force_login(self.founder)
        self.path = f"/api/v1/schools/{self.school.pk}/users"

    def create(self, username, scope):
        payload = {
            "username": username,
            "email": f"{username}@example.test",
            "first_name": "Test", "last_name": "Compte",
            "password": self.password,
            "role": "enseignant",
            "function_codes": [],
            "access_cycle_ids": scope,
        }
        return self.client.post(
            self.path, json.dumps(payload), content_type="application/json",
        )

    def test_new_member_scope_is_explicit_and_persisted(self):
        response = self.create("new-primary", [str(self.primary.id)])
        self.assertEqual(response.status_code, 201, response.content)
        member = SchoolMember.objects.get(user__email="new-primary@example.test")
        self.assertEqual(member.school_id, self.school.id)
        self.assertEqual(member.access_cycle_ids, [str(self.primary.id)])

    def test_foreign_cycle_rejected_atomically(self):
        response = self.create("new-foreign", [str(self.other_cycle.id)])
        self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(
            get_user_model().objects.filter(email="new-foreign@example.test").exists()
        )

    def test_global_access_remains_explicitly_possible_for_owner(self):
        response = self.create("new-global", None)
        self.assertEqual(response.status_code, 201, response.content)
        member = SchoolMember.objects.get(user__email="new-global@example.test")
        self.assertIsNone(member.access_cycle_ids)

    def test_roles_catalog_exposes_only_local_active_cycles(self):
        inactive = AcademicCycle.objects.create(
            school=self.school, code="archive", name="Archivé", active=False,
        )
        response = self.client.get(f"/api/v1/schools/{self.school.id}/roles")
        self.assertEqual(response.status_code, 200, response.content)
        ids = {c["id"] for c in response.json()["academic_cycles"]}
        self.assertEqual(ids, {str(self.primary.id), str(self.secondary.id)})
        self.assertNotIn(str(inactive.id), ids)
        self.assertNotIn(str(self.other_cycle.id), ids)

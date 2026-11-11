"""M2.1 — les formulaires élèves refusent les corps JSON malformés sans erreur 500."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from institutions.models import Organization, School, SchoolMember, SchoolRole
from institutions.student_models import Student


class StudentBadPayloadTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="École de recette M2")
        self.school = School.objects.create(
            organization=org, name="Établissement de recette M2",
            school_type="primaire", education_cycles=["primaire"],
        )
        user = get_user_model().objects.create_user(
            username="m2-admin-test", password="MotDePasseM2-fiable-2026!",
        )
        role = SchoolRole.objects.create(
            school=self.school, code="secretariat",
            label="Secrétariat", permissions=[
                "school.view", "school.students.manage",
                "school.students.profile.read", "school.students.sensitive.read",
            ],
        )
        SchoolMember.objects.create(school=self.school, user=user, role=role)
        self.student = Student.objects.create(
            school=self.school, first_name="Élève", last_name="Fictif",
        )
        self.client.force_login(user)
        self.base = f"/api/v1/schools/{self.school.pk}/"
        self.limited_user = get_user_model().objects.create_user(
            username="m2-limited-user", password="MotDePasseM2-fiable-2026!",
        )
        limited_role = SchoolRole.objects.create(
            school=self.school, code="limited_secretariat",
            label="Saisie administrative limitée",
            permissions=["school.view", "school.students.manage",
                         "school.students.profile.read"],
        )
        SchoolMember.objects.create(
            school=self.school, user=self.limited_user, role=limited_role,
        )

    def post_invalid(self, path, payload):
        return self.client.post(
            self.base + path, data=json.dumps(payload),
            content_type="application/json",
        )

    def test_student_create_rejects_array_without_500(self):
        result = self.post_invalid("students", [{"first_name": "Test"}])
        self.assertEqual(result.status_code, 400, result.content)
        self.assertIn("Objet JSON requis", result.json()["error"])
        self.assertEqual(Student.objects.filter(school=self.school).count(), 1)

    def test_guardian_create_rejects_array_without_500(self):
        result = self.post_invalid(
            f"students/{self.student.id}/guardians",
            [{"full_name": "Parent fictif"}],
        )
        self.assertEqual(result.status_code, 400, result.content)
        self.assertIn("Objet JSON requis", result.json()["error"])

    def test_enrollment_create_rejects_array_without_500(self):
        result = self.post_invalid(
            "enrollments", [{"student": str(self.student.id)}],
        )
        self.assertEqual(result.status_code, 400, result.content)
        self.assertIn("Objet JSON requis", result.json()["error"])

    def test_basic_creator_gets_only_non_sensitive_fields(self):
        self.client.force_login(self.limited_user)
        response = self.post_invalid("students", {
            "first_name": "Élève", "last_name": "Test de confidentialité",
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["last_name"], "Test de confidentialité")
        for field in ("date_of_birth", "address", "documents", "extra_fields",
                      "nationality", "previous_school", "place_of_birth"):
            self.assertNotIn(field, response.json())

    def test_basic_creator_cannot_write_sensitive_fields(self):
        self.client.force_login(self.limited_user)
        before = Student.objects.count()
        response = self.post_invalid("students", {
            "first_name": "Test", "last_name": "Refus",
            "address": "Information privée",
        })
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(Student.objects.count(), before)

    def test_combined_registration_denies_creator_without_sensitive_right(self):
        self.client.force_login(self.limited_user)
        before = Student.objects.count()
        response = self.post_invalid("students/register", {
            "student": {"first_name": "Élève", "last_name": "Test"},
            "guardians": [{"full_name": "Responsable fictif"}],
        })
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(Student.objects.count(), before)

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

    def post_invalid(self, path, payload):
        return self.client.post(
            self.base + path, data=json.dumps(payload),
            content_type="application/json",
        )

    def test_student_create_rejects_array_without_500(self):
        result = self.post_invalid("students", [{"first_name": "Test"}])
        self.assertEqual(result.status_code, 422, result.content)
        self.assertIn("Objet JSON attendu", result.json()["error"])
        self.assertEqual(Student.objects.filter(school=self.school).count(), 1)

    def test_guardian_create_rejects_array_without_500(self):
        result = self.post_invalid(
            f"students/{self.student.id}/guardians",
            [{"full_name": "Parent fictif"}],
        )
        self.assertEqual(result.status_code, 422, result.content)
        self.assertIn("Objet JSON attendu", result.json()["error"])

    def test_enrollment_create_rejects_array_without_500(self):
        result = self.post_invalid(
            "enrollments", [{"student": str(self.student.id)}],
        )
        self.assertEqual(result.status_code, 422, result.content)
        self.assertIn("Objet JSON attendu", result.json()["error"])

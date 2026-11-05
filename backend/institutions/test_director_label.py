"""Keep inclusive role labels without changing permissions or custom school titles."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES


class DirectorDisplayLabelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("role-label-director")
        self.school = School.objects.create(
            organization=Organization.objects.create(name="Établissement"),
            name="École",
        )
        self.role = SchoolRole.objects.create(
            school=self.school,
            code="direction",
            label="Direction",  # Existing schools may retain this historic value.
            permissions=["school.view", "school.roles.read"],
        )
        SchoolMember.objects.create(
            school=self.school, user=self.user, role=self.role,
        )
        self.client.force_login(self.user)

    def test_new_school_role_template_has_directeur_directrice_label(self):
        label = next(label for code, label, _ in ROLE_TEMPLATES if code == "direction")
        self.assertEqual(label, "Directeur / Directrice")

    def test_legacy_direction_label_is_updated_in_api_responses(self):
        prefix = f"/api/v1/schools/{self.school.pk}"
        access = self.client.get(prefix + "/my-access")
        self.assertEqual(access.status_code, 200, access.content)
        self.assertEqual(access.json()["role_label"], "Directeur / Directrice")
        roles = self.client.get(prefix + "/roles")
        self.assertEqual(roles.status_code, 200, roles.content)
        director = next(role for role in roles.json()["roles"] if role["code"] == "direction")
        self.assertEqual(director["label"], "Directeur / Directrice")
        self.role.refresh_from_db()
        self.assertEqual(self.role.label, "Direction")  # No destructive migration.

    def test_custom_school_role_label_remains_unchanged(self):
        self.role.label = "Proviseur du lycée"
        self.role.save(update_fields=["label"])
        access = self.client.get(f"/api/v1/schools/{self.school.pk}/my-access")
        self.assertEqual(access.status_code, 200)
        self.assertEqual(access.json()["role_label"], "Proviseur du lycée")

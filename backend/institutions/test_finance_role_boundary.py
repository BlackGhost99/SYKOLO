"""Guard the separation between financial cashiers, approvers and role managers."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES, effective_permissions


class FinanceRoleBoundaryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.founder = User.objects.create_user("finance-owner")
        self.director = User.objects.create_user("finance-director")
        self.other = User.objects.create_user("finance-staff")
        self.school = School.objects.create(
            organization=Organization.objects.create(name="Finance controls"),
            name="École contrôle",
        )
        OrganizationMember.objects.create(
            organization=self.school.organization, user=self.founder, role="founder"
        )
        for code, label, permissions in ROLE_TEMPLATES:
            SchoolRole.objects.create(
                school=self.school, code=code, label=label, permissions=permissions
            )
        SchoolMember.objects.create(
            school=self.school, user=self.director, role=self.role("direction")
        )
        self.base = f"/api/v1/schools/{self.school.pk}/"
        self.client.force_login(self.director)

    def role(self, code):
        return SchoolRole.objects.get(school=self.school, code=code)

    def call(self, path, payload, method="post"):
        return getattr(self.client, method)(
            self.base + path, json.dumps(payload), content_type="application/json"
        )

    def test_director_cannot_create_second_approver_with_known_password(self):
        response = self.call("users", {
            "username": "controlled-approver",
            "email": "controlled@example.test",
            "password": "Stronger Security Password 2026!",
            "role": "direction",
        })
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(get_user_model().objects.filter(username="controlled-approver").exists())

    def test_director_cannot_appoint_financial_staff_or_self_escalate(self):
        for payload in (
            {"username": self.other.username, "role": "direction"},
            {"username": self.other.username, "role": "comptabilite"},
            {"username": self.director.username, "role": "econome"},
            {"username": self.director.username, "role": "direction", "additional_roles": ["econome"]},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.call("members", payload).status_code, 403)
        self.assertFalse(SchoolMember.objects.filter(school=self.school, user=self.other).exists())
        self.assertNotIn("school.finance.receive", effective_permissions(self.director, self.school))

    def test_director_can_still_manage_nonfinancial_staff(self):
        self.assertEqual(self.call("members", {
            "username": self.other.username, "role": "enseignant",
        }).status_code, 201)
        self.assertEqual(self.call("roles", {
            "code": "bibliotheque", "label": "Bibliothèque",
            "permissions": ["school.view", "school.students.read"],
        }).status_code, 201)

    def test_director_cannot_launder_approver_permission_through_roles(self):
        self.assertEqual(self.call("roles", {
            "code": "controlled", "label": "Contrôleur",
            "permissions": ["school.finance.approve"],
        }).status_code, 403)
        teacher = self.role("enseignant")
        self.assertEqual(self.call(f"roles/{teacher.pk}", {
            "label": teacher.label, "revision": teacher.revision,
            "permissions": teacher.permissions + ["school.finance.approve"],
        }, "patch").status_code, 403)
        direction = self.role("direction")
        # Changing a role's label without changing financial authority remains legal.
        self.assertEqual(self.call(f"roles/{direction.pk}", {
            "label": "Directrice", "revision": direction.revision,
            "permissions": direction.permissions,
        }, "patch").status_code, 200)

    def test_founder_cannot_self_grant_financial_powers_by_membership(self):
        self.client.force_login(self.founder)
        self.assertEqual(self.call("members", {
            "username": self.founder.username, "role": "econome",
        }).status_code, 403)
        self.assertFalse(SchoolMember.objects.filter(school=self.school, user=self.founder).exists())
        self.assertEqual(self.call("members", {
            "username": self.director.username, "role": "direction",
            "additional_roles": ["econome"],
        }).status_code, 200)
        self.assertIn("school.finance.receive", effective_permissions(self.director, self.school))

    def test_founder_cannot_upgrade_role_already_assigned_to_self(self):
        founder_member = SchoolMember.objects.create(
            school=self.school, user=self.founder, role=self.role("direction")
        )
        founder_member.additional_roles.add(self.role("econome"))
        self.client.force_login(self.founder)
        direction = self.role("direction")
        self.assertIn("school.finance.receive", effective_permissions(self.founder, self.school))
        # The founder holds the role being modified. Adding a financial duty to
        # it would implicitly add that duty to their own profile.
        response = self.call(f"roles/{direction.pk}", {
            "label": direction.label, "revision": direction.revision,
            "permissions": direction.permissions + ["school.finance.receive"],
        }, "patch")
        self.assertEqual(response.status_code, 403, response.content)
        direction.refresh_from_db()
        self.assertNotIn("school.finance.receive", direction.permissions)

    def test_founder_can_appoint_existing_independent_controller(self):
        self.client.force_login(self.founder)
        self.assertEqual(self.call("members", {
            "username": self.other.username, "role": "comptabilite",
        }).status_code, 201)
        self.assertIn("school.finance.approve", effective_permissions(self.other, self.school))
        self.assertNotIn("school.finance.receive", effective_permissions(self.other, self.school))

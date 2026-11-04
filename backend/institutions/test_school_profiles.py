"""School profile tests: typing is explicit, editable and multi-school isolated."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES


class SchoolProfileTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user("founder-profile", password="Strong profile password 2026!")
        self.outsider = user_model.objects.create_user("outsider-profile", password="Strong profile password 2026!")
        self.org = Organization.objects.create(name="Groupe de test Libreville")
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role="founder")
        self.other_org = Organization.objects.create(name="Établissement étranger")
        self.other_school = School.objects.create(organization=self.other_org, name="École protégée")
        self.client = Client()
        self.client.force_login(self.owner)

    def send(self, path, value, method="post"):
        return getattr(self.client, method)(path, data=json.dumps(value), content_type="application/json")

    def create_school(self, school_type, cycles, name="Établissement YEM"):
        return self.send(f"/api/v1/organizations/{self.org.pk}/schools", {
            "name": name, "school_type": school_type, "enabled_cycles": cycles,
        })

    def test_creation_preset_recommended_roles_and_finance_split(self):
        response = self.create_school("lycee", ["lycee"])
        self.assertEqual(response.status_code, 201, response.content)
        info = response.json()
        school = School.objects.get(pk=info["id"])
        self.assertEqual(info["school_type"], "lycee")
        self.assertEqual(info["enabled_cycles"], ["lycee"])
        roles = {r.code: r for r in SchoolRole.objects.filter(school=school)}
        self.assertEqual(roles["direction"].label, "Direction / Proviseur")
        self.assertIn("censeur_pedagogique", roles)
        self.assertIn("censeur_vie_scolaire", roles)
        self.assertIn("intendant", roles)
        self.assertIn("econome", roles)
        self.assertIn("school.finance.receive", roles["econome"].permissions)
        self.assertNotIn("school.finance.manage", roles["econome"].permissions)
        self.assertNotIn("school.finance.receive", roles["intendant"].permissions)

    def test_multicycle_and_optimistic_update_preserves_custom_permissions(self):
        res = self.create_school("groupe_scolaire", ["lycee", "maternelle"], name="Grand groupe")
        self.assertEqual(res.status_code, 201, res.content)
        school = School.objects.get(pk=res.json()["id"])
        role = SchoolRole.objects.get(school=school, code="econome")
        role.label = "Gestionnaire de caisse local"
        role.permissions = ["school.view", "school.finance.read"]
        role.save()
        endpoint = f"/api/v1/schools/{school.pk}/profile"
        previous = self.client.get(endpoint)
        self.assertEqual(previous.status_code, 200)
        self.assertEqual(previous.json()["enabled_cycles"], ["maternelle", "lycee"])
        changed = self.send(endpoint, {
            "revision": 1, "school_type": "groupe_scolaire",
            "enabled_cycles": ["primaire", "college", "lycee"],
        }, method="patch")
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()["profile_revision"], 2)
        self.assertTrue(SchoolRole.objects.filter(school=school, code="responsable_primaire").exists())
        role.refresh_from_db()
        self.assertEqual(role.label, "Gestionnaire de caisse local")
        self.assertEqual(role.permissions, ["school.view", "school.finance.read"])
        self.assertEqual(self.send(endpoint, {"revision": 1, "school_type": "primaire"}, method="patch").status_code, 409)

    def test_invalid_type_and_cycles_do_not_create_school(self):
        for school_type, cycles in [
            ("lycee", ["primaire"]), ("maternelle", ["maternelle", "maternelle"]),
            ("groupe_scolaire", []), ("universite", ["lycee"]),
            ("college", "college"),
        ]:
            response = self.create_school(school_type, cycles, name="Erreur")
            self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(School.objects.filter(organization=self.org, name="Erreur").exists())

    def test_existing_school_unclassified_and_protected_from_other_school(self):
        legacy = School.objects.create(organization=self.org, name="École historique")
        self.assertEqual(legacy.school_type, "a_configurer")
        self.assertEqual(legacy.enabled_cycles, [])
        endpoint = f"/api/v1/schools/{legacy.pk}/profile"
        self.assertEqual(self.client.get(endpoint).status_code, 200)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(endpoint).status_code, 404)
        self.assertEqual(self.send(endpoint, {"revision": 1, "school_type": "primaire"}, method="patch").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other_school.pk}/profile").status_code, 404)

    def test_school_member_without_setting_permission_cannot_reclassify(self):
        response = self.create_school("college", ["college"])
        school = School.objects.get(pk=response.json()["id"])
        teacher = SchoolRole.objects.get(school=school, code="enseignant")
        SchoolMember.objects.create(school=school, user=self.outsider, role=teacher)
        self.client.force_login(self.outsider)
        endpoint = f"/api/v1/schools/{school.pk}/profile"
        self.assertEqual(self.client.get(endpoint).status_code, 200)
        self.assertEqual(self.send(endpoint, {
            "revision": 1, "school_type": "lycee", "enabled_cycles": ["lycee"],
        }, method="patch").status_code, 403)

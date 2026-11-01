import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from pedagogy.views import PRESETS

from .models import OrganizationMember, School, SchoolMember, SchoolRole, SchoolSetting


class InstitutionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.founder = User.objects.create_user(username="founder-a", password="Strong demo password 2026!")
        self.other = User.objects.create_user(username="founder-b", password="Strong demo password 2026!")
        self.director = User.objects.create_user(username="director-a", password="Strong demo password 2026!")
        self.teacher = User.objects.create_user(username="teacher-a", password="Strong demo password 2026!")
        self.client = Client(enforce_csrf_checks=True)
        self.as_user(self.founder)
        self.org = self.post("/api/v1/organizations", {"name": "Groupement A"}).json()
        self.school = self.post(
            f"/api/v1/organizations/{self.org['id']}/schools",
            {"name": "École de la Réussite", "short_name": "ER"},
        ).json()
        self.school_url = "/api/v1/schools/" + self.school["id"]
        self.as_user(self.other)
        self.org_b = self.post("/api/v1/organizations", {"name": "Groupement B"}).json()
        self.school_b = self.post(
            f"/api/v1/organizations/{self.org_b['id']}/schools",
            {"name": "Lycée B"},
        ).json()

    def as_user(self, user):
        self.client.force_login(user)
        self.token = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, path, body, method="post", csrf=True):
        extra = {"HTTP_X_CSRFTOKEN": self.token} if csrf else {}
        return getattr(self.client, method)(
            path, json.dumps(body), content_type="application/json", **extra
        )

    def test_school_creation_and_isolation(self):
        self.as_user(self.founder)
        self.assertEqual(len(self.client.get("/api/v1/schools").json()["schools"]), 1)
        self.assertEqual(self.client.get(self.school_url).status_code, 200)
        self.assertFalse(SchoolMember.objects.filter(school_id=self.school["id"], user=self.founder).exists())
        self.assertTrue(OrganizationMember.objects.filter(organization_id=self.org["id"], user=self.founder).exists())
        self.assertEqual(self.client.get(self.school_url + "/settings").status_code, 403)
        self.assertEqual(self.client.get(self.school_url + "/members").status_code, 403)
        self.as_user(self.other)
        self.assertEqual(self.client.get(self.school_url).status_code, 404)
        self.assertEqual(self.client.get(self.school_url + "/settings").status_code, 404)
        self.assertEqual(self.client.get(self.school_url + "/members").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/organizations/{self.org['id']}/schools").status_code, 404)

    def test_explicit_director_appointment_and_permissions(self):
        self.as_user(self.founder)
        roles = self.client.get(self.school_url + "/roles")
        self.assertEqual(roles.status_code, 200)
        self.assertIn("direction", [r["code"] for r in roles.json()["roles"]])
        appointed = self.post(self.school_url + "/members", {
            "username": "director-a", "role": "direction",
        })
        self.assertEqual(appointed.status_code, 201)
        self.assertEqual(self.client.get(self.school_url + "/settings").status_code, 403)
        self.as_user(self.director)
        self.assertEqual(self.client.get(self.school_url + "/settings").status_code, 200)
        self.assertEqual(self.client.get(self.school_url + "/members").status_code, 200)
        self.assertEqual(self.client.get(self.school_url + "/audit").status_code, 200)
        self.assertEqual(self.post(self.school_url + "/members", {
            "username": "teacher-a", "role": "enseignant",
        }).status_code, 201)
        self.as_user(self.teacher)
        self.assertEqual(self.client.get(self.school_url + "/settings").status_code, 200)
        self.assertEqual(self.post(self.school_url + "/settings", {
            "scope": {}, "revision": 0, "values": {"branding": {"motto": "Éducation"}},
        }).status_code, 403)
        self.assertEqual(self.client.get(self.school_url + "/members").status_code, 403)
        self.assertEqual(self.client.get(self.school_url + "/audit").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/schools/" + self.school_b["id"]).status_code, 404)

    def test_configurable_grading_resolution_and_revision_conflicts(self):
        self.as_user(self.founder)
        self.post(self.school_url + "/members", {"username": "director-a", "role": "direction"})
        self.as_user(self.director)
        policy = next(p["policy"] for p in PRESETS if p["id"] == "numeric-20")
        base = self.post(self.school_url + "/settings", {
            "scope": {}, "values": {"grading": policy, "notifications": {"sms": False}},
            "revision": 0,
        })
        self.assertEqual(base.status_code, 200, base.content.decode())
        self.assertEqual(base.json()["revision"], 1)
        cycle = self.post(self.school_url + "/settings", {
            "scope": {"cycle": "primaire"}, "values": {"notifications": {"sms": True}},
            "revision": 0,
        })
        self.assertEqual(cycle.status_code, 200, cycle.content.decode())
        self.assertEqual(self.post(self.school_url + "/settings", {
            "scope": {}, "values": {"notifications": {"sms": True}}, "revision": 0,
        }).status_code, 409)
        self.assertEqual(self.client.get(self.school_url + "/settings?cycle=primaire").json()["effective"]["grading"]["scale"]["max"], 20)
        self.assertTrue(self.client.get(self.school_url + "/settings?cycle=primaire").json()["effective"]["notifications"]["sms"])
        self.assertFalse(self.client.get(self.school_url + "/settings?cycle=secondaire").json()["effective"]["notifications"]["sms"])
        self.assertEqual(self.post(self.school_url + "/settings", {
            "scope": {"class": "6e"}, "values": {"x": 1}, "revision": 0,
        }).status_code, 422)
        self.assertEqual(self.post(self.school_url + "/settings", {
            "scope": {}, "values": {"grading": {"scale": {"max": -10}}}, "revision": 1,
        }).status_code, 422)
        self.assertEqual(SchoolSetting.objects.filter(school_id=self.school["id"]).count(), 2)

    def test_revisions_and_role_scope_no_cross_school_assignment(self):
        self.as_user(self.founder)
        self.post(self.school_url + "/members", {"username": "director-a", "role": "direction"})
        self.as_user(self.director)
        added = self.post(self.school_url + "/roles", {
            "code": "bibliothecaire", "label": "Bibliothécaire",
            "permissions": ["school.view", "school.settings.read"],
        })
        self.assertEqual(added.status_code, 201)
        self.assertEqual(self.post(self.school_url + "/roles", {
            "code": "bibliothecaire", "label": "Autre", "permissions": [],
        }).status_code, 409)
        changed = self.post(self.school_url + "/roles/" + added.json()["id"], {
            "label": "Gestion documentaire", "permissions": ["school.view"], "revision": 1,
        }, method="patch")
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.post(self.school_url + "/roles/" + added.json()["id"], {
            "label": "Encore", "permissions": [], "revision": 1,
        }, method="patch").status_code, 409)
        role_b = SchoolRole.objects.filter(school_id=self.school_b["id"], code="direction").first()
        with self.assertRaises(Exception):
            SchoolMember(school_id=self.school["id"], user=self.teacher, role=role_b).full_clean()
        self.assertEqual(self.post(self.school_url + "/members", {
            "username": "teacher-a", "role": "bibliothecaire",
        }).status_code, 201)
        self.as_user(self.teacher)
        self.assertEqual(self.post(self.school_url + "/roles", {
            "code": "hacker", "label": "Autorisations totales",
            "permissions": ["school.settings.write"],
        }).status_code, 403)

    def test_csrf_and_anonymous_requests(self):
        self.as_user(self.founder)
        self.assertEqual(self.post("/api/v1/organizations", {"name": "Rejeté"}, csrf=False).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/schools").status_code, 401)
        self.assertEqual(self.client.get(self.school_url).status_code, 401)

    def test_no_cross_tenant_role_injection_and_no_staff_leak(self):
        self.as_user(self.founder)
        self.assertEqual(self.post(self.school_url + "/members", {
            "username": "director-a", "role": "role-b-inconnu",
        }).status_code, 404)
        self.as_user(self.other)
        self.assertEqual(self.client.get(self.school_url + "/audit").status_code, 404)
        self.assertEqual(self.client.get(self.school_url + "/roles").status_code, 404)
        self.assertEqual(self.post(self.school_url + "/members", {
            "username": "director-a", "role": "direction",
        }).status_code, 404)

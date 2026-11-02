import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Organization, School, SchoolMember

class PlatformProvisioningTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="platform", email="platform@example.org", password="Valid-platform-2026!"
        )
        self.client.force_login(self.admin)
        self.url = "/api/v1/platform/schools"
        self.input = {
            "organization_name":"Fondation Test","school_name":"École Test",
            "username":"responsable","email":"responsable@example.org",
            "first_name":"Anne","last_name":"Test",
            "password":"Valid-responsable-2026!","role":"direction",
        }

    def post(self, url=None, data=None):
        return self.client.post(url or self.url, json.dumps(data or self.input),
                                content_type="application/json")

    def test_requires_confirmed_mfa_session(self):
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(School.objects.count(), 0)

    def test_atomic_provision_and_school_login(self):
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        response = self.post()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(School.objects.count(), 1)
        user = get_user_model().objects.get(username="responsable")
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(self.input["password"]))
        self.assertEqual(SchoolMember.objects.filter(user=user, active=True).count(), 1)

    def test_duplicate_username_does_not_create_orphan_school(self):
        get_user_model().objects.create_user(username="responsable", password="Not-this-password-2026!")
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        response = self.post()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(School.objects.count(), 0)
        self.assertEqual(Organization.objects.count(), 0)

    def test_school_user_cannot_access_platform(self):
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        response = self.post()
        school_id = response.json()["id"]
        user = get_user_model().objects.get(username="responsable")
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.post(
            f"/api/v1/platform/schools/{school_id}/users",json.dumps({
                "username":"teacher","email":"teacher@example.org","password":"Valid-teacher-2026!","role":"enseignant",
                "first_name":"Lena","last_name":"Test"
            }),content_type="application/json"
        ).status_code, 403)

    def test_school_director_can_create_teacher_but_teacher_cannot_create_users(self):
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        response = self.post()
        self.assertEqual(response.status_code, 201, response.content)
        school_id = response.json()["id"]
        director = get_user_model().objects.get(username="responsable")
        self.client.force_login(director)
        teacher = {"username":"teacher","email":"teacher@example.org",
                   "first_name":"A","last_name":"Teacher",
                   "password":"Secure-teacher-2026!", "role":"enseignant"}
        endpoint = f"/api/v1/schools/{school_id}/users"
        result = self.client.post(endpoint, json.dumps(teacher), content_type="application/json")
        self.assertEqual(result.status_code, 201, result.content)
        teacher_user = get_user_model().objects.get(username="teacher")
        self.client.force_login(teacher_user)
        attempt = self.client.post(endpoint, json.dumps({
            **teacher, "username":"another", "email":"another@example.org"
        }), content_type="application/json")
        self.assertEqual(attempt.status_code, 403)

    def test_platform_explicit_school_administration_is_audited(self):
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        response = self.post()
        school_id = response.json()["id"]
        endpoint = f"/api/v1/platform/schools/{school_id}/admin-access"
        self.assertEqual(self.client.post(endpoint).status_code, 200)
        self.assertTrue(SchoolMember.objects.filter(school_id=school_id, user=self.admin, active=True).exists())
        from .models import SchoolAudit
        self.assertTrue(SchoolAudit.objects.filter(school_id=school_id,
            event="platform_admin_school_access").exists())

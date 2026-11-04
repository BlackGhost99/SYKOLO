import json
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import AuthAudit, MFADevice
from institutions.models import Organization, PlatformAudit, School, SchoolMember, SchoolRole


@override_settings(AUTH_PUBLIC_BASE_URL="https://yem.example.test", PASSWORD_RESET_ENABLED=False)
class AssistedPasswordRecoveryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="platform_admin", email="platform_admin@example.test",
            password="Super Admin Access 2027! Strong",
        )
        self.user = User.objects.create_user(
            username="directrice", email="directrice@example.test",
            password="First Valid School Password 2026!",
        )
        org = Organization.objects.create(name="Groupe test")
        self.school = School.objects.create(organization=org, name="Lycée test")
        self.other = School.objects.create(organization=org, name="Collège voisin")
        role = SchoolRole.objects.create(school=self.school, code="direction", label="Direction", permissions=[])
        self.member = SchoolMember.objects.create(user=self.user, school=self.school, role=role)
        self.url = "/api/v1/auth/password/admin-reset"
        self.client = Client(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def login_superadmin(self, mfa=True):
        self.client.force_login(self.admin)
        s = self.client.session
        s["mfa_verified"] = mfa
        s.save()

    def post(self, payload, url=None):
        return self.client.post(
            url or self.url, json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def request_body(self, **other):
        return {
            "school_id": str(self.school.pk), "member_id": str(self.member.pk),
            "reason": "Contrôle de l'identité effectué au secrétariat",
            "current_password": "Super Admin Access 2027! Strong",
            **other,
        }

    def test_mfa_reauthenticated_admin_can_issue_link_without_smtp(self):
        self.login_superadmin()
        MFADevice.objects.create(user=self.user, encrypted_secret="not-used", confirmed_at=timezone.now())
        result = self.post(self.request_body())
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result["Cache-Control"], "no-store, private")
        self.assertIn("yem.example.test/#/reset?uid=", result.json()["reset_url"])
        self.assertNotIn("password", json.dumps(result.json()))
        self.assertEqual(PlatformAudit.objects.filter(event="password_reset_link_issued").count(), 1)
        self.assertEqual(AuthAudit.objects.filter(event="admin_reset_link_issued").count(), 1)
        logged = PlatformAudit.objects.get(event="password_reset_link_issued")
        self.assertNotIn("token=", logged.reason)
        self.assertNotIn("token=", logged.subject)
        self.assertTrue(MFADevice.objects.filter(user=self.user).exists())

        # The recipient chooses the password; the administrator never receives it.
        params = parse_qs(urlparse(result.json()["reset_url"]).fragment.split("?", 1)[1])
        data = {"uid": params["uid"][0], "token": params["token"][0],
                "password": "Another Valid School Password 2027!"}
        changed = self.post(data, "/api/v1/auth/password/reset/confirm")
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(self.post(data, "/api/v1/auth/password/reset/confirm").status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(data["password"]))
        self.assertTrue(MFADevice.objects.filter(user=self.user).exists())

    def test_denies_unauthenticated_without_mfa_and_school_user(self):
        self.assertEqual(self.post(self.request_body()).status_code, 401)
        self.login_superadmin(mfa=False)
        self.assertEqual(self.post(self.request_body()).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.post(self.request_body()).status_code, 403)
        self.login_superadmin()
        self.assertEqual(self.post(self.request_body(), url=self.url).status_code, 200)

    def test_rejects_wrong_password_and_unknown_membership_without_leaking_token(self):
        self.login_superadmin()
        wrong = self.post(self.request_body(current_password="wrong"))
        self.assertEqual(wrong.status_code, 403)
        self.assertNotIn("reset_url", wrong.json())
        target_wrong_school = self.post(self.request_body(school_id=str(self.other.pk)))
        self.assertEqual(target_wrong_school.status_code, 404)
        self.assertEqual(PlatformAudit.objects.filter(event="password_reset_link_issued").count(), 0)

    def test_rejects_platform_accounts_and_inactive_members(self):
        self.login_superadmin()
        role = SchoolRole.objects.get(school=self.school)
        root_member = SchoolMember.objects.create(school=self.school, user=self.admin, role=role)
        self.assertEqual(
            self.post(self.request_body(member_id=str(root_member.pk))).status_code, 403
        )
        self.member.active = False
        self.member.save(update_fields=["active"])
        self.assertEqual(self.post(self.request_body()).status_code, 409)

    def test_verified_parent_can_get_admin_assisted_reset_without_smtp(self):
        parent = get_user_model().objects.create_user(
            username="parent_ga", email="parent_ga@example.test",
            password="Parent Original Secret Password 2026!", is_active=True,
        )
        self.login_superadmin()
        response = self.post({
            "username": "parent_ga", "email": "parent_ga@example.test",
            "reason": "Pièce présentée et identité du parent vérifiée",
            "current_password": "Super Admin Access 2027! Strong",
        }, "/api/v1/auth/password/admin-parent-reset")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("reset_url", response.json())
        self.assertEqual(PlatformAudit.objects.filter(
            school__isnull=True, event="password_reset_link_issued").count(), 1)

        params = parse_qs(urlparse(response.json()["reset_url"]).fragment.split("?", 1)[1])
        data = {"uid": params["uid"][0], "token": params["token"][0],
                "password": "Parent New Secret Password 2027!"}
        self.assertEqual(self.post(data, "/api/v1/auth/password/reset/confirm").status_code, 200)
        parent.refresh_from_db()
        self.assertTrue(parent.check_password(data["password"]))

    def test_parent_assist_rejects_organization_members_and_mismatched_emails(self):
        self.login_superadmin()
        endpoint = "/api/v1/auth/password/admin-parent-reset"
        self.assertEqual(self.post({
            "username": "directrice", "email": "directrice@example.test",
            "reason": "Identité vérifiée par le secrétariat",
            "current_password": "Super Admin Access 2027! Strong",
        }, endpoint).status_code, 404)
        self.assertEqual(self.post({
            "username": "directrice", "email": "different@example.test",
            "reason": "Identité vérifiée par le secrétariat",
            "current_password": "Super Admin Access 2027! Strong",
        }, endpoint).status_code, 404)
        self.assertEqual(PlatformAudit.objects.filter(event="password_reset_link_issued").count(), 0)

    def test_requires_real_reason_and_valid_csrf(self):
        self.login_superadmin()
        self.assertEqual(self.post(self.request_body(reason="x")).status_code, 422)
        self.assertEqual(self.client.post(self.url, json.dumps(self.request_body()),
                         content_type="application/json").status_code, 403)
        self.assertEqual(PlatformAudit.objects.filter(event="password_reset_link_issued").count(), 0)

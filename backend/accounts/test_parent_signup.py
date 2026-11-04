"""Email-verified self-registration creates an ordinary identity, never a school role."""
import json
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from institutions.models import SchoolMember
from institutions.parent_models import GuardianAccountLink


@override_settings(
    PASSWORD_RESET_ENABLED=True,
    AUTH_PUBLIC_BASE_URL="https://yem.example.test",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="YEM <no-reply@yem.example.test>",
)
class ParentRegistrationTests(TestCase):
    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,endpoint,payload):
        return self.client.post("/api/v1/auth/"+endpoint,
            data=json.dumps(payload), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def user_payload(self):
        return {
            "username":"parent-appli-test","first_name":"Diane","last_name":"Nze",
            "email":"famille@example.test","password":"Compte parent de test 2026!",
        }

    def test_registration_requires_email_activation_and_creates_no_school_access(self):
        response=self.post("parents/register",self.user_payload())
        self.assertEqual(response.status_code,201,response.content)
        user=get_user_model().objects.get(username="parent-appli-test")
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(SchoolMember.objects.count(),0)
        self.assertEqual(GuardianAccountLink.objects.count(),0)
        self.assertEqual(len(mail.outbox),1)
        url=re.search(r"uid=([^&\s]+)&token=([^\s]+)",mail.outbox[0].body)
        self.assertIsNotNone(url)
        bad=self.post("parents/verify",{"uid":url.group(1),"token":"forged"})
        self.assertEqual(bad.status_code,422)
        verified=self.post("parents/verify",{"uid":url.group(1),"token":url.group(2)})
        self.assertEqual(verified.status_code,200,verified.content)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(self.post("parents/verify",{"uid":url.group(1),"token":url.group(2)}).status_code,422)

    def test_duplicate_email_does_not_issue_a_second_account(self):
        self.assertEqual(self.post("parents/register",self.user_payload()).status_code,201)
        second=self.user_payload()
        second["username"]="parent-appli-test-2"
        self.assertEqual(self.post("parents/register",second).status_code,200)
        self.assertEqual(get_user_model().objects.count(),1)
        self.assertEqual(len(mail.outbox),1)

    def test_invalid_token_uid_and_csrf_are_rejected(self):
        self.assertEqual(self.post("parents/verify",{"uid":"bm90LWEtVVVJRA","token":"x"}).status_code,422)
        response=self.client.post("/api/v1/auth/parents/register",data=json.dumps(self.user_payload()),
                                  content_type="application/json")
        self.assertEqual(response.status_code,403)

    @override_settings(PASSWORD_RESET_ENABLED=False)
    def test_unconfigured_email_disables_registration(self):
        response=self.post("parents/register",self.user_payload())
        self.assertEqual(response.status_code,503)

    def test_resend_link_is_generic_and_only_for_self_registered_parent(self):
        self.assertEqual(self.post("parents/register",self.user_payload()).status_code,201)
        self.assertEqual(len(mail.outbox),1)
        res=self.post("parents/resend-verification",{"email":"famille@example.test"})
        self.assertEqual(res.status_code,200,res.content)
        self.assertEqual(len(mail.outbox),2)
        missing=self.post("parents/resend-verification",{"email":"inconnu@example.test"})
        self.assertEqual(missing.status_code,200)
        self.assertEqual(missing.json()["message"],res.json()["message"])
        self.assertEqual(len(mail.outbox),2)

    def test_registration_status_does_not_disclose_mail_secrets(self):
        result=self.client.get("/api/v1/auth/parents/registration-status")
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json()["email_registration_available"])
        self.assertNotIn("password",result.content.decode().lower())
        with override_settings(PASSWORD_RESET_ENABLED=False):
            result=self.client.get("/api/v1/auth/parents/registration-status")
            self.assertFalse(result.json()["email_registration_available"])

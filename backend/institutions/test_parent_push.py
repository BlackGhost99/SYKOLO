import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from .parent_push_models import ParentPushDevice
from .parent_push_views import push_cipher


@override_settings(YEM_PARENT_PUSH_ENABLED=True, YEM_PARENT_PUSH_KEY="synthetic-parent-push-key-only-for-tests")
class ParentPushTests(TestCase):
    path = "/api/v1/parents/push-device"
    token = "synthetic:device-token-123456789"

    def setUp(self):
        self.parent = get_user_model().objects.create_user(username="push-parent")
        self.other = get_user_model().objects.create_user(username="push-other")

    def login(self, user, scope="parent"):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        session = client.session
        session["login_scope"] = scope
        session.save()
        client.get("/api/v1/auth/csrf")
        return client

    def send(self, client, payload=None):
        return client.post(self.path, json.dumps(payload or {"token": self.token}),
                           content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)

    def test_registration_encrypted_idempotent_and_revoked_on_logout(self):
        client = self.login(self.parent)
        self.assertEqual(self.send(client).status_code, 201)
        row = ParentPushDevice.objects.get()
        self.assertNotIn(self.token, row.encrypted_token)
        self.assertEqual(push_cipher().decrypt(row.encrypted_token.encode()).decode(), self.token)
        self.assertEqual(self.send(client).status_code, 200)
        self.assertEqual(ParentPushDevice.objects.count(), 1)
        self.assertEqual(client.post("/api/v1/auth/logout", "{}", content_type="application/json",
                                     HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value).status_code, 200)
        self.assertFalse(ParentPushDevice.objects.exists())

    def test_denies_wrong_scope_csrf_and_cross_account_token(self):
        parent = self.login(self.parent)
        stranger = self.login(self.other)
        self.assertEqual(parent.post(self.path, json.dumps({"token":self.token}), content_type="application/json").status_code, 403)
        self.assertEqual(self.send(self.login(self.other, "school")).status_code, 403)
        self.assertEqual(self.send(parent, {"token":self.token, "parent":str(self.other.pk)}).status_code, 422)
        self.assertEqual(self.send(parent).status_code, 201)
        self.assertEqual(self.send(stranger).status_code, 409)
        self.assertEqual(ParentPushDevice.objects.get().parent, self.parent)
        self.assertEqual(stranger.delete(self.path, HTTP_X_CSRFTOKEN=stranger.cookies["csrftoken"].value).status_code, 200)
        self.assertEqual(ParentPushDevice.objects.count(),1)

    @override_settings(YEM_PARENT_PUSH_ENABLED=False)
    def test_default_off(self):
        self.assertEqual(self.send(self.login(self.parent)).status_code, 503)
        self.assertFalse(ParentPushDevice.objects.exists())

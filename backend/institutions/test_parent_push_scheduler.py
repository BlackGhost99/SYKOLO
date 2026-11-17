from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

PATH = "/internal/yem-parent-push"
TOKEN = "a" * 64
AUTH = {"HTTP_AUTHORIZATION": "Bearer " + TOKEN}
MODULE = "institutions.parent_push_scheduler"


@override_settings(YEM_PARENT_PUSH_ENABLED=True, YEM_PARENT_PUSH_KEY="x" * 64)
class ParentPushSchedulerTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    @patch(MODULE + ".take_ticket")
    def test_requires_post_and_exact_bearer(self, ticket):
        self.assertEqual(self.client.get(PATH).status_code, 405)
        self.assertEqual(self.client.post(PATH).status_code, 401)
        self.assertEqual(self.client.post(PATH, HTTP_AUTHORIZATION="Bearer bad").status_code, 401)
        ticket.assert_not_called()

    @patch(MODULE + ".take_ticket", return_value=False)
    @patch(MODULE + ".enqueue")
    def test_invalid_or_replayed_ticket_never_dispatches(self, enqueue, ticket):
        self.assertEqual(self.client.post(PATH, **AUTH).status_code, 401)
        ticket.assert_called_once_with(TOKEN)
        enqueue.assert_not_called()

    @override_settings(YEM_PARENT_PUSH_ENABLED=False)
    @patch(MODULE + ".take_ticket")
    def test_disabled(self, ticket):
        self.assertEqual(self.client.post(PATH, **AUTH).status_code, 503)
        ticket.assert_not_called()

    @patch(MODULE + ".take_ticket", return_value=True)
    @patch(MODULE + ".enqueue", return_value=2)
    @patch(MODULE + ".deliver", return_value={"accepted": 2, "retry": 0})
    @patch(MODULE + ".FcmTransport")
    def test_one_bounded_dispatch(self, transport, deliver, enqueue, ticket):
        with patch.dict("os.environ", {"YEM_FCM_SERVICE_ACCOUNT_JSON": "test", "YEM_FCM_PROJECT_ID": "sykolo"}):
            response = self.client.post(PATH, **AUTH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["queued"], 2)
        enqueue.assert_called_once_with(limit=12)
        deliver.assert_called_once_with(transport.return_value, limit=3)
        transport.assert_called_once_with("test", "sykolo", timeout=5)

    @patch(MODULE + ".take_ticket", return_value=True)
    @patch(MODULE + ".FcmTransport", side_effect=ValueError("private value"))
    def test_no_secret_in_error(self, transport, ticket):
        with patch.dict("os.environ", {"YEM_FCM_SERVICE_ACCOUNT_JSON": "test", "YEM_FCM_PROJECT_ID": "sykolo"}):
            response = self.client.post(PATH, **AUTH)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private value", response.content.decode())

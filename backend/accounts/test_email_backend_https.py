from unittest.mock import patch
from urllib.error import HTTPError

from django.core import mail
from django.test import SimpleTestCase, override_settings


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(
    EMAIL_BACKEND="accounts.email_backends.ResendEmailBackend",
    YEM_RESEND_API_KEY="test-secret-only",
    DEFAULT_FROM_EMAIL="YEM <no-reply@example.test>",
)
class HttpsEmailBackendTests(SimpleTestCase):
    @patch("accounts.email_backends.urlopen", return_value=FakeResponse())
    def test_email_sent_to_exactly_one_recipient_over_https(self, urlopen):
        count = mail.send_mail(
            "YEM — Réinitialisation", "Lien temporaire : https://example.test/#/reset?token=test",
            None, ["directrice@example.test"], fail_silently=False,
        )
        self.assertEqual(count, 1)
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.resend.com/emails")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer test-secret-only")
        self.assertEqual(req.get_header("User-agent"), "YEM/1.0")
        self.assertIn(b"directrice@example.test", req.data)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 8)

    @patch("accounts.email_backends.urlopen", side_effect=HTTPError(
        "https://api.resend.com/emails", 403, "forbidden", {}, None))
    def test_provider_failure_does_not_expose_api_key(self, urlopen):
        with self.assertRaises(RuntimeError) as caught:
            mail.send_mail(
                "Test", "Message", None, ["directrice@example.test"], fail_silently=False,
            )
        self.assertNotIn("test-secret-only", str(caught.exception))
        self.assertNotIn("https://example.test", str(caught.exception))

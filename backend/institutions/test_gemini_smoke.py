from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class GeminiSmokeCommandTests(SimpleTestCase):
    @override_settings(ENVIRONMENT="test", YEM_GEMINI_API_KEY="fixture-key", YEM_GEMINI_MODEL="fixture-model")
    @patch("institutions.management.commands.yem_test_gemini.header_adapter")
    def test_smoke_sends_one_synthetic_request(self, factory):
        factory.return_value = Mock(return_value={"0": "balance", "1": "payment_candidate"})
        output = StringIO()
        call_command("yem_test_gemini", stdout=output)
        factory.assert_called_once_with("gemini", model="fixture-model", api_key="fixture-key")
        factory.return_value.assert_called_once_with({"0": ("solde",), "1": ("versement",)})
        self.assertIn("deux colonnes fictives", output.getvalue())
        self.assertNotIn("fixture-key", output.getvalue())

    @override_settings(ENVIRONMENT="production")
    @patch("institutions.management.commands.yem_test_gemini.header_adapter")
    def test_production_rejects_before_network(self, factory):
        with self.assertRaises(CommandError):
            call_command("yem_test_gemini")
        factory.assert_not_called()

    @override_settings(ENVIRONMENT="test", YEM_GEMINI_API_KEY="", YEM_GEMINI_MODEL="")
    @patch("institutions.intelligence_providers.build_opener")
    def test_missing_configuration_fails_without_network(self, network):
        with self.assertRaises(CommandError):
            call_command("yem_test_gemini")
        network.assert_not_called()

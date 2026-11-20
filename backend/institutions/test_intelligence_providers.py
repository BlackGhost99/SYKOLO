import json
from unittest.mock import MagicMock, Mock, patch
from urllib.error import URLError

from django.test import SimpleTestCase

from .intelligence_engine import IntelligenceEngine, engine
from .intelligence_providers import (
    CHAT_ENDPOINTS, GEMINI_ENDPOINT, MAX_OUTPUT_TOKENS, MAX_RESPONSE_BYTES,
    ProviderError, REQUEST_TIMEOUT, header_adapter, post_json,
)


class IntelligenceProviderTests(SimpleTestCase):
    def test_chat_adapters_use_their_own_endpoint_and_output_limit(self):
        for provider, (endpoint, token_field) in CHAT_ENDPOINTS.items():
            with self.subTest(provider=provider):
                send = Mock(return_value={"choices": [{
                    "finish_reason": "stop", "message": {"content": '{"1":"balance"}'},
                }]})
                advisor = header_adapter(provider, model="mock-model", api_key="test-key", transport=send)
                send.assert_not_called()
                result = IntelligenceEngine(header_advisor=advisor).classify_headers({
                    "1": "solde prénom 077777777", "2": "octobre",
                })
                self.assertEqual(result.hints, {"1": "balance", "2": "ambiguous"})
                self.assertEqual(result.source, "advisor")
                url, auth, body = send.call_args.args
                self.assertEqual(url, endpoint)
                self.assertEqual(auth, {"Authorization": "Bearer test-key"})
                self.assertEqual(body[token_field], MAX_OUTPUT_TOKENS)
                self.assertEqual(body["response_format"], {"type": "json_object"})
                self.assertIn('"1":["solde"]', body["messages"][0]["content"])
                self.assertNotIn("077777777", json.dumps(body))
                self.assertNotIn("test-key", json.dumps(body))

    def test_gemini_uses_generate_content_and_excludes_thought_parts(self):
        send = Mock(return_value={"candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"thought": True, "text": "private"}, {"text": '{"1":"billing"}'}]},
        }]})
        advisor = header_adapter("gemini", model="mock-model", api_key="test-key", transport=send)
        self.assertEqual(advisor({"1": ("frais",)}), {"1": "billing"})
        url, auth, body = send.call_args.args
        self.assertEqual(url, GEMINI_ENDPOINT + "mock-model:generateContent")
        self.assertEqual(auth, {"x-goog-api-key": "test-key"})
        self.assertEqual(body["generationConfig"], {
            "responseMimeType": "application/json", "maxOutputTokens": MAX_OUTPUT_TOKENS,
        })

    def test_invalid_input_is_rejected_before_transport(self):
        send = Mock()
        advisor = header_adapter("openai", model="mock-model", api_key="test-key", transport=send)
        for clues in ({"1": ("solde privé",)}, {"école": ("solde",)}, {}, {"1": "solde"},
                      {str(i): ("solde",) for i in range(25)}):
            with self.subTest(clues=clues), self.assertRaises(ProviderError):
                advisor(clues)
        send.assert_not_called()
        with self.assertRaises(ValueError):
            header_adapter("gemini", model="../wrong", api_key="test-key", transport=send)

    def test_truncation_refusal_and_invalid_categories_fall_back(self):
        for finish, message in (
            ("length", {"content": '{"1":"billing"}'}),
            ("stop", {"refusal": "blocked"}),
            ("stop", {"content": '{"1":"balance","1":"billing"}'}),
            ("stop", {"content": '{"1":"execute_payment"}'}),
            ("stop", {"content": '{"2":"balance"}'}),
        ):
            with self.subTest(finish=finish, message=message):
                send = Mock(return_value={"choices": [{"finish_reason": finish, "message": message}]})
                advisor = header_adapter("mistral", model="mock-model", api_key="test-key", transport=send)
                with self.assertLogs("institutions.intelligence_engine", level="WARNING"):
                    result = IntelligenceEngine(header_advisor=advisor).classify_headers({"1": "solde"})
                self.assertEqual(result.hints, {"1": "balance"})
                self.assertEqual(result.source, "local_fallback")
                send.assert_called_once()

    @patch("institutions.intelligence_providers.build_opener")
    def test_transport_sets_timeout_bounds_response_and_hides_error(self, build):
        remote = MagicMock()
        build.return_value.open.return_value.__enter__.return_value = remote
        remote.read.return_value = b" " * (MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(ProviderError):
            post_json(CHAT_ENDPOINTS["openai"][0], {}, {})
        remote.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
        self.assertEqual(build.return_value.open.call_args.kwargs["timeout"], REQUEST_TIMEOUT)
        self.assertIsNone(build.call_args.args[0].redirect_request(None, None, 302, "", {}, "https://unexpected.test"))
        build.return_value.open.side_effect = URLError("secret detail")
        with self.assertRaisesRegex(ProviderError, "^Provider request failed$"):
            post_json(CHAT_ENDPOINTS["openai"][0], {}, {})

    def test_application_still_has_no_configured_adapter(self):
        self.assertFalse(engine.capabilities()["header_adapter_configured"])

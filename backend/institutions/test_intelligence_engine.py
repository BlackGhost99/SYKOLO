"""The advisory boundary never promotes columns or accepts free-form output."""
from unittest import TestCase
from unittest.mock import Mock

from .intelligence_engine import IntelligenceEngine
from .intelligence_import import analyze_import_headers


class IntelligenceEngineTests(TestCase):
    def test_local_engine_labels_advisory_headers_only(self):
        result = analyze_import_headers(["Matricule", "Solde", "Bourse", "Octobre", "Versement"])
        self.assertFalse(result["external_provider_used"])
        self.assertEqual(result["financial_columns"], [1, 2, 3, 4])
        self.assertEqual(result["financial_hints"], {
            "1": "balance", "2": "scholarship", "3": "ambiguous", "4": "payment_candidate",
        })

    def test_valid_advice_respects_candidate_scope(self):
        advisor = Mock(return_value={"1": "payment_candidate"})
        headers = {"1": "versement Marie X 077777777", "2": "octobre"}
        result = IntelligenceEngine(header_advisor=advisor).classify_headers(headers)
        self.assertEqual(result.hints, {"1": "payment_candidate", "2": "ambiguous"})
        self.assertEqual(result.source, "advisor")
        advisor.assert_called_once_with({"1": ("versement",)})

    def test_rejects_out_of_scope_or_malformed_advice(self):
        headers = {"1": "solde"}
        for output in (
            {"1": "balance", "9": "payment_candidate"}, {}, {"1": "confirm_payment"},
            {"1": ["balance"]}, ["balance"],
        ):
            with self.subTest(output=output):
                advisor = Mock(return_value=output)
                with self.assertLogs("institutions.intelligence_engine", level="WARNING"):
                    result = IntelligenceEngine(header_advisor=advisor).classify_headers(headers)
                self.assertEqual(result.hints, {"1": "balance"})
                self.assertEqual(result.source, "local_fallback")

    def test_unavailable_advisor_falls_back_locally(self):
        advisor = Mock(side_effect=TimeoutError("secret detail"))
        engine = IntelligenceEngine(header_advisor=advisor)
        with self.assertLogs("institutions.intelligence_engine", level="WARNING") as logs:
            result = engine.classify_headers({"1": "solde"})
        self.assertEqual(result.hints, {"1": "balance"})
        self.assertEqual(result.source, "local_fallback")
        self.assertNotIn("secret detail", "\n".join(logs.output))
        advisor.reset_mock()
        self.assertEqual(engine.classify_headers({}).hints, {})
        self.assertEqual(engine.classify_headers({"1": "octobre"}).source, "local")
        advisor.assert_not_called()

    def test_student_identifiers_always_stay_in_local_numbering(self):
        advisor = Mock()
        engine = IntelligenceEngine(header_advisor=advisor)
        result = engine.suggest_numbering(iter(["0001", "0002", "0003"]))
        self.assertEqual(result["candidates"][0]["next_code"], "0004")
        advisor.assert_not_called()

    def test_arbitrary_candidate_keys_never_reach_the_adapter(self):
        advisor = Mock()
        engine = IntelligenceEngine(header_advisor=advisor)
        with self.assertLogs("institutions.intelligence_engine", level="WARNING"):
            result = engine.classify_headers({"private data": "solde"})
        self.assertEqual(result.source, "local_fallback")
        advisor.assert_not_called()

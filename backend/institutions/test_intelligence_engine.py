"""The advisory boundary never promotes columns or accepts free-form output."""
from unittest import TestCase
from unittest.mock import Mock

from .intelligence_engine import classify_financial_headers
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
        headers = {"1": "octobre"}
        self.assertEqual(classify_financial_headers(headers, advisor=advisor), advisor.return_value)
        advisor.assert_called_once_with(headers)

    def test_rejects_out_of_scope_or_malformed_advice(self):
        headers = {"1": "solde"}
        for output in (
            {"1": "balance", "9": "payment_candidate"}, {}, {"1": "confirm_payment"},
            {"1": ["balance"]}, ["balance"],
        ):
            with self.subTest(output=output):
                advisor = Mock(return_value=output)
                self.assertEqual(classify_financial_headers(headers, advisor=advisor), {"1": "balance"})

    def test_unavailable_advisor_falls_back_locally(self):
        advisor = Mock(side_effect=TimeoutError)
        self.assertEqual(classify_financial_headers({"1": "solde"}, advisor=advisor), {"1": "balance"})
        advisor.reset_mock()
        self.assertEqual(classify_financial_headers({}, advisor=advisor), {})
        advisor.assert_not_called()

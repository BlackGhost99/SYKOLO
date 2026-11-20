from django.test import SimpleTestCase

from .intelligence_numbering import suggest_series
from .student_numbering import MAX_NUMBER


class IntelligenceNumberingTests(SimpleTestCase):
    def test_continues_numeric_and_affixed_series(self):
        for existing, template, expected in [
            (["0001", "0050", "0500"], "{n}", "0501"),
            (["AW-0001", "AW-0250", "AW-0010"], "AW-{n}", "AW-0251"),
            (["001/A", "150/A"], "{n}/A", "151/A"),
            (["2026-0001", "2026-0320"], "2026-{n}", "2026-0321"),
        ]:
            with self.subTest(template=template):
                result = suggest_series(existing)
                self.assertEqual(result["candidates"][0]["template"], template)
                self.assertEqual(result["candidates"][0]["next_code"], expected)
                self.assertTrue(result["confirmation_required"])

    def test_mixed_series_and_ambiguous_counter(self):
        result = suggest_series(["AW-001", "AW-200", "BT-001", "BT-003"])
        self.assertTrue(result["ambiguous"])
        self.assertEqual({c["next_code"] for c in result["candidates"]}, {"AW-201", "BT-004"})
        result = suggest_series(["2025-001", "2026-001", "2026-002"])
        self.assertTrue(result["ambiguous"])
        self.assertIn("2026-{n}", {c["template"] for c in result["candidates"]})
        self.assertIn("{n}-001", {c["template"] for c in result["candidates"]})

    def test_no_permanent_yem_ids_or_duplicate_evidence(self):
        result = suggest_series(["YEM-1234", "aw-001", "AW-001", "", None])
        self.assertEqual(result["distinct_local_codes"], 1)
        self.assertEqual(result["candidates"][0]["matched"], 1)
        self.assertTrue(result["ambiguous"])
        self.assertEqual(suggest_series(["YEM-1234"])["candidates"], [])

    def test_exhaustion_and_sample_limit(self):
        result = suggest_series([str(MAX_NUMBER - 1), str(MAX_NUMBER)])
        self.assertIsNone(result["candidates"][0]["next_code"])
        result = suggest_series(str(i) for i in range(10001))
        self.assertTrue(result["truncated"])
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["examined"], 10000)

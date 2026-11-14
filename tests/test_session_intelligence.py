import unittest
from decimal import Decimal

from src.session_intelligence import analyze_session_intelligence


def make_snapshot():
    return {
        "session_date": "2026-11-11",
        "status": "READY",
        "comparisons": {
            "ADAUSDT": {
                "5m": {
                    "status": "READY",
                    "london_direction": "BULLISH",
                    "new_york_direction": "BULLISH",
                    "direction_match": True,
                    "change_pct_difference": "0.5",
                    "range_pct_difference": "1.2",
                    "volume_difference": "100",
                    "volume_change_pct": "25",
                }
            }
        },
    }


class TestSessionIntelligence(unittest.TestCase):

    def test_ready_analysis(self):
        result = analyze_session_intelligence(make_snapshot())

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["ready"], 1)
        self.assertEqual(result["incomplete"], 0)

    def test_new_york_dominance(self):
        result = analyze_session_intelligence(make_snapshot())
        item = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(item["session_dominance"], "NEW_YORK")
        self.assertEqual(item["range_behavior"], "NEW_YORK_WIDER")

    def test_london_dominance(self):
        snapshot = make_snapshot()
        item = snapshot["comparisons"]["ADAUSDT"]["5m"]
        item["range_pct_difference"] = "-0.8"

        result = analyze_session_intelligence(snapshot)
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["session_dominance"], "LONDON")
        self.assertEqual(analysis["range_behavior"], "LONDON_WIDER")

    def test_balanced_range(self):
        snapshot = make_snapshot()
        snapshot["comparisons"]["ADAUSDT"]["5m"]["range_pct_difference"] = "0"

        result = analyze_session_intelligence(snapshot)
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["session_dominance"], "BALANCED")
        self.assertEqual(analysis["range_behavior"], "EQUAL")

    def test_direction_alignment(self):
        result = analyze_session_intelligence(make_snapshot())
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["direction_alignment"], "ALIGNED")

    def test_direction_divergence(self):
        snapshot = make_snapshot()
        item = snapshot["comparisons"]["ADAUSDT"]["5m"]
        item["new_york_direction"] = "BEARISH"
        item["direction_match"] = False

        result = analyze_session_intelligence(snapshot)
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["direction_alignment"], "DIVERGENT")

    def test_flat_direction_is_neutral(self):
        snapshot = make_snapshot()
        item = snapshot["comparisons"]["ADAUSDT"]["5m"]
        item["london_direction"] = "FLAT"
        item["new_york_direction"] = "FLAT"

        result = analyze_session_intelligence(snapshot)
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["direction_alignment"], "NEUTRAL")

    def test_mixed_direction(self):
        snapshot = make_snapshot()
        item = snapshot["comparisons"]["ADAUSDT"]["5m"]
        item["new_york_direction"] = "FLAT"
        item["direction_match"] = False

        result = analyze_session_intelligence(snapshot)
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["direction_alignment"], "MIXED")

    def test_volume_behavior(self):
        result = analyze_session_intelligence(make_snapshot())
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertEqual(analysis["volume_behavior"], "NEW_YORK_HIGHER")

    def test_zero_baseline_volume(self):
        snapshot = make_snapshot()
        item = snapshot["comparisons"]["ADAUSDT"]["5m"]
        item["volume_change_pct"] = None

        result = analyze_session_intelligence(snapshot)
        analysis = result["intelligence"]["ADAUSDT"]["5m"]

        self.assertIsNone(analysis["volume_change_pct"])
        self.assertEqual(analysis["volume_behavior"], "NEW_YORK_HIGHER")

    def test_incomplete_comparison(self):
        snapshot = make_snapshot()
        snapshot["comparisons"]["ADAUSDT"]["5m"]["status"] = "INCOMPLETE"

        result = analyze_session_intelligence(snapshot)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["ready"], 0)
        self.assertEqual(result["incomplete"], 1)

    def test_non_finite_metric(self):
        snapshot = make_snapshot()
        snapshot["comparisons"]["ADAUSDT"]["5m"]["range_pct_difference"] = "NaN"

        result = analyze_session_intelligence(snapshot)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["incomplete"], 1)

    def test_inconsistent_direction_match(self):
        snapshot = make_snapshot()
        snapshot["comparisons"]["ADAUSDT"]["5m"]["direction_match"] = False

        result = analyze_session_intelligence(snapshot)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["incomplete"], 1)

    def test_partial_source_remains_partial(self):
        snapshot = make_snapshot()
        snapshot["status"] = "PARTIAL"

        result = analyze_session_intelligence(snapshot)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["ready"], 1)

    def test_invalid_root_input(self):
        with self.assertRaises(ValueError):
            analyze_session_intelligence(None)


if __name__ == "__main__":
    unittest.main()

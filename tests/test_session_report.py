import unittest

from src.session_report import build_session_report


def make_inputs():
    date = "2026-11-11"

    analysis = {
        "status": "READY",
        "change_pct": "1.25",
        "range_pct": "2.50",
        "volume": "1200",
    }

    london = {
        "session_date": date,
        "status": "READY",
        "ready": 1,
        "total": 1,
        "results": {
            "ADAUSDT": {
                "5m": {"status": "READY", "analysis": analysis}
            }
        },
    }

    new_york = {
        "session_date": date,
        "status": "READY",
        "ready": 1,
        "total": 1,
        "results": {
            "ADAUSDT": {
                "5m": {
                    "status": "READY",
                    "analysis": {
                        **analysis,
                        "change_pct": "-0.50",
                        "range_pct": "3.00",
                        "volume": "1500",
                    },
                }
            }
        },
    }

    comparison = {
        "session_date": date,
        "status": "READY",
        "comparisons": {
            "ADAUSDT": {
                "5m": {
                    "status": "READY",
                    "london_direction": "BULLISH",
                    "new_york_direction": "BEARISH",
                    "direction_match": False,
                    "change_pct_difference": "-1.75",
                    "range_pct_difference": "0.50",
                    "volume_difference": "300",
                    "volume_change_pct": "25",
                }
            }
        },
    }

    intelligence = {
        "session_date": date,
        "status": "READY",
        "ready": 1,
        "total": 1,
        "intelligence": {
            "ADAUSDT": {
                "5m": {
                    "status": "READY",
                    "session_dominance": "NEW_YORK",
                    "direction_alignment": "DIVERGENT",
                    "london_direction": "BULLISH",
                    "new_york_direction": "BEARISH",
                    "range_behavior": "NEW_YORK_WIDER",
                    "volume_behavior": "NEW_YORK_HIGHER",
                }
            }
        },
    }

    return london, new_york, comparison, intelligence


class TestSessionReport(unittest.TestCase):

    def test_build_complete_report(self):
        report = build_session_report(*make_inputs())

        self.assertIn("IRZIAN SESSION INTELLIGENCE", report)
        self.assertIn("ADAUSDT", report)
        self.assertIn("Dominance: NEW_YORK", report)
        self.assertIn("Direction: DIVERGENT", report)
        self.assertIn("Complete: 1/1", report)

    def test_report_contains_both_sessions(self):
        report = build_session_report(*make_inputs())

        self.assertIn("London: change 1.25%", report)
        self.assertIn("New York: change -0.50%", report)

    def test_incomplete_session_is_not_guessed(self):
        inputs = list(make_inputs())
        inputs[0]["results"]["ADAUSDT"]["5m"]["status"] = "INCOMPLETE"

        report = build_session_report(*inputs)

        self.assertIn("5m: INCOMPLETE", report)
        self.assertIn("Complete: 0/1", report)

    def test_incomplete_intelligence_is_not_reported_as_ready(self):
        inputs = list(make_inputs())
        inputs[3]["intelligence"]["ADAUSDT"]["5m"]["status"] = "INCOMPLETE"

        report = build_session_report(*inputs)

        self.assertIn("5m: INCOMPLETE", report)

    def test_date_mismatch_is_rejected(self):
        inputs = list(make_inputs())
        inputs[1]["session_date"] = "2026-11-10"

        with self.assertRaises(ValueError):
            build_session_report(*inputs)

    def test_missing_session_date_is_rejected(self):
        inputs = list(make_inputs())
        inputs[0]["session_date"] = None

        with self.assertRaises(ValueError):
            build_session_report(*inputs)

    def test_invalid_comparison_snapshot_is_rejected(self):
        inputs = list(make_inputs())
        inputs[2]["comparisons"] = None

        with self.assertRaises(ValueError):
            build_session_report(*inputs)

    def test_invalid_metric_becomes_incomplete(self):
        inputs = list(make_inputs())
        inputs[2]["comparisons"]["ADAUSDT"]["5m"][
            "range_pct_difference"
        ] = "NaN"

        report = build_session_report(*inputs)

        self.assertIn("5m: INCOMPLETE", report)

    def test_report_is_read_only(self):
        report = build_session_report(*make_inputs())

        self.assertIn("READ ONLY - NO TRADE EXECUTION", report)


if __name__ == "__main__":
    unittest.main()

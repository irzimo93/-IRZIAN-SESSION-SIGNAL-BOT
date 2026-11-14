import unittest
from datetime import date
from decimal import Decimal

from src.session_comparison import compare_sessions


def make_snapshot(session, change, range_pct, volume, status="READY"):
    return {
        "session": session,
        "session_date": date(2026, 11, 11),
        "results": {
            "ADAUSDT": {
                "15m": {
                    "status": status,
                    "analysis": {
                        "change_pct": Decimal(str(change)),
                        "range_pct": Decimal(str(range_pct)),
                        "volume": Decimal(str(volume)),
                    },
                }
            }
        },
    }


class TestSessionComparison(unittest.TestCase):

    def test_complete_comparison(self):
        london = make_snapshot("london", 2, 3, 100)
        new_york = make_snapshot("new_york", -1, 5, 150)

        result = compare_sessions(london, new_york)
        item = result["comparisons"]["ADAUSDT"]["15m"]

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["ready"], 1)
        self.assertEqual(item["london_direction"], "BULLISH")
        self.assertEqual(item["new_york_direction"], "BEARISH")
        self.assertFalse(item["direction_match"])
        self.assertEqual(item["change_pct_difference"], Decimal("-3"))
        self.assertEqual(item["range_pct_difference"], Decimal("2"))
        self.assertEqual(item["volume_difference"], Decimal("50"))
        self.assertEqual(item["volume_change_pct"], Decimal("50"))

    def test_incomplete_session(self):
        london = make_snapshot("london", 2, 3, 100)
        new_york = make_snapshot("new_york", 1, 2, 80, status="INCOMPLETE")

        result = compare_sessions(london, new_york)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["ready"], 0)
        self.assertEqual(result["incomplete"], 1)

    def test_different_dates_rejected(self):
        london = make_snapshot("london", 2, 3, 100)
        new_york = make_snapshot("new_york", 1, 2, 80)
        new_york["session_date"] = date(2026, 11, 12)

        with self.assertRaises(ValueError):
            compare_sessions(london, new_york)

    def test_zero_london_volume(self):
        london = make_snapshot("london", 0, 1, 0)
        new_york = make_snapshot("new_york", 0, 2, 50)

        result = compare_sessions(london, new_york)
        item = result["comparisons"]["ADAUSDT"]["15m"]

        self.assertEqual(result["status"], "READY")
        self.assertEqual(item["volume_difference"], Decimal("50"))
        self.assertIsNone(item["volume_change_pct"])


if __name__ == "__main__":
    unittest.main()

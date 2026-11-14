import unittest
from datetime import date
from unittest.mock import patch

from src.market_data import SYMBOLS, INTERVALS
from src.session_snapshot import build_session_snapshot


class FakeClient:
    def fetch_closed_klines(self, symbol, interval, limit):
        return [object()]


class TestSessionSnapshot(unittest.TestCase):

    @patch("src.session_snapshot.analyze_session")
    def test_complete_snapshot(self, mock_analyze):
        mock_analyze.return_value = {"change_pct": 1}

        result = build_session_snapshot(
            session="London",
            session_date=date(2026, 11, 11),
            client=FakeClient(),
        )

        total = len(SYMBOLS) * len(INTERVALS)

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["total"], total)
        self.assertEqual(result["ready"], total)
        self.assertEqual(result["incomplete"], 0)
        self.assertEqual(mock_analyze.call_count, total)

    @patch("src.session_snapshot.analyze_session")
    def test_partial_snapshot(self, mock_analyze):
        mock_analyze.side_effect = [
            {"change_pct": 1},
            ValueError("Incomplete session"),
        ] + [{"change_pct": 1}] * (
            len(SYMBOLS) * len(INTERVALS) - 2
        )

        result = build_session_snapshot(
            session="London",
            session_date=date(2026, 11, 11),
            client=FakeClient(),
        )

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["ready"], result["total"] - 1)
        self.assertEqual(result["incomplete"], 1)
        self.assertEqual(len(result["errors"]), 1)

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            build_session_snapshot(
                session="London",
                session_date="2026-11-11",
                client=FakeClient(),
            )

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            build_session_snapshot(
                session="London",
                session_date=date(2026, 11, 11),
                client=FakeClient(),
                limit=1501,
            )


if __name__ == "__main__":
    unittest.main()

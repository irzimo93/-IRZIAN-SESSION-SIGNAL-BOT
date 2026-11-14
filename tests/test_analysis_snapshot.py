import unittest
from decimal import Decimal
from unittest.mock import Mock

from src.market_data import Candle, SYMBOLS, INTERVALS
from src.analysis_snapshot import build_snapshot


def fake_candles(count=220):
    result = []

    for i in range(count):
        price = Decimal(100 + i)

        result.append(Candle(
            open_time=i * 60000,
            open=price,
            high=price + Decimal("2"),
            low=price - Decimal("2"),
            close=price,
            volume=Decimal("10"),
            close_time=(i + 1) * 60000 - 1,
        ))

    return result


class AnalysisSnapshotTests(unittest.TestCase):

    def test_builds_all_market_snapshots(self):
        client = Mock()
        client.fetch_closed_klines.return_value = fake_candles()

        result = build_snapshot(client)

        self.assertEqual(set(result), set(SYMBOLS))

        for symbol in SYMBOLS:
            self.assertEqual(set(result[symbol]), set(INTERVALS))

    def test_all_snapshots_are_ready(self):
        client = Mock()
        client.fetch_closed_klines.return_value = fake_candles()

        result = build_snapshot(client)

        for symbol in SYMBOLS:
            for interval in INTERVALS:
                item = result[symbol][interval]

                self.assertEqual(item["status"], "READY")
                self.assertEqual(item["history_count"], 220)
                self.assertIsNotNone(item["indicators"]["ema200"])

    def test_rejects_insufficient_history(self):
        client = Mock()
        client.fetch_closed_klines.return_value = fake_candles(100)

        with self.assertRaises(ValueError):
            build_snapshot(client)

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            build_snapshot(Mock(), limit=100)

    def test_fetches_all_twenty_combinations(self):
        client = Mock()
        client.fetch_closed_klines.return_value = fake_candles()

        build_snapshot(client)

        self.assertEqual(client.fetch_closed_klines.call_count, 20)


if __name__ == "__main__":
    unittest.main()

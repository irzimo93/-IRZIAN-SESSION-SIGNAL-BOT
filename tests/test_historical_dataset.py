import unittest
from datetime import datetime, timezone
from decimal import Decimal

from src.market_data import Candle, SYMBOLS, INTERVALS
from src.historical_dataset import HistoricalDatasetBuilder


BASE = 1_800_000_000_000
INTERVAL = 5 * 60 * 1000


def candle(open_time, close=Decimal("10")):
    return Candle(
        open_time=open_time,
        open=Decimal("9"),
        high=Decimal("11"),
        low=Decimal("8"),
        close=close,
        volume=Decimal("2"),
        close_time=open_time + INTERVAL - 1,
    )


class FakeClient:
    def __init__(self, rows=None, fail=False):
        self.rows = list(rows or [])
        self.fail = fail
        self.calls = []

    def fetch_closed_klines_range(self, symbol, interval, start, end, now_ms=None):
        self.calls.append((symbol, interval))
        if self.fail:
            raise RuntimeError("simulated fetch failure")
        return list(self.rows)


def window():
    start = datetime.fromtimestamp(BASE / 1000, tz=timezone.utc)
    end = datetime.fromtimestamp((BASE + 3 * INTERVAL) / 1000, tz=timezone.utc)
    return start, end


class HistoricalDatasetTests(unittest.TestCase):
    def setUp(self):
        self.start, self.end = window()
        self.now_ms = BASE + 10 * INTERVAL

    def builder(self, rows=None, fail=False):
        return HistoricalDatasetBuilder(
            FakeClient(rows, fail), now_ms=self.now_ms
        )

    def test_ready_sorted_and_counts_exact_duplicates(self):
        result = self.builder([
            candle(BASE + INTERVAL),
            candle(BASE),
            candle(BASE),
            candle(BASE + 2 * INTERVAL),
        ]).build_dataset(SYMBOLS[0], "5m", self.start, self.end)
        self.assertEqual(result.status, "READY")
        self.assertEqual([c.open_time for c in result.candles],
                         [BASE, BASE + INTERVAL, BASE + 2 * INTERVAL])
        self.assertEqual(result.expected_count, 3)
        self.assertEqual(result.received_count, 4)
        self.assertEqual(result.valid_count, 3)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.gap_count, 0)

    def test_missing_candle_is_partial(self):
        result = self.builder([candle(BASE), candle(BASE + 2 * INTERVAL)]).build_dataset(
            SYMBOLS[0], "5m", self.start, self.end
        )
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.gap_count, 1)

    def test_conflicting_duplicate_is_invalid(self):
        result = self.builder([
            candle(BASE), candle(BASE, Decimal("10.5")),
            candle(BASE + INTERVAL), candle(BASE + 2 * INTERVAL),
        ]).build_dataset(SYMBOLS[0], "5m", self.start, self.end)
        self.assertEqual(result.status, "INVALID")
        self.assertIn("Conflicting duplicate", result.error)

    def test_fetch_failure_is_pair_local(self):
        client = FakeClient(fail=True)
        results = HistoricalDatasetBuilder(client, now_ms=self.now_ms).build_all(
            self.start, self.end
        )
        self.assertEqual(len(results), len(SYMBOLS) * len(INTERVALS))
        self.assertTrue(all(item.status == "INVALID" for item in results.values()))

    def test_naive_datetime_rejected(self):
        naive = datetime.fromtimestamp(BASE / 1000)
        with self.assertRaises(ValueError):
            self.builder().build_dataset(SYMBOLS[0], "5m", naive, self.end)

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            self.builder().build_dataset(SYMBOLS[0], "5m", self.end, self.start)

    def test_invalid_ohlc_is_invalid(self):
        bad = Candle(BASE, Decimal("9"), Decimal("8"), Decimal("7"),
                     Decimal("9"), Decimal("1"), BASE + INTERVAL - 1)
        result = self.builder([bad]).build_dataset(SYMBOLS[0], "5m", self.start, self.end)
        self.assertEqual(result.status, "INVALID")

    def test_all_pairs_are_attempted_after_individual_failure(self):
        class OnePairFails(FakeClient):
            def fetch_closed_klines_range(inner, symbol, interval, start, end, now_ms=None):
                inner.calls.append((symbol, interval))
                if (symbol, interval) == (SYMBOLS[0], INTERVALS[0]):
                    raise RuntimeError("one pair failed")
                return []
        client = OnePairFails()
        results = HistoricalDatasetBuilder(client, now_ms=self.now_ms).build_all(
            self.start, self.end
        )
        self.assertEqual(len(client.calls), len(SYMBOLS) * len(INTERVALS))
        self.assertEqual(results[(SYMBOLS[0], INTERVALS[0])].status, "INVALID")
        self.assertEqual(results[(SYMBOLS[0], INTERVALS[1])].status, "PARTIAL")


if __name__ == "__main__":
    unittest.main()

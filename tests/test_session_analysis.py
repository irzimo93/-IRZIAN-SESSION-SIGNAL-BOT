import unittest
from datetime import date
from decimal import Decimal

from src.market_data import Candle
from src.session_analysis import (
    session_bounds_utc,
    filter_session_candles,
    analyze_session,
)


class SessionAnalysisTests(unittest.TestCase):

    def make_candles(self, session, day, interval):
        start, _ = session_bounds_utc(session, day)

        minutes = {
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
        }[interval]

        count = 240 // minutes
        start_ms = int(start.timestamp() * 1000)

        return [
            Candle(
                open_time=start_ms + i * minutes * 60 * 1000,
                close_time=start_ms + (i + 1) * minutes * 60 * 1000 - 1,
                open=Decimal("100"),
                high=Decimal("102"),
                low=Decimal("98"),
                close=Decimal("101"),
                volume=Decimal("2"),
            )
            for i in range(count)
        ]

    def test_london_dst(self):
        winter, _ = session_bounds_utc(
            "LONDON", date(2026, 1, 15)
        )
        summer, _ = session_bounds_utc(
            "LONDON", date(2026, 7, 15)
        )

        self.assertEqual(winter.hour, 8)
        self.assertEqual(summer.hour, 7)

    def test_new_york_dst(self):
        winter, _ = session_bounds_utc(
            "NEW_YORK", date(2026, 1, 15)
        )
        summer, _ = session_bounds_utc(
            "NEW_YORK", date(2026, 7, 15)
        )

        self.assertEqual(winter.hour, 13)
        self.assertEqual(summer.hour, 12)

    def test_all_intervals_complete(self):
        day = date(2026, 7, 15)

        for interval, expected in [
            ("5m", 48),
            ("15m", 16),
            ("30m", 8),
            ("1h", 4),
        ]:
            with self.subTest(interval=interval):
                candles = self.make_candles(
                    "LONDON", day, interval
                )
                result = analyze_session(
                    candles, "LONDON", day, interval
                )
                self.assertEqual(
                    result["candle_count"], expected
                )
                self.assertEqual(result["status"], "READY")

    def test_incomplete_session_rejected(self):
        day = date(2026, 7, 15)
        candles = self.make_candles("LONDON", day, "15m")

        with self.assertRaises(ValueError):
            analyze_session(
                candles[:-1], "LONDON", day, "15m"
            )

    def test_irregular_timestamps_rejected(self):
        day = date(2026, 7, 15)
        candles = self.make_candles("LONDON", day, "15m")

        candles[5] = Candle(
            open_time=candles[5].open_time + 60000,
            close_time=candles[5].close_time,
            open=candles[5].open,
            high=candles[5].high,
            low=candles[5].low,
            close=candles[5].close,
            volume=candles[5].volume,
        )

        with self.assertRaises(ValueError):
            analyze_session(
                candles, "LONDON", day, "15m"
            )

    def test_session_calculations(self):
        day = date(2026, 7, 15)
        candles = self.make_candles(
            "LONDON", day, "1h"
        )

        result = analyze_session(
            candles, "LONDON", day, "1h"
        )

        self.assertEqual(result["open"], Decimal("100"))
        self.assertEqual(result["high"], Decimal("102"))
        self.assertEqual(result["low"], Decimal("98"))
        self.assertEqual(result["close"], Decimal("101"))
        self.assertEqual(result["volume"], Decimal("8"))
        self.assertEqual(result["change_pct"], Decimal("1"))
        self.assertEqual(result["range_pct"], Decimal("4"))


if __name__ == "__main__":
    unittest.main()

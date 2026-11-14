import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from src.market_data import MarketDataClient, Candle


def make_row(open_time, close_time, close="10"):
    return [
        open_time, "9", "11", "8", close,
        "100", close_time, "0", 10, "0", "0", "0"
    ]


class MarketDataRangeTests(unittest.TestCase):

    def make_client(self, rows):
        session = Mock()
        response = Mock()
        response.json.return_value = rows
        session.get.return_value = response
        return MarketDataClient(session), session

    def test_fetches_only_closed_candles_inside_range(self):
        start = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 11, 8, 10, tzinfo=timezone.utc)

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        rows = [
            make_row(start_ms - 300000, start_ms - 1),
            make_row(start_ms, start_ms + 299999),
            make_row(start_ms + 300000, start_ms + 599999),
            make_row(end_ms, end_ms + 299999),
        ]

        client, session = self.make_client(rows)

        result = client.fetch_closed_klines_range(
            "ADAUSDT", "5m", start, end,
            now_ms=end_ms + 1,
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(item, Candle) for item in result))
        self.assertEqual(
            [item.open_time for item in result],
            [start_ms, start_ms + 300000],
        )

        call = session.get.call_args
        self.assertEqual(
            call.kwargs["params"],
            {
                "symbol": "ADAUSDT",
                "interval": "5m",
                "startTime": start_ms,
                "endTime": end_ms - 1,
                "limit": 1500,
            },
        )
        self.assertEqual(call.kwargs["timeout"], 20)

    def test_converts_timezone_aware_datetimes_to_utc(self):
        start = datetime(
            2026, 11, 11, 10, 0,
            tzinfo=timezone(timedelta(hours=2)),
        )
        end = datetime(
            2026, 11, 11, 10, 10,
            tzinfo=timezone(timedelta(hours=2)),
        )

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        client, session = self.make_client([
            make_row(start_ms, start_ms + 299999)
        ])

        client.fetch_closed_klines_range(
            "ADAUSDT", "5m", start, end,
            now_ms=end_ms + 1,
        )

        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["startTime"], start_ms)
        self.assertEqual(params["endTime"], end_ms - 1)

    def test_excludes_candle_not_closed_at_now_ms(self):
        start = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        client, _ = self.make_client([
            make_row(start_ms, end_ms - 1)
        ])

        with self.assertRaises(ValueError):
            client.fetch_closed_klines_range(
                "ADAUSDT", "5m", start, end,
                now_ms=end_ms - 1,
            )

    def test_rejects_naive_datetime(self):
        client, _ = self.make_client([])
        start = datetime(2026, 11, 11, 8, 0)
        end = datetime(2026, 11, 11, 8, 5)

        with self.assertRaises(ValueError):
            client.fetch_closed_klines_range(
                "ADAUSDT", "5m", start, end
            )

    def test_rejects_invalid_time_range(self):
        client, _ = self.make_client([])
        start = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)

        with self.assertRaises(ValueError):
            client.fetch_closed_klines_range(
                "ADAUSDT", "5m", start, start
            )

    def test_rejects_unknown_symbol(self):
        client, _ = self.make_client([])
        start = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)

        with self.assertRaises(ValueError):
            client.fetch_closed_klines_range(
                "BTCUSDT", "5m", start, end
            )

    def test_rejects_invalid_ohlc(self):
        start = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)
        start_ms = int(start.timestamp() * 1000)

        bad = make_row(start_ms, start_ms + 299999)
        bad[2] = "8"

        client, _ = self.make_client([bad])

        with self.assertRaises(ValueError):
            client.fetch_closed_klines_range(
                "ADAUSDT", "5m", start, end,
                now_ms=int(end.timestamp() * 1000) + 1,
            )

    def test_rejects_invalid_now_ms(self):
        client, _ = self.make_client([])
        start = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)

        with self.assertRaises(ValueError):
            client.fetch_closed_klines_range(
                "ADAUSDT", "5m", start, end, now_ms=True
            )


if __name__ == "__main__":
    unittest.main()

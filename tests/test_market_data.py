import unittest
from unittest.mock import Mock

from src.market_data import MarketDataClient, Candle


def make_row(close="10"):
    return [
        1000, "9", "11", "8", close,
        "100", 1999, "0", 10, "0", "0", "0"
    ]


class MarketDataTests(unittest.TestCase):

    def make_client(self, rows):
        session = Mock()
        response = Mock()
        response.json.return_value = rows
        session.get.return_value = response
        return MarketDataClient(session), session

    def test_returns_closed_candles_only(self):
        client, _ = self.make_client([
            make_row(), make_row("10.5"), make_row("11")
        ])

        result = client.fetch_closed_klines("ADAUSDT", "5m")

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], Candle)

    def test_decimal_prices(self):
        client, _ = self.make_client([
            make_row(), make_row("10.5")
        ])

        result = client.fetch_closed_klines("ADAUSDT", "15m")

        self.assertEqual(str(result[0].close), "10")

    def test_rejects_unknown_symbol(self):
        client, _ = self.make_client([])

        with self.assertRaises(ValueError):
            client.fetch_closed_klines("BTCUSDT", "5m")

    def test_rejects_invalid_ohlc(self):
        bad = make_row()
        bad[2] = "8"

        client, _ = self.make_client([bad, make_row()])

        with self.assertRaises(ValueError):
            client.fetch_closed_klines("ADAUSDT", "5m")

    def test_rejects_invalid_limit(self):
        client, _ = self.make_client([])

        with self.assertRaises(ValueError):
            client.fetch_closed_klines("ADAUSDT", "5m", 1)


if __name__ == "__main__":
    unittest.main()

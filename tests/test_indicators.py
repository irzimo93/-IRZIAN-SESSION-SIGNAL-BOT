import unittest
from decimal import Decimal

from src.market_data import Candle
from src.indicators import calculate_indicators, ema_series


def make_candles(count, flat=False):
    candles = []

    for i in range(count):
        close = Decimal("100") if flat else Decimal(100 + i)
        candles.append(Candle(
            open_time=i * 60000,
            open=close,
            high=close + Decimal("2"),
            low=close - Decimal("2"),
            close=close,
            volume=Decimal("10"),
            close_time=(i + 1) * 60000 - 1,
        ))

    return candles


class IndicatorTests(unittest.TestCase):

    def test_ema_warmup(self):
        values = [Decimal(x) for x in ("1", "2", "3", "4")]
        result = ema_series(values, 3)

        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertEqual(result[2], Decimal("2"))
        self.assertIsNotNone(result[3])

    def test_rsi_flat_market(self):
        result = calculate_indicators(make_candles(220, flat=True))
        self.assertEqual(result["rsi14"], Decimal("50"))

    def test_rsi_rising_market(self):
        result = calculate_indicators(make_candles(220))
        self.assertEqual(result["rsi14"], Decimal("100"))

    def test_ema200_available_after_warmup(self):
        result = calculate_indicators(make_candles(220))
        self.assertIsNotNone(result["ema200"])

    def test_macd_values_available(self):
        result = calculate_indicators(make_candles(220))
        self.assertIsNotNone(result["macd"])
        self.assertIsNotNone(result["macd_signal"])
        self.assertIsNotNone(result["macd_histogram"])

    def test_vwap_and_atr_available(self):
        result = calculate_indicators(make_candles(220))
        self.assertIsNotNone(result["vwap"])
        self.assertIsNotNone(result["atr14"])
        self.assertGreater(result["atr14"], Decimal("0"))

    def test_insufficient_history_has_no_ema200(self):
        result = calculate_indicators(make_candles(100))
        self.assertIsNone(result["ema200"])

    def test_empty_candles_rejected(self):
        with self.assertRaises(ValueError):
            calculate_indicators([])


if __name__ == "__main__":
    unittest.main()

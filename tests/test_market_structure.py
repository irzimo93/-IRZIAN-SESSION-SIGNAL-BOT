import unittest
from decimal import Decimal

from src.market_data import Candle
from src.market_structure import (
    find_swings,
    cluster_levels,
    build_market_structure,
)


def make_candle(index, high, low, close=None):
    close = close if close is not None else (high + low) / 2

    return Candle(
        open_time=index,
        open=Decimal(str(close)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal("100"),
        close_time=index + 1,
    )


class TestMarketStructure(unittest.TestCase):

    def setUp(self):
        self.candles = [
            make_candle(0, 11, 9, 10),
            make_candle(1, 12, 8, 10),
            make_candle(2, 15, 9, 12),
            make_candle(3, 12, 7, 10),
            make_candle(4, 11, 5, 8),
            make_candle(5, 12, 8, 10),
            make_candle(6, 13, 9, 11),
        ]

    def test_find_swing_high(self):
        result = find_swings(self.candles, left=1, right=1)
        self.assertIn(2, [item["index"] for item in result["swing_highs"]])

    def test_find_swing_low(self):
        result = find_swings(self.candles, left=1, right=1)
        self.assertIn(4, [item["index"] for item in result["swing_lows"]])

    def test_cluster_levels(self):
        result = cluster_levels(
            ["100", "100.2", "102"],
            tolerance="0.5",
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["touches"], 2)
        self.assertEqual(result[0]["price"], Decimal("100.1"))

    def test_cluster_empty_levels(self):
        self.assertEqual(cluster_levels([], "0.5"), [])

    def test_build_market_structure(self):
        result = build_market_structure(
            self.candles,
            atr=Decimal("2"),
            left=1,
            right=1,
        )
        self.assertIn("supports", result)
        self.assertIn("resistances", result)
        self.assertIn("distance_atr", result["supports"][0])

    def test_invalid_atr(self):
        with self.assertRaises(ValueError):
            build_market_structure(self.candles, atr=0)

    def test_invalid_swing_parameters(self):
        with self.assertRaises(ValueError):
            find_swings(self.candles, left=0, right=1)


if __name__ == "__main__":
    unittest.main()

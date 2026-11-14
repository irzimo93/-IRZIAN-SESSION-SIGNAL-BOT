from src.market_data import (
    MarketDataClient,
    SYMBOLS,
    INTERVALS,
)
from src.indicators import calculate_indicators
from src.market_structure import build_market_structure


REQUIRED_HISTORY = 200


def build_snapshot(client=None, limit=250):
    client = client or MarketDataClient()

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Limit must be an integer")

    if not REQUIRED_HISTORY < limit <= 1500:
        raise ValueError("Limit must be between 201 and 1500")

    snapshot = {}

    for symbol in SYMBOLS:
        snapshot[symbol] = {}

        for interval in INTERVALS:
            candles = client.fetch_closed_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
            )

            if len(candles) < REQUIRED_HISTORY:
                raise ValueError(
                    f"Insufficient history: {symbol} {interval}"
                )

            indicators = calculate_indicators(candles)

            required = (
                "ema20", "ema50", "ema200",
                "rsi14", "macd", "macd_signal",
                "macd_histogram", "vwap", "atr14",
            )

            missing = [
                key for key in required
                if indicators[key] is None
            ]

            if missing:
                raise ValueError(
                    f"Missing indicators for {symbol} {interval}: "
                    f"{missing}"
                )

            market_structure = build_market_structure(
                candles=candles,
                atr=indicators["atr14"],
            )
            last = candles[-1]

            snapshot[symbol][interval] = {
                "candle_time": last.open_time,
                "close": last.close,
                "volume": last.volume,
                "market_structure": market_structure,
                "indicators": indicators,
                "history_count": len(candles),
                "status": "READY",
            }

    return snapshot

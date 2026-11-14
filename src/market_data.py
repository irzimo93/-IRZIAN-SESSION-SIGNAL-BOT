from dataclasses import dataclass
from decimal import Decimal
import requests
from datetime import datetime, timezone


BASE_URL = "https://fapi.binance.com"

SYMBOLS = (
    "ADAUSDT", "TRXUSDT", "PUMPUSDT",
    "DOGEUSDT", "GRAMUSDT",
)

INTERVALS = ("5m", "15m", "30m", "1h")


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: int


class MarketDataClient:

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def fetch_closed_klines(self, symbol, interval, limit=200):

        if symbol not in SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")

        if interval not in INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")

        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("Limit must be an integer")

        if not 2 <= limit <= 1500:
            raise ValueError("Limit must be between 2 and 1500")

        response = self.session.get(
            f"{BASE_URL}/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
            timeout=20,
        )

        response.raise_for_status()
        rows = response.json()

        if not isinstance(rows, list) or len(rows) < 2:
            raise ValueError("Insufficient kline data")

        candles = []

        # آخرین ردیف ممکن است هنوز در حال تشکیل باشد.
        for row in rows[:-1]:

            if not isinstance(row, list) or len(row) < 7:
                raise ValueError("Invalid kline structure")

            candle = Candle(
                open_time=int(row[0]),
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                close_time=int(row[6]),
            )

            values = (
                candle.open, candle.high,
                candle.low, candle.close,
                candle.volume,
            )

            if not all(value.is_finite() for value in values):
                raise ValueError("Non-finite candle value")

            if min(values[:4]) <= 0 or candle.volume < 0:
                raise ValueError("Invalid price or volume")

            if not (
                candle.low <= min(candle.open, candle.close)
                <= max(candle.open, candle.close)
                <= candle.high
            ):
                raise ValueError("Invalid OHLC values")

            candles.append(candle)

        if not candles:
            raise ValueError("No closed candles available")

        return candles

    def fetch_closed_klines_range(
        self, symbol, interval, start_time, end_time, now_ms=None
    ):
        if symbol not in SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        if interval not in INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")

        if not isinstance(start_time, datetime):
            raise ValueError("start_time must be a datetime")
        if not isinstance(end_time, datetime):
            raise ValueError("end_time must be a datetime")

        if start_time.utcoffset() is None:
            raise ValueError("start_time must be timezone-aware")
        if end_time.utcoffset() is None:
            raise ValueError("end_time must be timezone-aware")

        start_ms = int(
            start_time.astimezone(timezone.utc).timestamp() * 1000
        )
        end_ms = int(
            end_time.astimezone(timezone.utc).timestamp() * 1000
        )

        if end_ms <= start_ms:
            raise ValueError("end_time must be after start_time")

        if now_ms is None:
            now_ms = int(
                datetime.now(timezone.utc).timestamp() * 1000
            )
        elif (
            not isinstance(now_ms, int)
            or isinstance(now_ms, bool)
            or now_ms < 0
        ):
            raise ValueError("now_ms must be a non-negative integer")

        response = self.session.get(
            f"{BASE_URL}/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms - 1,
                "limit": 1500,
            },
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json()

        if not isinstance(rows, list):
            raise ValueError("Invalid kline response")

        candles = []

        for row in rows:
            if not isinstance(row, list) or len(row) < 7:
                raise ValueError("Invalid kline structure")

            candle = Candle(
                open_time=int(row[0]),
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                close_time=int(row[6]),
            )

            values = (
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )

            if not all(value.is_finite() for value in values):
                raise ValueError("Non-finite candle value")

            if min(values[:4]) <= 0 or candle.volume < 0:
                raise ValueError("Invalid price or volume")

            if not (
                candle.low <= min(candle.open, candle.close)
                <= max(candle.open, candle.close)
                <= candle.high
            ):
                raise ValueError("Invalid OHLC values")

            if start_ms <= candle.open_time < end_ms:
                if candle.close_time < now_ms:
                    candles.append(candle)

        candles.sort(key=lambda candle: candle.open_time)

        if not candles:
            raise ValueError(
                "No closed candles available in requested range"
            )

        return candles


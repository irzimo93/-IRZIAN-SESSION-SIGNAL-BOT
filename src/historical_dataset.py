"""Build validated historical candle datasets without changing market-data retrieval."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from .market_data import Candle, INTERVALS, SYMBOLS

INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
}
MAX_CANDLES_PER_REQUEST = 1500
STATUSES = ("READY", "PARTIAL", "INVALID")


@dataclass(frozen=True)
class HistoricalDataset:
    symbol: str
    interval: str
    status: str
    candles: tuple
    expected_count: int
    received_count: int
    valid_count: int
    duplicate_count: int
    gap_count: int
    actual_start: Optional[int]
    actual_end: Optional[int]
    error: Optional[str] = None


def _to_utc_ms(value, field_name):
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _expected_open_times(start_ms, end_ms, interval_ms, now_ms):
    first = ((start_ms + interval_ms - 1) // interval_ms) * interval_ms
    result = []
    current = first
    while current < end_ms and current + interval_ms - 1 < now_ms:
        result.append(current)
        current += interval_ms
    return result


def _validate_candle(candle, interval_ms):
    if not isinstance(candle, Candle):
        raise ValueError("Received object is not a Candle")
    if (not isinstance(candle.open_time, int) or isinstance(candle.open_time, bool)
            or not isinstance(candle.close_time, int) or isinstance(candle.close_time, bool)):
        raise ValueError("Candle timestamps must be integers")
    if candle.open_time < 0 or candle.close_time < 0:
        raise ValueError("Candle timestamps must be non-negative")
    if candle.open_time % interval_ms != 0:
        raise ValueError("Candle open_time is not aligned to interval")
    if candle.close_time != candle.open_time + interval_ms - 1:
        raise ValueError("Candle close_time does not match interval")
    values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
    if not all(isinstance(v, Decimal) and v.is_finite() for v in values):
        raise ValueError("Candle values must be finite Decimals")
    if min(values[:4]) <= 0 or candle.volume < 0:
        raise ValueError("Invalid price or volume")
    if not (candle.low <= min(candle.open, candle.close)
            <= max(candle.open, candle.close) <= candle.high):
        raise ValueError("Invalid OHLC values")


class HistoricalDatasetBuilder:
    """Build isolated datasets for every configured symbol/interval pair."""

    def __init__(self, market_data_client, now_ms=None):
        if not hasattr(market_data_client, "fetch_closed_klines_range"):
            raise ValueError("market_data_client lacks fetch_closed_klines_range")
        if now_ms is not None and (
            not isinstance(now_ms, int) or isinstance(now_ms, bool) or now_ms < 0
        ):
            raise ValueError("now_ms must be a non-negative integer")
        self.client = market_data_client
        self.now_ms = now_ms

    def build_dataset(self, symbol, interval, start_time, end_time):
        if symbol not in SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        if interval not in INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")
        start_ms = _to_utc_ms(start_time, "start_time")
        end_ms = _to_utc_ms(end_time, "end_time")
        if end_ms <= start_ms:
            raise ValueError("end_time must be after start_time")

        interval_ms = INTERVAL_MS[interval]
        effective_now = self.now_ms
        if effective_now is None:
            effective_now = int(datetime.now(timezone.utc).timestamp() * 1000)
        expected = _expected_open_times(start_ms, end_ms, interval_ms, effective_now)

        try:
            kwargs = {}
            if self.now_ms is not None:
                kwargs["now_ms"] = self.now_ms
            fetched = self.client.fetch_closed_klines_range(
                symbol, interval, start_time, end_time, **kwargs
            )
            if not isinstance(fetched, (list, tuple)):
                raise ValueError("Market-data client must return a list or tuple")
            raw = list(fetched)
            by_open = {}
            duplicates = 0
            for candle in raw:
                _validate_candle(candle, interval_ms)
                if not (start_ms <= candle.open_time < end_ms):
                    raise ValueError("Candle is outside requested range")
                if candle.close_time >= effective_now:
                    raise ValueError("Received candle is not closed")
                previous = by_open.get(candle.open_time)
                if previous is not None:
                    if previous != candle:
                        raise ValueError(
                            f"Conflicting duplicate at open_time={candle.open_time}"
                        )
                    duplicates += 1
                else:
                    by_open[candle.open_time] = candle

            ordered = tuple(by_open[key] for key in sorted(by_open))
            expected_set = set(expected)
            received_set = set(by_open)
            unexpected = received_set - expected_set
            if unexpected:
                raise ValueError("Received candle timestamp is not expected in range")

            gaps = len(expected_set - received_set)
            over_limit = len(expected) > MAX_CANDLES_PER_REQUEST
            status = "READY" if expected and gaps == 0 and not over_limit else "PARTIAL"
            return HistoricalDataset(
                symbol=symbol,
                interval=interval,
                status=status,
                candles=ordered,
                expected_count=len(expected),
                received_count=len(raw),
                valid_count=len(ordered),
                duplicate_count=duplicates,
                gap_count=gaps,
                actual_start=ordered[0].open_time if ordered else None,
                actual_end=ordered[-1].open_time if ordered else None,
                error=("Requested range exceeds single-request capacity"
                       if over_limit else None),
            )
        except Exception as exc:
            return HistoricalDataset(
                symbol=symbol,
                interval=interval,
                status="INVALID",
                candles=(),
                expected_count=len(expected),
                received_count=0,
                valid_count=0,
                duplicate_count=0,
                gap_count=len(expected),
                actual_start=None,
                actual_end=None,
                error=f"{type(exc).__name__}: {exc}",
            )

    def build_all(self, start_time, end_time):
        """Return one result per configured pair; failures stay pair-local."""
        results = {}
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                results[(symbol, interval)] = self.build_dataset(
                    symbol, interval, start_time, end_time
                )
        return results

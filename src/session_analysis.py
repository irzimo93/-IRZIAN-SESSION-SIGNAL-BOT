from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

from src.market_data import INTERVALS


SESSIONS = {
    "LONDON": ("Europe/London", 8, 12),
    "NEW_YORK": ("America/New_York", 8, 12),
}

INTERVAL_MINUTES = {
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
}


def session_bounds_utc(session, session_date):
    session = session.upper()

    if session not in SESSIONS:
        raise ValueError(f"Unsupported session: {session}")

    if isinstance(session_date, str):
        session_date = date.fromisoformat(session_date)

    if not isinstance(session_date, date):
        raise ValueError("session_date must be a date or ISO date string")

    timezone_name, start_hour, end_hour = SESSIONS[session]
    local_tz = ZoneInfo(timezone_name)

    start_local = datetime.combine(
        session_date, time(start_hour), tzinfo=local_tz
    )
    end_local = datetime.combine(
        session_date, time(end_hour), tzinfo=local_tz
    )

    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )


def filter_session_candles(candles, session, session_date):
    start_utc, end_utc = session_bounds_utc(
        session, session_date
    )

    start_ms = int(start_utc.timestamp() * 1000)
    end_ms = int(end_utc.timestamp() * 1000)

    return sorted(
        [
            candle for candle in candles
            if start_ms <= candle.open_time < end_ms
        ],
        key=lambda candle: candle.open_time,
    )


def analyze_session(candles, session, session_date, interval):
    if interval not in INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}")

    if not candles:
        raise ValueError("No session candles available")

    session_candles = filter_session_candles(
        candles, session, session_date
    )

    minutes = INTERVAL_MINUTES[interval]
    expected_count = 240 // minutes

    if len(session_candles) != expected_count:
        raise ValueError(
            f"Incomplete session: expected {expected_count}, "
            f"received {len(session_candles)}"
        )

    start_utc, _ = session_bounds_utc(session, session_date)
    start_ms = int(start_utc.timestamp() * 1000)
    step_ms = minutes * 60 * 1000

    expected_times = [
        start_ms + index * step_ms
        for index in range(expected_count)
    ]

    actual_times = [
        candle.open_time for candle in session_candles
    ]

    if actual_times != expected_times:
        raise ValueError("Session candle timestamps are incomplete")

    first = session_candles[0]
    last = session_candles[-1]

    session_high = max(c.high for c in session_candles)
    session_low = min(c.low for c in session_candles)
    total_volume = sum(
        (c.volume for c in session_candles), Decimal("0")
    )

    change_pct = (
        (last.close - first.open) / first.open
    ) * Decimal("100")

    range_pct = (
        (session_high - session_low) / first.open
    ) * Decimal("100")

    return {
        "session": session.upper(),
        "date": str(session_date),
        "interval": interval,
        "status": "READY",
        "candle_count": len(session_candles),
        "expected_count": expected_count,
        "open": first.open,
        "high": session_high,
        "low": session_low,
        "close": last.close,
        "volume": total_volume,
        "change_pct": change_pct,
        "range_pct": range_pct,
    }

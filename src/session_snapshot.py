from datetime import date

from src.market_data import MarketDataClient, SYMBOLS, INTERVALS
from src.session_analysis import analyze_session


def build_session_snapshot(
    session,
    session_date,
    client=None,
    limit=1500,
):
    if not isinstance(session_date, date):
        raise ValueError("session_date must be a date")

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer")

    if not 2 <= limit <= 1500:
        raise ValueError("limit must be between 2 and 1500")

    client = client or MarketDataClient()

    results = {}
    errors = []

    for symbol in SYMBOLS:
        results[symbol] = {}

        for interval in INTERVALS:
            try:
                candles = client.fetch_closed_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                )

                analysis = analyze_session(
                    candles=candles,
                    session=session,
                    session_date=session_date,
                    interval=interval,
                )

                results[symbol][interval] = {
                    "status": "READY",
                    "analysis": analysis,
                }

            except Exception as exc:
                message = str(exc)

                results[symbol][interval] = {
                    "status": "INCOMPLETE",
                    "error": message,
                }

                errors.append({
                    "symbol": symbol,
                    "interval": interval,
                    "error": message,
                })

    total = len(SYMBOLS) * len(INTERVALS)
    ready = total - len(errors)

    return {
        "session": session,
        "session_date": session_date,
        "status": "READY" if ready == total else "PARTIAL",
        "total": total,
        "ready": ready,
        "incomplete": len(errors),
        "results": results,
        "errors": errors,
    }

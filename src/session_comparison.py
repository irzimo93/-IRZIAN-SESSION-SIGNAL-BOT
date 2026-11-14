from decimal import Decimal, InvalidOperation


def _decimal(value, field):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid metric: {field}")

    if not result.is_finite():
        raise ValueError(f"Non-finite metric: {field}")

    return result


def _direction(change):
    if change > 0:
        return "BULLISH"
    if change < 0:
        return "BEARISH"
    return "FLAT"


def compare_sessions(london_snapshot, new_york_snapshot):
    if not isinstance(london_snapshot, dict):
        raise ValueError("Invalid London snapshot")

    if not isinstance(new_york_snapshot, dict):
        raise ValueError("Invalid New York snapshot")

    if london_snapshot.get("session_date") != new_york_snapshot.get("session_date"):
        raise ValueError("Session dates must match")

    if london_snapshot.get("session") == new_york_snapshot.get("session"):
        raise ValueError("Snapshots must represent different sessions")

    london_results = london_snapshot.get("results")
    new_york_results = new_york_snapshot.get("results")

    if not isinstance(london_results, dict) or not isinstance(new_york_results, dict):
        raise ValueError("Invalid snapshot results")

    comparisons = {}
    errors = []

    symbols = sorted(set(london_results) | set(new_york_results))

    for symbol in symbols:
        comparisons[symbol] = {}

        london_intervals = london_results.get(symbol, {})
        ny_intervals = new_york_results.get(symbol, {})

        intervals = sorted(set(london_intervals) | set(ny_intervals))

        for interval in intervals:
            london_item = london_intervals.get(interval)
            ny_item = ny_intervals.get(interval)

            try:
                if not isinstance(london_item, dict) or london_item.get("status") != "READY":
                    raise ValueError("London session data is incomplete")

                if not isinstance(ny_item, dict) or ny_item.get("status") != "READY":
                    raise ValueError("New York session data is incomplete")

                london = london_item.get("analysis")
                new_york = ny_item.get("analysis")

                if not isinstance(london, dict) or not isinstance(new_york, dict):
                    raise ValueError("Missing session analysis")

                london_change = _decimal(london["change_pct"], "London change_pct")
                ny_change = _decimal(new_york["change_pct"], "New York change_pct")

                london_range = _decimal(london["range_pct"], "London range_pct")
                ny_range = _decimal(new_york["range_pct"], "New York range_pct")

                london_volume = _decimal(london["volume"], "London volume")
                ny_volume = _decimal(new_york["volume"], "New York volume")

                if london_volume < 0 or ny_volume < 0:
                    raise ValueError("Volume cannot be negative")

                volume_difference = ny_volume - london_volume
                volume_change_pct = (
                    (volume_difference / london_volume) * Decimal("100")
                    if london_volume > 0 else None
                )

                comparisons[symbol][interval] = {
                    "status": "READY",
                    "london_direction": _direction(london_change),
                    "new_york_direction": _direction(ny_change),
                    "direction_match": _direction(london_change) == _direction(ny_change),
                    "change_pct_difference": ny_change - london_change,
                    "range_pct_difference": ny_range - london_range,
                    "volume_difference": volume_difference,
                    "volume_change_pct": volume_change_pct,
                }

            except (KeyError, ValueError) as exc:
                message = str(exc)

                comparisons[symbol][interval] = {
                    "status": "INCOMPLETE",
                    "error": message,
                }

                errors.append({
                    "symbol": symbol,
                    "interval": interval,
                    "error": message,
                })

    total = sum(len(items) for items in comparisons.values())
    incomplete = len(errors)
    ready = total - incomplete

    return {
        "session_date": london_snapshot["session_date"],
        "status": "READY" if total > 0 and incomplete == 0 else "PARTIAL",
        "total": total,
        "ready": ready,
        "incomplete": incomplete,
        "comparisons": comparisons,
        "errors": errors,
    }

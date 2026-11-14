from decimal import Decimal, InvalidOperation


VALID_DIRECTIONS = {"BULLISH", "BEARISH", "FLAT"}
VALID_STATUSES = {"READY", "PARTIAL"}


def _decimal(value, field):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid metric: {field}")

    if not result.is_finite():
        raise ValueError(f"Non-finite metric: {field}")

    return result


def _session_dominance(range_difference):
    if range_difference > 0:
        return "NEW_YORK"
    if range_difference < 0:
        return "LONDON"
    return "BALANCED"


def _direction_alignment(london, new_york):
    if london == new_york:
        return "NEUTRAL" if london == "FLAT" else "ALIGNED"

    if london == "FLAT" or new_york == "FLAT":
        return "MIXED"

    return "DIVERGENT"


def _volume_behavior(volume_difference):
    if volume_difference > 0:
        return "NEW_YORK_HIGHER"
    if volume_difference < 0:
        return "LONDON_HIGHER"
    return "EQUAL"


def _analyze_comparison(item):
    if not isinstance(item, dict) or item.get("status") != "READY":
        raise ValueError("Comparison data is incomplete")

    london_direction = item.get("london_direction")
    new_york_direction = item.get("new_york_direction")

    if london_direction not in VALID_DIRECTIONS:
        raise ValueError("Invalid London direction")

    if new_york_direction not in VALID_DIRECTIONS:
        raise ValueError("Invalid New York direction")

    direction_match = item.get("direction_match")

    if not isinstance(direction_match, bool):
        raise ValueError("Invalid direction_match")

    expected_match = london_direction == new_york_direction

    if direction_match != expected_match:
        raise ValueError("Inconsistent direction_match")

    change_difference = _decimal(
        item.get("change_pct_difference"),
        "change_pct_difference",
    )
    range_difference = _decimal(
        item.get("range_pct_difference"),
        "range_pct_difference",
    )
    volume_difference = _decimal(
        item.get("volume_difference"),
        "volume_difference",
    )

    volume_change_pct = item.get("volume_change_pct")

    if volume_change_pct is not None:
        volume_change_pct = _decimal(
            volume_change_pct,
            "volume_change_pct",
        )

    return {
        "status": "READY",
        "session_dominance": _session_dominance(range_difference),
        "direction_alignment": _direction_alignment(
            london_direction,
            new_york_direction,
        ),
        "london_direction": london_direction,
        "new_york_direction": new_york_direction,
        "range_behavior": (
            "NEW_YORK_WIDER"
            if range_difference > 0
            else "LONDON_WIDER"
            if range_difference < 0
            else "EQUAL"
        ),
        "volume_behavior": _volume_behavior(volume_difference),
        "change_pct_difference": change_difference,
        "range_pct_difference": range_difference,
        "volume_difference": volume_difference,
        "volume_change_pct": volume_change_pct,
    }


def analyze_session_intelligence(comparison_snapshot):
    if not isinstance(comparison_snapshot, dict):
        raise ValueError("Invalid comparison snapshot")

    session_date = comparison_snapshot.get("session_date")

    if session_date is None:
        raise ValueError("Missing session_date")

    source_status = comparison_snapshot.get("status")

    if source_status not in VALID_STATUSES:
        raise ValueError("Invalid comparison snapshot status")

    comparisons = comparison_snapshot.get("comparisons")

    if not isinstance(comparisons, dict):
        raise ValueError("Invalid comparisons")

    intelligence = {}
    errors = []
    total = 0
    ready = 0

    for symbol, intervals in comparisons.items():
        if not isinstance(intervals, dict):
            raise ValueError(f"Invalid intervals for {symbol}")

        intelligence[symbol] = {}

        for interval, item in intervals.items():
            total += 1

            try:
                result = _analyze_comparison(item)
                intelligence[symbol][interval] = result
                ready += 1

            except (ValueError, TypeError) as exc:
                message = str(exc)

                intelligence[symbol][interval] = {
                    "status": "INCOMPLETE",
                    "error": message,
                }

                errors.append({
                    "symbol": symbol,
                    "interval": interval,
                    "error": message,
                })

    incomplete = total - ready

    final_status = (
        "READY"
        if total > 0
        and incomplete == 0
        and source_status == "READY"
        else "PARTIAL"
    )

    return {
        "session_date": session_date,
        "status": final_status,
        "source_status": source_status,
        "total": total,
        "ready": ready,
        "incomplete": incomplete,
        "intelligence": intelligence,
        "errors": errors,
    }

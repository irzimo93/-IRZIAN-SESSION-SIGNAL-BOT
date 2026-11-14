from decimal import Decimal, InvalidOperation


def _decimal_text(value, field):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid report metric: {field}")

    if not number.is_finite():
        raise ValueError(f"Non-finite report metric: {field}")

    return f"{number:.2f}"


def _validate_date(name, snapshot, expected_date):
    if not isinstance(snapshot, dict):
        raise ValueError(f"Invalid {name} snapshot")

    if snapshot.get("session_date") != expected_date:
        raise ValueError(f"{name} session date mismatch")


def _session_metrics(snapshot, symbol, interval):
    result = snapshot.get("results", {}).get(symbol, {}).get(interval)

    if not isinstance(result, dict) or result.get("status") != "READY":
        return None

    analysis = result.get("analysis")

    if not isinstance(analysis, dict):
        return None

    required = ("change_pct", "range_pct", "volume")

    try:
        return {
            field: _decimal_text(analysis.get(field), field)
            for field in required
        }
    except ValueError:
        return None


def _comparison_metrics(comparison, intelligence):
    if not isinstance(comparison, dict):
        return None

    if comparison.get("status") != "READY":
        return None

    if not isinstance(intelligence, dict):
        return None

    if intelligence.get("status") != "READY":
        return None

    try:
        return {
            "change": _decimal_text(
                comparison.get("change_pct_difference"),
                "change_pct_difference",
            ),
            "range": _decimal_text(
                comparison.get("range_pct_difference"),
                "range_pct_difference",
            ),
            "volume": _decimal_text(
                comparison.get("volume_difference"),
                "volume_difference",
            ),
        }
    except ValueError:
        return None


def build_session_report(
    london_snapshot,
    new_york_snapshot,
    comparison_snapshot,
    intelligence_snapshot,
):
    if not isinstance(comparison_snapshot, dict):
        raise ValueError("Invalid comparison snapshot")

    if not isinstance(intelligence_snapshot, dict):
        raise ValueError("Invalid intelligence snapshot")

    session_date = comparison_snapshot.get("session_date")

    if not session_date:
        raise ValueError("Missing session date")

    _validate_date("London", london_snapshot, session_date)
    _validate_date("New York", new_york_snapshot, session_date)
    _validate_date("Intelligence", intelligence_snapshot, session_date)

    if not isinstance(comparison_snapshot.get("comparisons"), dict):
        raise ValueError("Invalid comparison data")

    if not isinstance(intelligence_snapshot.get("intelligence"), dict):
        raise ValueError("Invalid intelligence data")

    lines = [
        "IRZIAN SESSION INTELLIGENCE",
        f"Date: {session_date}",
        "",
        "SESSION STATUS",
        (
            f"London: {london_snapshot.get('status', 'UNKNOWN')} "
            f"({london_snapshot.get('ready', 0)}/"
            f"{london_snapshot.get('total', 0)} ready)"
        ),
        (
            f"New York: {new_york_snapshot.get('status', 'UNKNOWN')} "
            f"({new_york_snapshot.get('ready', 0)}/"
            f"{new_york_snapshot.get('total', 0)} ready)"
        ),
        (
            f"Comparison: {comparison_snapshot.get('status', 'UNKNOWN')}"
        ),
        (
            f"Intelligence: {intelligence_snapshot.get('status', 'UNKNOWN')} "
            f"({intelligence_snapshot.get('ready', 0)}/"
            f"{intelligence_snapshot.get('total', 0)} ready)"
        ),
        "",
        "SYMBOL ANALYSIS",
    ]

    comparisons = comparison_snapshot["comparisons"]
    intelligence = intelligence_snapshot["intelligence"]

    total = 0
    complete = 0

    for symbol, intervals in comparisons.items():
        if not isinstance(intervals, dict):
            continue

        lines.extend(["", f"[{symbol}]"])

        for interval, comparison in intervals.items():
            total += 1

            insight = intelligence.get(symbol, {}).get(interval)

            london = _session_metrics(
                london_snapshot, symbol, interval
            )
            new_york = _session_metrics(
                new_york_snapshot, symbol, interval
            )
            metrics = _comparison_metrics(comparison, insight)

            if london is None or new_york is None or metrics is None:
                lines.append(f"{interval}: INCOMPLETE")
                continue

            complete += 1

            lines.extend([
                f"{interval}: READY",
                (
                    f"  London: change {london['change_pct']}% | "
                    f"range {london['range_pct']}% | "
                    f"volume {london['volume']}"
                ),
                (
                    f"  New York: change {new_york['change_pct']}% | "
                    f"range {new_york['range_pct']}% | "
                    f"volume {new_york['volume']}"
                ),
                (
                    f"  Dominance: "
                    f"{insight['session_dominance']}"
                ),
                (
                    f"  Direction: "
                    f"{insight['direction_alignment']} "
                    f"({insight['london_direction']} / "
                    f"{insight['new_york_direction']})"
                ),
                (
                    f"  Range: {insight['range_behavior']} | "
                    f"Difference: {metrics['range']}%"
                ),
                (
                    f"  Volume: {insight['volume_behavior']} | "
                    f"Difference: {metrics['volume']}"
                ),
                f"  Change difference: {metrics['change']}%",
            ])

    lines.extend([
        "",
        "REPORT SUMMARY",
        f"Complete: {complete}/{total}",
        f"Incomplete: {total - complete}/{total}",
        "",
        "READ ONLY - NO TRADE EXECUTION",
    ])

    return "\n".join(lines)

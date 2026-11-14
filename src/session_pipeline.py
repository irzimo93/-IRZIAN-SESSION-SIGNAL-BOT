import json
import os
from datetime import date, datetime
from pathlib import Path

from src.historical_dataset import HistoricalDatasetBuilder
from src.market_data import INTERVALS, SYMBOLS, MarketDataClient
from src.session_analysis import analyze_session, session_bounds_utc
from src.session_comparison import compare_sessions
from src.session_intelligence import analyze_session_intelligence
from src.session_report import build_session_report
from src.telegram_delivery import send_telegram_report


EXPECTED_TOTAL = len(SYMBOLS) * len(INTERVALS)


class SessionPipelineError(Exception):
    """Safe error raised by the session pipeline."""


def _normalize_date(value):
    if isinstance(value, datetime):
        raise ValueError("session_date must be a date, not datetime")
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise ValueError("session_date must use YYYY-MM-DD") from None
    if not isinstance(value, date):
        raise ValueError("session_date must be a date or ISO date string")
    return value


def _build_one_session(session, session_date, builder):
    start_utc, end_utc = session_bounds_utc(session, session_date)

    snapshot = {
        "session": session,
        "session_date": session_date,
        "status": "PARTIAL",
        "total": EXPECTED_TOTAL,
        "ready": 0,
        "incomplete": 0,
        "results": {},
        "errors": [],
    }

    for symbol in SYMBOLS:
        snapshot["results"][symbol] = {}

        for interval in INTERVALS:
            try:
                dataset = builder.build_dataset(
                    symbol=symbol,
                    interval=interval,
                    start_time=start_utc,
                    end_time=end_utc,
                )

                if dataset.status != "READY":
                    raise ValueError(
                        f"Historical dataset status: {dataset.status}"
                    )

                if (
                    dataset.expected_count <= 0
                    or dataset.valid_count != dataset.expected_count
                    or dataset.gap_count != 0
                ):
                    raise ValueError("Historical dataset is incomplete")

                analysis = analyze_session(
                    candles=dataset.candles,
                    session=session,
                    session_date=session_date,
                    interval=interval,
                )

                if not isinstance(analysis, dict):
                    raise ValueError("Invalid session analysis")
                if analysis.get("status") != "READY":
                    raise ValueError("Session analysis is not READY")

                snapshot["results"][symbol][interval] = {
                    "status": "READY",
                    "analysis": analysis,
                }
                snapshot["ready"] += 1

            except Exception as exc:
                message = str(exc) or type(exc).__name__
                snapshot["results"][symbol][interval] = {
                    "status": "INCOMPLETE",
                    "error": message,
                }
                snapshot["errors"].append({
                    "symbol": symbol,
                    "interval": interval,
                    "error": message,
                })

    snapshot["incomplete"] = EXPECTED_TOTAL - snapshot["ready"]
    if snapshot["ready"] == EXPECTED_TOTAL:
        snapshot["status"] = "READY"

    return snapshot


def _snapshot_is_ready(snapshot):
    return (
        isinstance(snapshot, dict)
        and snapshot.get("status") == "READY"
        and snapshot.get("total") == EXPECTED_TOTAL
        and snapshot.get("ready") == EXPECTED_TOTAL
        and snapshot.get("incomplete") == 0
        and isinstance(snapshot.get("results"), dict)
    )


def _intelligence_is_ready(snapshot):
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("status") != "READY":
        return False
    if snapshot.get("source_status") != "READY":
        return False
    if snapshot.get("total") != EXPECTED_TOTAL:
        return False
    if snapshot.get("ready") != EXPECTED_TOTAL:
        return False
    if snapshot.get("incomplete") != 0:
        return False
    return True


def _default_state_file():
    return (
        Path.home()
        / ".irzian"
        / "session-signal-bot"
        / "telegram_delivery_state.json"
    )


def _load_delivery_state(state_file):
    path = Path(state_file)
    if not path.exists():
        return {"delivered_dates": []}

    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise SessionPipelineError(
            "Delivery state cannot be read; sending was stopped."
        ) from None

    if (
        not isinstance(state, dict)
        or not isinstance(state.get("delivered_dates"), list)
        or any(
            not isinstance(item, str)
            for item in state["delivered_dates"]
        )
    ):
        raise SessionPipelineError(
            "Delivery state is invalid; sending was stopped."
        )

    return state


def _save_delivery_state(state_file, state):
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")

    try:
        temporary.write_text(
            json.dumps(state, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def run_session_pipeline(
    session_date,
    client=None,
    send=False,
    env_file=None,
    state_file=None,
    now_ms=None,
):
    session_date = _normalize_date(session_date)

    if not isinstance(send, bool):
        raise ValueError("send must be True or False")

    if client is None:
        client = MarketDataClient()

    builder = HistoricalDatasetBuilder(
        market_data_client=client,
        now_ms=now_ms,
    )

    london_snapshot = _build_one_session(
        "LONDON", session_date, builder
    )
    new_york_snapshot = _build_one_session(
        "NEW_YORK", session_date, builder
    )

    comparison_snapshot = compare_sessions(
        london_snapshot,
        new_york_snapshot,
    )

    intelligence_snapshot = analyze_session_intelligence(
        comparison_snapshot
    )

    report = build_session_report(
        london_snapshot,
        new_york_snapshot,
        comparison_snapshot,
        intelligence_snapshot,
    )

    report_ready = (
        _snapshot_is_ready(london_snapshot)
        and _snapshot_is_ready(new_york_snapshot)
        and comparison_snapshot.get("status") == "READY"
        and comparison_snapshot.get("total") == EXPECTED_TOTAL
        and comparison_snapshot.get("ready") == EXPECTED_TOTAL
        and comparison_snapshot.get("incomplete") == 0
        and _intelligence_is_ready(intelligence_snapshot)
        and isinstance(report, str)
        and bool(report.strip())
    )

    result = {
        "session_date": session_date.isoformat(),
        "status": "REPORT_READY" if report_ready else "NOT_READY",
        "sent": False,
        "report": report,
        "london": london_snapshot,
        "new_york": new_york_snapshot,
        "comparison": comparison_snapshot,
        "intelligence": intelligence_snapshot,
    }

    if not report_ready:
        result["message"] = (
            "Report is incomplete. Telegram delivery was not attempted."
        )
        return result

    if not send:
        result["message"] = (
            "Report is ready. Telegram delivery was not requested."
        )
        return result

    if state_file is None:
        state_file = _default_state_file()

    state = _load_delivery_state(state_file)
    report_date = session_date.isoformat()

    if report_date in state["delivered_dates"]:
        result["status"] = "ALREADY_DELIVERED"
        result["message"] = (
            "This session date has already been delivered."
        )
        return result

    try:
        delivery = send_telegram_report(
            report=report,
            env_file=env_file,
        )
    except Exception as exc:
        result["status"] = "SEND_FAILED"
        result["message"] = (
            f"Telegram delivery failed ({type(exc).__name__})."
        )
        return result

    if (
        not isinstance(delivery, dict)
        or delivery.get("status") != "SENT"
        or delivery.get("messages_sent") != delivery.get("total_messages")
    ):
        result["status"] = "SEND_FAILED"
        result["message"] = "Telegram did not confirm complete delivery."
        return result

    state["delivered_dates"].append(report_date)

    try:
        _save_delivery_state(state_file, state)
    except OSError:
        result["status"] = "DELIVERED_STATE_UNRECORDED"
        result["sent"] = True
        result["message"] = (
            "Telegram confirmed delivery, but delivery state "
            "could not be saved. Do not retry automatically."
        )
        return result

    result["status"] = "SENT"
    result["sent"] = True
    result["delivery"] = delivery
    result["message"] = "Report delivered and delivery state saved."
    return result

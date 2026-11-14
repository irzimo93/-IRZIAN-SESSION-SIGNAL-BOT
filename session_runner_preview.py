#!/usr/bin/env python3
"""IRZIAN Session Signal Bot — safe preview runner.

This runner is intentionally preview-only:
- It never requests Telegram delivery.
- It always calls run_session_pipeline(..., send=False).
- It does not read, print, or modify the Telegram .env file.
"""

import argparse
import sys
from datetime import date
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build an IRZIAN session report without sending it."
    )
    parser.add_argument(
        "session_date",
        nargs="?",
        help="Session date in YYYY-MM-DD format (default: device local date).",
    )
    return parser.parse_args()


def main():
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from src.session_pipeline import run_session_pipeline
    except Exception as exc:
        print(f"IMPORT_FAILED: {type(exc).__name__}: {exc}")
        return 2

    args = parse_args()

    try:
        session_date = (
            date.fromisoformat(args.session_date)
            if args.session_date
            else date.today()
        )
    except ValueError:
        print("INVALID_DATE: use YYYY-MM-DD.")
        return 2

    try:
        result = run_session_pipeline(
            session_date=session_date,
            send=False,
        )
    except Exception as exc:
        print(f"PIPELINE_FAILED: {type(exc).__name__}: {exc}")
        return 1

    if not isinstance(result, dict):
        print("INVALID_RESULT: pipeline did not return a dictionary.")
        return 1

    print(f"SESSION_DATE: {result.get('session_date', session_date.isoformat())}")
    print(f"STATUS: {result.get('status', 'UNKNOWN')}")
    print("TELEGRAM_SEND: DISABLED (preview-only runner)")
    print(f"MESSAGE: {result.get('message', '')}")

    report = result.get("report")
    if isinstance(report, str) and report.strip():
        print("\n----- REPORT PREVIEW -----")
        print(report)
        print("----- END REPORT PREVIEW -----")

    return 0 if result.get("status") == "REPORT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

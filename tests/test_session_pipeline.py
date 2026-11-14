import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src import session_pipeline as pipeline


class FakeBuilder:
    def __init__(self, fail=False, status="READY"):
        self.fail = fail
        self.status = status
        self.calls = 0

    def build_dataset(self, **kwargs):
        self.calls += 1

        if self.fail:
            raise RuntimeError("offline dataset failure")

        return SimpleNamespace(
            status=self.status,
            expected_count=1,
            valid_count=1,
            gap_count=0,
            candles=(object(),),
        )


class SessionPipelineTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "state.json"

        self.builder = FakeBuilder()

        self.patches = [
            patch.object(
                pipeline,
                "HistoricalDatasetBuilder",
                return_value=self.builder,
            ),
            patch.object(
                pipeline,
                "analyze_session",
                return_value={"status": "READY"},
            ),
            patch.object(
                pipeline,
                "compare_sessions",
                return_value={
                    "status": "READY",
                    "total": pipeline.EXPECTED_TOTAL,
                    "ready": pipeline.EXPECTED_TOTAL,
                    "incomplete": 0,
                    "comparisons": {},
                    "errors": [],
                },
            ),
            patch.object(
                pipeline,
                "analyze_session_intelligence",
                return_value={
                    "status": "READY",
                    "source_status": "READY",
                    "total": pipeline.EXPECTED_TOTAL,
                    "ready": pipeline.EXPECTED_TOTAL,
                    "incomplete": 0,
                    "intelligence": {},
                    "errors": [],
                },
            ),
            patch.object(
                pipeline,
                "build_session_report",
                return_value="IRZIAN SESSION REPORT",
            ),
        ]

        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_pipeline(self, **kwargs):
        defaults = {
            "session_date": date(2026, 11, 10),
            "client": object(),
            "send": False,
            "state_file": self.state_file,
        }
        defaults.update(kwargs)
        return pipeline.run_session_pipeline(**defaults)

    def test_dry_run_builds_ready_report_without_sending(self):
        with patch.object(
            pipeline, "send_telegram_report"
        ) as sender:
            result = self.run_pipeline()

        self.assertEqual(result["status"], "REPORT_READY")
        self.assertFalse(result["sent"])
        self.assertEqual(result["report"], "IRZIAN SESSION REPORT")
        self.assertEqual(
            self.builder.calls,
            pipeline.EXPECTED_TOTAL * 2,
        )
        sender.assert_not_called()

    def test_incomplete_dataset_blocks_delivery(self):
        self.builder.fail = True

        with patch.object(
            pipeline, "send_telegram_report"
        ) as sender:
            result = self.run_pipeline(send=True)

        self.assertEqual(result["status"], "NOT_READY")
        self.assertFalse(result["sent"])
        sender.assert_not_called()

    def test_non_ready_dataset_blocks_delivery(self):
        self.builder.status = "PARTIAL"

        with patch.object(
            pipeline, "send_telegram_report"
        ) as sender:
            result = self.run_pipeline(send=True)

        self.assertEqual(result["status"], "NOT_READY")
        sender.assert_not_called()

    def test_successful_delivery_records_date(self):
        with patch.object(
            pipeline,
            "send_telegram_report",
            return_value={
                "status": "SENT",
                "messages_sent": 1,
                "total_messages": 1,
            },
        ) as sender:
            result = self.run_pipeline(send=True)

        self.assertEqual(result["status"], "SENT")
        self.assertTrue(result["sent"])
        sender.assert_called_once()

        saved = json.loads(
            self.state_file.read_text(encoding="utf-8")
        )
        self.assertEqual(
            saved["delivered_dates"],
            ["2026-11-10"],
        )

    def test_duplicate_date_is_not_sent_again(self):
        self.state_file.write_text(
            json.dumps({
                "delivered_dates": ["2026-11-10"]
            }),
            encoding="utf-8",
        )

        with patch.object(
            pipeline, "send_telegram_report"
        ) as sender:
            result = self.run_pipeline(send=True)

        self.assertEqual(result["status"], "ALREADY_DELIVERED")
        self.assertFalse(result["sent"])
        sender.assert_not_called()

    def test_delivery_failure_does_not_record_date(self):
        with patch.object(
            pipeline,
            "send_telegram_report",
            side_effect=RuntimeError("delivery failure"),
        ):
            result = self.run_pipeline(send=True)

        self.assertEqual(result["status"], "SEND_FAILED")
        self.assertFalse(result["sent"])
        self.assertFalse(self.state_file.exists())

    def test_state_save_failure_reports_delivery_separately(self):
        with patch.object(
            pipeline,
            "send_telegram_report",
            return_value={
                "status": "SENT",
                "messages_sent": 1,
                "total_messages": 1,
            },
        ), patch.object(
            pipeline,
            "_save_delivery_state",
            side_effect=OSError("disk failure"),
        ):
            result = self.run_pipeline(send=True)

        self.assertEqual(
            result["status"],
            "DELIVERED_STATE_UNRECORDED",
        )
        self.assertTrue(result["sent"])

    def test_invalid_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_pipeline(
                session_date=datetime(2026, 11, 10)
            )

    def test_non_boolean_send_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_pipeline(send="yes")


if __name__ == "__main__":
    unittest.main()

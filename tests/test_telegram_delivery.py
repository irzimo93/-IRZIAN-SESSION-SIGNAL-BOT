import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src.telegram_delivery import (
    TelegramDeliveryError,
    load_telegram_config,
    send_telegram_report,
    split_message,
)


class TelegramDeliveryTests(unittest.TestCase):

    def setUp(self):
        self.token = "TEST_SECRET_TOKEN"
        self.chat_id = "TEST_CHAT_ID"

    def make_response(self, ok=True, http_error=None, json_error=None):
        response = Mock()
        response.raise_for_status.side_effect = http_error
        if json_error:
            response.json.side_effect = json_error
        else:
            response.json.return_value = {"ok": ok}
        return response

    def make_session(self, responses):
        session = Mock()
        session.post.side_effect = responses
        return session

    # Message splitting

    def test_split_short_message(self):
        self.assertEqual(split_message("hello", 10), ["hello"])

    def test_split_long_message(self):
        chunks = split_message("abcdefghij", 4)
        self.assertEqual(chunks, ["abcd", "efgh", "ij"])

    def test_split_prefers_newline(self):
        chunks = split_message("abc\ndefgh", 5)
        self.assertEqual(chunks, ["abc\n", "defgh"])

    def test_split_newline_at_exact_limit(self):
        chunks = split_message("abcd\nefgh", 4)
        self.assertTrue(all(len(chunk) <= 4 for chunk in chunks))
        self.assertEqual("".join(chunks), "abcd\nefgh")

    def test_split_unicode_without_data_loss(self):
        message = "سلام 🌍 " * 20
        chunks = split_message(message, 9)
        self.assertEqual("".join(chunks), message)
        self.assertTrue(all(len(chunk) <= 9 for chunk in chunks))

    def test_split_long_line(self):
        message = "x" * 31
        chunks = split_message(message, 7)
        self.assertEqual("".join(chunks), message)
        self.assertTrue(all(len(chunk) <= 7 for chunk in chunks))

    def test_split_rejects_invalid_input(self):
        for value in ("", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    split_message(value)

    def test_split_rejects_invalid_limit(self):
        for value in (0, -1, True, 2.5, "10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    split_message("hello", value)

    # Configuration

    def test_load_config_from_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                'BOT_TOKEN="FILE_TOKEN"\nCHAT_ID=12345\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_telegram_config(env_file)
            self.assertEqual(config.bot_token, "FILE_TOKEN")
            self.assertEqual(config.chat_id, "12345")

    def test_environment_overrides_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "BOT_TOKEN=FILE_TOKEN\nCHAT_ID=111\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"BOT_TOKEN": "ENV_TOKEN", "CHAT_ID": "222"},
                clear=True,
            ):
                config = load_telegram_config(env_file)
            self.assertEqual(config.bot_token, "ENV_TOKEN")
            self.assertEqual(config.chat_id, "222")

    def test_env_file_supports_export_comments_and_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "# credentials\n"
                "export BOT_TOKEN='TOKEN_VALUE'\n"
                'CHAT_ID="98765"\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_telegram_config(env_file)
            self.assertEqual(config.bot_token, "TOKEN_VALUE")
            self.assertEqual(config.chat_id, "98765")

    def test_missing_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(TelegramDeliveryError):
                    load_telegram_config(env_file)

    # Delivery

    def test_single_message_success(self):
        session = self.make_session([self.make_response()])
        result = send_telegram_report(
            "Hello",
            self.token,
            self.chat_id,
            session=session,
        )
        self.assertEqual(result["status"], "SENT")
        self.assertEqual(result["messages_sent"], 1)
        self.assertEqual(result["total_messages"], 1)
        session.post.assert_called_once()
        self.assertFalse(session.close.called)

    def test_multiple_messages_are_sent_in_order(self):
        session = self.make_session([
            self.make_response(),
            self.make_response(),
            self.make_response(),
        ])
        report = "abcdefghij" * 781
        result = send_telegram_report(
            report,
            self.token,
            self.chat_id,
            session=session,
        )
        self.assertEqual(result["messages_sent"], 3)
        sent_texts = [
            call.kwargs["data"]["text"]
            for call in session.post.call_args_list
        ]
        self.assertEqual("".join(sent_texts), report)

    def test_timeout_is_passed_to_request(self):
        session = self.make_session([self.make_response()])
        send_telegram_report(
            "Hello",
            self.token,
            self.chat_id,
            session=session,
            timeout=7,
        )
        self.assertEqual(
            session.post.call_args.kwargs["timeout"],
            7,
        )

    def test_network_error_stops_delivery_and_hides_token(self):
        session = self.make_session([
            requests.ConnectionError("sensitive URL"),
            self.make_response(),
        ])
        with self.assertRaises(TelegramDeliveryError) as context:
            send_telegram_report(
                "Hello",
                self.token,
                self.chat_id,
                session=session,
            )
        self.assertNotIn(self.token, str(context.exception))
        self.assertEqual(session.post.call_count, 1)

    def test_http_error_stops_delivery(self):
        session = self.make_session([
            self.make_response(
                http_error=requests.HTTPError("failure")
            ),
            self.make_response(),
        ])
        with self.assertRaises(TelegramDeliveryError):
            send_telegram_report(
                "Hello",
                self.token,
                self.chat_id,
                session=session,
            )
        self.assertEqual(session.post.call_count, 1)

    def test_invalid_json_is_rejected(self):
        session = self.make_session([
            self.make_response(json_error=ValueError("invalid"))
        ])
        with self.assertRaises(TelegramDeliveryError):
            send_telegram_report(
                "Hello",
                self.token,
                self.chat_id,
                session=session,
            )

    def test_telegram_rejection_is_detected(self):
        session = self.make_session([self.make_response(ok=False)])
        with self.assertRaises(TelegramDeliveryError):
            send_telegram_report(
                "Hello",
                self.token,
                self.chat_id,
                session=session,
            )

    def test_stops_after_first_failed_chunk(self):
        session = self.make_session([
            self.make_response(),
            self.make_response(ok=False),
            self.make_response(),
        ])
        with self.assertRaises(TelegramDeliveryError) as context:
            send_telegram_report(
                "abcdefghij" * 781,
                self.token,
                self.chat_id,
                session=session,
            )
        self.assertIn("1 message(s) were sent", str(context.exception))
        self.assertEqual(session.post.call_count, 2)

    def test_injected_session_is_not_closed(self):
        session = self.make_session([self.make_response()])
        send_telegram_report(
            "Hello",
            self.token,
            self.chat_id,
            session=session,
        )
        session.close.assert_not_called()

    def test_internal_session_is_closed(self):
        fake_session = self.make_session([self.make_response()])
        with patch(
            "src.telegram_delivery.requests.Session",
            return_value=fake_session,
        ):
            send_telegram_report(
                "Hello",
                self.token,
                self.chat_id,
            )
        fake_session.close.assert_called_once()

    def test_internal_session_closes_after_failure(self):
        fake_session = self.make_session([
            requests.ConnectionError("failure")
        ])
        with patch(
            "src.telegram_delivery.requests.Session",
            return_value=fake_session,
        ):
            with self.assertRaises(TelegramDeliveryError):
                send_telegram_report(
                    "Hello",
                    self.token,
                    self.chat_id,
                )
        fake_session.close.assert_called_once()

    def test_explicit_token_can_use_chat_id_from_environment(self):
        with patch.dict(
            os.environ,
            {"CHAT_ID": self.chat_id},
            clear=True,
        ):
            session = self.make_session([self.make_response()])
            result = send_telegram_report(
                "Hello",
                bot_token=self.token,
                session=session,
            )
        self.assertEqual(result["status"], "SENT")

    def test_invalid_timeout_is_rejected(self):
        for timeout in (0, -1, True, float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    send_telegram_report(
                        "Hello",
                        self.token,
                        self.chat_id,
                        session=Mock(),
                        timeout=timeout,
                    )

    def test_empty_report_is_rejected(self):
        with self.assertRaises(ValueError):
            send_telegram_report(
                "   ",
                self.token,
                self.chat_id,
                session=Mock(),
            )


if __name__ == "__main__":
    unittest.main()

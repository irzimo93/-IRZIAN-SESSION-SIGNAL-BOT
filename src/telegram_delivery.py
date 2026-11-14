import math
import os
from dataclasses import dataclass
from pathlib import Path

import requests


TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 3900
DEFAULT_TIMEOUT = 15


class TelegramDeliveryError(Exception):
    """Safe, non-sensitive Telegram delivery error."""


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


def _read_env_file(env_file):
    path = Path(env_file)
    values = {}

    if not path.is_file():
        return values

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise TelegramDeliveryError(
            "Telegram configuration file could not be read."
        ) from None

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1]:
            if value[0] in ("'", '"'):
                value = value[1:-1].strip()

        if key in ("BOT_TOKEN", "CHAT_ID"):
            values[key] = value

    return values


def load_telegram_config(env_file=None):
    if env_file is None:
        env_file = Path(__file__).resolve().parent.parent / ".env"

    file_values = _read_env_file(env_file)

    env_token = os.environ.get("BOT_TOKEN")
    env_chat_id = os.environ.get("CHAT_ID")

    bot_token = (
        env_token.strip()
        if env_token and env_token.strip()
        else file_values.get("BOT_TOKEN", "").strip()
    )

    chat_id = (
        env_chat_id.strip()
        if env_chat_id and env_chat_id.strip()
        else file_values.get("CHAT_ID", "").strip()
    )

    if not bot_token or not chat_id:
        raise TelegramDeliveryError(
            "BOT_TOKEN or CHAT_ID is missing from the environment and .env."
        )

    return TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
    )


def split_message(text, max_length=MAX_MESSAGE_LENGTH):
    if not isinstance(text, str):
        raise ValueError("Message must be a string.")

    if not text:
        raise ValueError("Message must not be empty.")

    if not isinstance(max_length, int) or isinstance(max_length, bool):
        raise ValueError("max_length must be an integer.")

    if max_length < 1:
        raise ValueError("max_length must be positive.")

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        boundary = remaining.rfind("\n", 0, max_length)

        if boundary > 0:
            split_at = boundary + 1
        else:
            split_at = max_length

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    if remaining:
        chunks.append(remaining)

    return chunks


def send_telegram_report(
    report,
    bot_token=None,
    chat_id=None,
    session=None,
    timeout=DEFAULT_TIMEOUT,
    env_file=None,
):
    if not isinstance(report, str) or not report.strip():
        raise ValueError("Report must be a non-empty string.")

    if bot_token is None or chat_id is None:
        if env_file is None:
            env_file = Path(__file__).resolve().parent.parent / ".env"

        file_values = _read_env_file(env_file)

        if bot_token is None:
            env_token = os.environ.get("BOT_TOKEN")
            bot_token = (
                env_token.strip()
                if env_token and env_token.strip()
                else file_values.get("BOT_TOKEN", "").strip()
            )

        if chat_id is None:
            env_chat_id = os.environ.get("CHAT_ID")
            chat_id = (
                env_chat_id.strip()
                if env_chat_id and env_chat_id.strip()
                else file_values.get("CHAT_ID", "").strip()
            )

    if not isinstance(bot_token, str) or not bot_token.strip():
        raise ValueError("A valid bot token is required.")

    if not isinstance(chat_id, str) or not chat_id.strip():
        raise ValueError("A valid chat ID is required.")

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("timeout must be a finite positive number.")

    bot_token = bot_token.strip()
    chat_id = chat_id.strip()
    chunks = split_message(report)

    owns_session = session is None
    http = session if session is not None else requests.Session()

    endpoint = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    messages_sent = 0

    try:
        for index, chunk in enumerate(chunks, start=1):
            try:
                response = http.post(
                    endpoint,
                    data={
                        "chat_id": chat_id,
                        "text": chunk,
                    },
                    timeout=timeout,
                )
            except requests.RequestException:
                raise TelegramDeliveryError(
                    "Telegram network failure after "
                    f"{messages_sent} successful message(s)."
                ) from None

            try:
                response.raise_for_status()
            except requests.RequestException:
                raise TelegramDeliveryError(
                    "Telegram HTTP failure after "
                    f"{messages_sent} successful message(s)."
                ) from None

            try:
                payload = response.json()
            except (ValueError, TypeError):
                raise TelegramDeliveryError(
                    "Telegram returned an invalid response after "
                    f"{messages_sent} successful message(s)."
                ) from None

            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise TelegramDeliveryError(
                    f"Telegram rejected message {index}; "
                    f"{messages_sent} message(s) were sent successfully."
                )

            messages_sent += 1

    finally:
        if owns_session:
            http.close()

    return {
        "status": "SENT",
        "messages_sent": messages_sent,
        "total_messages": len(chunks),
    }

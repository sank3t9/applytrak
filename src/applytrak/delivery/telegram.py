"""Send a message via Telegram Bot API.

Public API:
    send_message(text, parse_mode="HTML") -> dict
"""

import logging

import httpx

from applytrak.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


def send_message(
    text: str,
    *,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> dict:
    """Send `text` to the configured Telegram chat. Returns the API response dict.

    Raises:
        RuntimeError: if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset.
        ValueError: if text exceeds Telegram's 4096-char limit.
        httpx.HTTPStatusError: on non-2xx Telegram responses.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError(
            "Telegram is not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env."
        )

    if len(text) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"Message length {len(text)} exceeds Telegram's {MAX_MESSAGE_LENGTH}-char limit"
        )

    url = f"{TELEGRAM_API_BASE}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

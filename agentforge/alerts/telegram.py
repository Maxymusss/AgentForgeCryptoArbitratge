"""Telegram alert module — sends arbitrage opportunity alerts via bot."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from ..models import ArbitrageOpportunity

logger = logging.getLogger(__name__)

# Chat ID — user must message the bot first to register
_CHAT_ID: Optional[str] = None


def set_chat_id(chat_id: str) -> None:
    """Set the Telegram chat ID for this session."""
    global _CHAT_ID
    _CHAT_ID = chat_id


def get_chat_id() -> Optional[str]:
    """Return the configured chat ID."""
    return _CHAT_ID


def send_message(text: str) -> bool:
    """Send a text message via the Telegram bot.

    Args:
        text: Message content.

    Returns:
        True if sent successfully, False otherwise.
    """
    from ..config import CONFIG

    chat_id = _CHAT_ID or CONFIG.telegram_chat_id
    if not chat_id:
        logger.warning("Telegram: no chat_id configured, skipping message")
        return False

    token = CONFIG.telegram_bot_token
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.debug("Telegram message sent: %s", text[:50])
        return True
    except requests.RequestException as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


def send_opportunity(opp: "ArbitrageOpportunity") -> bool:
    """Send an ArbitrageOpportunity alert via Telegram.

    Uses the opportunity's to_telegram() method for formatting.
    """
    return send_message(opp.to_telegram())

"""Telegram alert module — sends arbitrage opportunity alerts via bot."""

from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Bot token (from config — set TELEGRAM_BOT_TOKEN in .env or openclaw.json)
_TELEGRAM_TOKEN = "8782066565:AAHNlnYFgp0-7MeLpJ2S4BCLNx014uJ9aBA"
_TELEGRAM_API = f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}"

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
    if _CHAT_ID is None:
        logger.warning("Telegram: no chat_id configured, skipping message")
        return False

    url = f"{_TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": _CHAT_ID,
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


def send_arbitrage_alert(
    pair: str,
    buy_exchange: str,
    sell_exchange: str,
    buy_price: float,
    sell_price: float,
    profit_pct: float,
) -> bool:
    """Format and send an arbitrage opportunity alert to Telegram.

    Args:
        pair: Trading pair, e.g. "BTC/USDT".
        buy_exchange: Exchange to buy on.
        sell_exchange: Exchange to sell on.
        buy_price: Price on buy exchange.
        sell_price: Price on sell exchange.
        profit_pct: Net profit percentage after fees.

    Returns:
        True if sent successfully.
    """
    spread_pct = ((sell_price - buy_price) / buy_price) * 100

    message = (
        f"💰 <b>Arbitrage Opportunity</b>\n\n"
        f"Pair: <code>{pair}</code>\n"
        f"Buy:  <b>{buy_exchange}</b> @ ${buy_price:,.4f}\n"
        f"Sell: <b>{sell_exchange}</b> @ ${sell_price:,.4f}\n\n"
        f"Spread: <code>{spread_pct:+.4f}%</code>\n"
        f"Net profit: <b>{profit_pct:+.4f}%</b>\n\n"
        f"⚠️ Verify balances & API limits before trading!"
    )

    return send_message(message)

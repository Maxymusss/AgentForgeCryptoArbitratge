"""Binance exchange connector — public REST API for bid/ask prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BINANCE_BOOK_URL = "https://api.binance.com/api/v3/ticker/bookTicker"


def fetch_bid_ask(symbol: str) -> tuple[float | None, float | None]:
    """Fetch the current bid and ask prices for `symbol` on Binance.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT", "ETHUSDT".

    Returns:
        (bid, ask) — either may be None if the request fails.
    """
    params = {"symbol": symbol.upper()}
    try:
        resp = requests.get(_BINANCE_BOOK_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        bid = float(data["bidPrice"]) if data.get("bidPrice") else None
        ask = float(data["askPrice"]) if data.get("askPrice") else None
        logger.debug("Binance %s bid=%s ask=%s", symbol, bid, ask)
        return bid, ask
    except requests.RequestException as exc:
        logger.warning("Binance bid/ask fetch failed for %s: %s", symbol, exc)
        return None, None
    except (KeyError, ValueError) as exc:
        logger.warning("Binance unexpected response for %s: %s", symbol, exc)
        return None, None




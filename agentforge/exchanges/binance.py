"""Binance exchange connector — uses python-binance for authenticated calls
and the public REST API for unauthenticated price queries.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from ..config import CONFIG

logger = logging.getLogger(__name__)

# Public Binance ticker endpoint (no auth required for price reads)
_BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"


def fetch_price(symbol: str) -> float | None:
    """Fetch the current spot price for `symbol` on Binance.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT", "ETHUSDT".

    Returns:
        Current price as a float, or None if the request fails.
    """
    params = {"symbol": symbol.upper()}
    try:
        resp = requests.get(_BINANCE_TICKER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        price = float(data["price"])
        logger.debug("Binance %s @ %s", symbol, price)
        return price
    except requests.RequestException as exc:
        logger.warning("Binance price fetch failed for %s: %s", symbol, exc)
        return None
    except (KeyError, ValueError) as exc:
        logger.warning("Binance unexpected response for %s: %s — %s", symbol, exc, resp.text[:200])
        return None

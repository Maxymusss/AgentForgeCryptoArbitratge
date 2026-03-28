"""Bybit exchange connector — public REST API for spot bid/ask prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BYBIT_TICKER_URL = "https://api.bybit.com/v5/market/tickers"


def fetch_bid_ask(symbol: str) -> tuple[float | None, float | None]:
    """Fetch the current bid and ask prices for a symbol on Bybit.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT".

    Returns:
        (bid, ask) — either may be None if the request fails.
    """
    params: dict[str, str] = {
        "category": "spot",
        "symbol": symbol.upper(),
    }

    try:
        resp = requests.get(_BYBIT_TICKER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        if data.get("retMsg") != "OK":
            logger.warning("Bybit API error for %s: %s", symbol, data.get("retMsg"))
            return None, None

        list_data = data.get("result", {}).get("list", [])
        if not list_data:
            return None, None

        tick = list_data[0]
        bid = float(tick.get("bid1Price", 0)) or None
        ask = float(tick.get("ask1Price", 0)) or None
        logger.debug("Bybit %s bid=%s ask=%s", symbol, bid, ask)
        return bid, ask

    except requests.RequestException as exc:
        logger.warning("Bybit bid/ask fetch failed for %s: %s", symbol, exc)
        return None, None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Bybit unexpected response for %s: %s", symbol, exc)
        return None, None

"""Bybit exchange connector — public REST API for spot prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BYBIT_TICKER_URL = "https://api.bybit.com/v5/market/tickers"


def fetch_price(symbol: str) -> float | None:
    """Fetch the current spot price for a symbol on Bybit.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT", "ETHUSDT".

    Returns:
        Current price as a float, or None if the request fails.
    """
    # Bybit uses category=spot for spot market tickers
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
            return None

        list_data = data.get("result", {}).get("list", [])
        if not list_data:
            logger.warning("Bybit empty result for %s", symbol)
            return None

        tick = list_data[0]
        price = float(tick.get("lastPrice", 0))
        logger.debug("Bybit %s @ %s", symbol, price)
        return price if price > 0 else None

    except requests.RequestException as exc:
        logger.warning("Bybit price fetch failed for %s: %s", symbol, exc)
        return None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Bybit unexpected response for %s: %s", symbol, exc)
        return None

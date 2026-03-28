"""OKX exchange connector — public REST API for spot prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .symbols import normalize, Exchange

logger = logging.getLogger(__name__)

_OKX_TICKER_URL = "https://www.okx.com/api/v5/market/ticker"


def fetch_price(symbol: str) -> float | None:
    """Fetch the current spot price for a symbol on OKX.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT" (converted internally to "BTC-USDT").

    Returns:
        Current price as a float, or None if the request fails.
    """
    okx_symbol = normalize(symbol, Exchange.OKX)
    params = {"instId": okx_symbol}

    try:
        resp = requests.get(_OKX_TICKER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        if data.get("code") != "0":
            logger.warning("OKX API error for %s: %s", okx_symbol, data.get("msg"))
            return None

        ticks = data.get("data", [])
        if not ticks:
            logger.warning("OKX empty result for %s", okx_symbol)
            return None

        price = float(ticks[0].get("last", 0))
        logger.debug("OKX %s @ %s", okx_symbol, price)
        return price if price > 0 else None

    except requests.RequestException as exc:
        logger.warning("OKX price fetch failed for %s: %s", symbol, exc)
        return None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("OKX unexpected response for %s: %s", symbol, exc)
        return None

"""OKX exchange connector — public REST API for spot bid/ask prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .symbols import normalize, Exchange

logger = logging.getLogger(__name__)

_OKX_TICKER_URL = "https://www.okx.com/api/v5/market/ticker"


def fetch_bid_ask(symbol: str) -> tuple[float | None, float | None]:
    """Fetch the current bid and ask prices for a symbol on OKX.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT".

    Returns:
        (bid, ask) — either may be None if the request fails.
    """
    okx_symbol = normalize(symbol, Exchange.OKX)
    params = {"instId": okx_symbol}

    try:
        resp = requests.get(_OKX_TICKER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        if data.get("code") != "0":
            logger.warning("OKX API error for %s: %s", okx_symbol, data.get("msg"))
            return None, None

        ticks = data.get("data", [])
        if not ticks:
            return None, None

        tick = ticks[0]
        bid = float(tick.get("bidPx", 0)) or None
        ask = float(tick.get("askPx", 0)) or None
        logger.debug("OKX %s bid=%s ask=%s", okx_symbol, bid, ask)
        return bid, ask

    except requests.RequestException as exc:
        logger.warning("OKX bid/ask fetch failed for %s: %s", symbol, exc)
        return None, None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("OKX unexpected response for %s: %s", symbol, exc)
        return None, None

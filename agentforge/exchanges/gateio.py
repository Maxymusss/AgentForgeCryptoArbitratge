"""Gate.io exchange connector — public REST API for spot bid/ask prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .symbols import normalize, Exchange

logger = logging.getLogger(__name__)

_GATEIO_TICKER_URL = "https://api.gateio.ws/api/v4/spot/tickers"


def fetch_bid_ask(symbol: str) -> tuple[float | None, float | None]:
    """Fetch the current bid and ask prices for a symbol on Gate.io.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT".

    Returns:
        (bid, ask) — either may be None if the request fails.
    """
    gate_symbol = normalize(symbol, Exchange.GATEIO)
    params = {"currency_pair": gate_symbol}

    try:
        resp = requests.get(_GATEIO_TICKER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()

        if not data:
            return None, None

        tick = data[0]
        bid = float(tick.get("highest_bid", 0)) or None
        ask = float(tick.get("lowest_ask", 0)) or None
        logger.debug("Gate.io %s bid=%s ask=%s", gate_symbol, bid, ask)
        return bid, ask

    except requests.RequestException as exc:
        logger.warning("Gate.io bid/ask fetch failed for %s: %s", symbol, exc)
        return None, None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Gate.io unexpected response for %s: %s", symbol, exc)
        return None, None

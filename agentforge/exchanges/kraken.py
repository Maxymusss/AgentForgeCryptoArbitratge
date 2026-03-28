"""Kraken exchange connector — public REST API for spot bid/ask prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .symbols import normalize, Exchange

logger = logging.getLogger(__name__)

_KRAKEN_TICKER_URL = "https://api.kraken.com/0/public/Ticker"


def fetch_bid_ask(pair: str) -> tuple[float | None, float | None]:
    """Fetch the current bid and ask prices for a pair on Kraken.

    Args:
        pair: Binance-style symbol, e.g. "BTCUSDT".

    Returns:
        (bid, ask) — either may be None if the request fails or pair unsupported.
    """
    kraken_pair = normalize(pair, Exchange.KRAKEN)
    if kraken_pair is None:
        logger.warning("Kraken: pair %s not supported", pair)
        return None, None

    try:
        resp = requests.get(_KRAKEN_TICKER_URL, params={"pair": kraken_pair}, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        if data.get("error"):
            logger.warning("Kraken API error for %s: %s", kraken_pair, data["error"])
            return None, None

        result = data.get("result")
        if not result:
            return None, None

        tick_data = next(iter(result.values()), None)
        if tick_data is None:
            return None, None

        # Kraken Ticker: b = [bid, whole_lot, volume], a = [ask, whole_lot, volume]
        bid = float(tick_data["b"][0]) if tick_data["b"] else None
        ask = float(tick_data["a"][0]) if tick_data["a"] else None
        logger.debug("Kraken %s bid=%s ask=%s", kraken_pair, bid, ask)
        return bid, ask

    except requests.RequestException as exc:
        logger.warning("Kraken bid/ask fetch failed for %s: %s", pair, exc)
        return None, None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Kraken unexpected response for %s: %s", pair, exc)
        return None, None




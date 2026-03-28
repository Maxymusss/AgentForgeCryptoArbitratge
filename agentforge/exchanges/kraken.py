"""Kraken exchange connector — public REST API for spot prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .symbols import normalize, Exchange

logger = logging.getLogger(__name__)

_KRAKEN_TICKER_URL = "https://api.kraken.com/0/public/Ticker"


def fetch_price(pair: str) -> float | None:
    """Fetch the current spot price for a pair on Kraken.

    Args:
        pair: Binance-style symbol, e.g. "BTCUSDT" (converts internally).

    Returns:
        Current price as a float, or None if the request fails.
    """
    kraken_pair = normalize(pair, Exchange.KRAKEN)

    try:
        resp = requests.get(_KRAKEN_TICKER_URL, params={"pair": kraken_pair}, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        if data.get("error"):
            logger.warning("Kraken API error for %s: %s", kraken_pair, data["error"])
            return None

        # Result is keyed by pair name (e.g. "XXBTZUSD") → tick data
        result = data.get("result")
        if not result:
            return None

        # Get the first result key (the pair name as Kraken knows it)
        tick_data = next(iter(result.values()), None)
        if tick_data is None:
            return None

        # c[0] = last trade closed price (string)
        price = float(tick_data["c"][0])
        logger.debug("Kraken %s @ %s", kraken_pair, price)
        return price

    except requests.RequestException as exc:
        logger.warning("Kraken price fetch failed for %s: %s", pair, exc)
        return None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Kraken unexpected response for %s: %s", pair, exc)
        return None

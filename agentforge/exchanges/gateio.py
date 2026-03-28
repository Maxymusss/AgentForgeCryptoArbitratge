"""Gate.io exchange connector — public REST API for spot prices."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .symbols import normalize, Exchange

logger = logging.getLogger(__name__)

_GATEIO_TICKER_URL = "https://api.gateio.ws/api/v4/spot/tickers"


def fetch_price(symbol: str) -> float | None:
    """Fetch the current spot price for a symbol on Gate.io.

    Args:
        symbol: Binance-style symbol, e.g. "BTCUSDT" (converted internally to "BTC_USDT").

    Returns:
        Current price as a float, or None if the request fails.
    """
    gate_symbol = normalize(symbol, Exchange.GATEIO)
    params = {"currency_pair": gate_symbol}

    try:
        resp = requests.get(_GATEIO_TICKER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()

        if not data:
            logger.warning("Gate.io empty result for %s", gate_symbol)
            return None

        price = float(data[0].get("last", 0))
        logger.debug("Gate.io %s @ %s", gate_symbol, price)
        return price if price > 0 else None

    except requests.RequestException as exc:
        logger.warning("Gate.io price fetch failed for %s: %s", symbol, exc)
        return None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Gate.io unexpected response for %s: %s", symbol, exc)
        return None

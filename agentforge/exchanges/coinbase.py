"""Coinbase exchange connector — uses the public Coinbase REST API v2.

API docs: https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_get Spot price
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Public Coinbase spot price endpoint
_COINBASE_SPOT_URL = "https://api.coinbase.com/v2/prices/{pair}/spot"


def fetch_price(pair: str) -> float | None:
    """Fetch the current spot price for `pair` on Coinbase.

    Args:
        pair: Coinbase-style pair, e.g. "BTC-USD", "ETH-USD".
              Internally we convert Binance-style "BTCUSDT" -> "BTC-USD".

    Returns:
        Current price as a float, or None if the request fails.
    """
    # Convert Binance symbol (BTCUSDT) -> Coinbase format (BTC-USD)
    coinbase_pair = _to_coinbase_pair(pair)

    url = _COINBASE_SPOT_URL.format(pair=coinbase_pair)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        price = float(data["data"]["amount"])
        logger.debug("Coinbase %s @ %s", coinbase_pair, price)
        return price
    except requests.RequestException as exc:
        logger.warning("Coinbase price fetch failed for %s: %s", coinbase_pair, exc)
        return None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning(
            "Coinbase unexpected response for %s: %s — %s",
            coinbase_pair,
            exc,
            resp.text[:200],
        )
        return None


def _to_coinbase_pair(binance_symbol: str) -> str:
    """Convert Binance symbol to Coinbase pair format.

    Examples:
        BTCUSDT -> BTC-USD
        ETHUSDT -> ETH-USD
        SOLUSDT -> SOL-USD
    """
    # Remove common quote currencies
    for quote in ("USDT", "USD", "BUSD", "USDC"):
        if binance_symbol.endswith(quote):
            base = binance_symbol[: -len(quote)]
            return f"{base}-{quote.replace('USDT', 'USD')}"
    # Fallback
    return binance_symbol

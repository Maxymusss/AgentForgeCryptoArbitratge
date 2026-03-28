"""Coinbase exchange connector — public REST API v2 for spot bid/ask."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_COINBASE_SPOT_URL = "https://api.coinbase.com/v2/prices/{pair}/{side}"


def fetch_bid_ask(pair: str) -> tuple[float | None, float | None]:
    """Fetch the current bid and ask prices for `pair` on Coinbase.

    Args:
        pair: Binance-style symbol, e.g. "BTCUSDT" (converted internally to "BTC-USD").

    Returns:
        (bid, ask) — either may be None if the request fails.
    """
    coinbase_pair = _to_coinbase_pair(pair)
    bid, ask = None, None

    for side in ("bid", "ask"):
        url = _COINBASE_SPOT_URL.format(pair=coinbase_pair, side=side)
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            price = float(data["data"]["amount"])
            if side == "bid":
                bid = price
            else:
                ask = price
            logger.debug("Coinbase %s %s=%s", coinbase_pair, side, price)
        except requests.RequestException as exc:
            logger.warning("Coinbase %s fetch failed: %s", side, exc)
            return None, None
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Coinbase unexpected response for %s: %s", side, exc)
            return None, None

    return bid, ask


def _to_coinbase_pair(binance_symbol: str) -> str:
    """Convert Binance symbol (BTCUSDT) → Coinbase format (BTC-USD).

    Handles USDT, USD, USDC, and BUSD quote currencies.
    Note: BUSD is passed through as-is (BTCBUSD → BTC-BUSD); Coinbase
    may not list all BUSD pairs, so some conversions may fail at the API level.
    """
    for quote in ("USDT", "USD", "USDC", "BUSD"):
        if binance_symbol.endswith(quote):
            base = binance_symbol[: -len(quote)]
            return f"{base}-{quote.replace('USDT', 'USD')}"
    return binance_symbol

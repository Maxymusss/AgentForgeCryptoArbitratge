"""CoinGecko API connector — used to fetch the top 50 most liquid crypto pairs."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

_COINGECKO_MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
)


@dataclass
class CoinInfo:
    """A cryptocurrency with symbol and name."""
    symbol: str       # e.g. "BTC"
    name: str         # e.g. "Bitcoin"
    id: str           # CoinGecko id (e.g. "bitcoin")


# In-memory cache + timestamp
_cached_coins: list[CoinInfo] = []
_cache_time: float = 0.0
_CACHE_TTL: int = 30 * 60  # 30 minutes


def get_top_coins(limit: int = 50) -> list[CoinInfo]:
    """Fetch the top `limit` most liquid cryptocurrencies from CoinGecko.

    Results are cached for 30 minutes to respect API rate limits.

    Args:
        limit: Number of coins to return (default 50).

    Returns:
        List of CoinInfo objects sorted by volume descending.
    """
    global _cached_coins, _cache_time

    now = time.time()
    if _cached_coins and (now - _cache_time) < _CACHE_TTL:
        return _cached_coins[:limit]

    params: dict[str, Any] = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": False,
    }

    try:
        resp = requests.get(_COINGECKO_MARKETS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()

        _cached_coins = [
            CoinInfo(
                symbol=coin["symbol"].upper(),
                name=coin["name"],
                id=coin["id"],
            )
            for coin in data
        ]
        _cache_time = now
        logger.info("CoinGecko: refreshed top %d coins", len(_cached_coins))

    except requests.RequestException as exc:
        logger.warning("CoinGecko fetch failed, using cache: %s", exc)
        if _cached_coins:
            return _cached_coins[:limit]

    return _cached_coins[:limit]


def get_binance_symbol(coin: CoinInfo) -> str:
    """Convert a CoinInfo symbol to Binance-style pair symbol.

    Args:
        coin: CoinInfo from CoinGecko.

    Returns:
        Binance-style symbol, e.g. "BTCUSDT", "ETHUSDT".
    """
    return f"{coin.symbol}USDT"

"""Standalone arbitrage detection for the web package — avoids circular imports with core."""

from __future__ import annotations

from ..config import CONFIG
from ..models import Exchange


def find_arbitrage_opportunities(
    bid_asks: dict[Exchange, tuple[float | None, float | None]],
    pair: str,
) -> list[dict]:
    """Web-friendly version — accepts bid/ask dict, returns dicts instead of model objects."""
    from ..core.arbitrage import find_arbitrage_opportunities as _core_find
    from ..models import ArbitrageOpportunity

    opps: list[ArbitrageOpportunity] = _core_find(bid_asks, pair)
    return [
        {
            "buy_exchange": o.buy_exchange,
            "sell_exchange": o.sell_exchange,
            "pair": o.pair,
            "buy_price": o.buy_price,
            "sell_price": o.sell_price,
            "raw_spread_pct": o.raw_spread_pct,
            "profit_pct": o.profit_pct,
        }
        for o in opps
    ]

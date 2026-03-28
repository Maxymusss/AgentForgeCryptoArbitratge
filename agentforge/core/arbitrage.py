"""Multi-exchange arbitrage detection engine — N×N comparison across all enabled exchanges."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import CONFIG
from ..models import ArbitrageOpportunity, Exchange

logger = logging.getLogger(__name__)


@dataclass
class PriceResult:
    """Result of fetching price from a single exchange."""
    exchange: Exchange
    price: float | None


def find_arbitrage_opportunities(
    prices: dict[Exchange, float],
    pair: str,
) -> list[ArbitrageOpportunity]:
    """Find all arbitrage opportunities given prices across exchanges.

    Performs N×N comparison: tries every exchange as buy, every other as sell.
    Applies the correct fee schedule per exchange.

    Args:
        prices: Dict mapping Exchange → price (float), or None if unavailable.
        pair: Trading pair symbol, e.g. "BTCUSDT".

    Returns:
        List of ArbitrageOpportunity, sorted by net_profit_pct descending.
        Empty list if no profitable opportunities.
    """
    opportunities: list[ArbitrageOpportunity] = []

    exchanges = list(Exchange)
    for buy_exchange in exchanges:
        buy_price = prices.get(buy_exchange)
        if buy_price is None or buy_price <= 0:
            continue

        for sell_exchange in exchanges:
            if sell_exchange == buy_exchange:
                continue

            sell_price = prices.get(sell_exchange)
            if sell_price is None or sell_price <= 0:
                continue

            opp = _evaluate(buy_exchange, sell_exchange, pair, buy_price, sell_price)
            if opp:
                opportunities.append(opp)

    # Sort by most profitable first
    opportunities.sort(key=lambda o: o.profit_pct, reverse=True)
    return opportunities


def _evaluate(
    buy_exchange: Exchange,
    sell_exchange: Exchange,
    pair: str,
    buy_price: float,
    sell_price: float,
) -> ArbitrageOpportunity | None:
    """Evaluate a single buy_exchange → sell_exchange trade."""
    if buy_price <= 0 or sell_price <= 0:
        return None

    raw_spread_pct = ((sell_price - buy_price) / buy_price) * 100

    buy_fee = _taker_fee(buy_exchange)
    sell_fee = _taker_fee(sell_exchange)
    total_fees_pct = (buy_fee + sell_fee) * 100

    net_profit_pct = raw_spread_pct - total_fees_pct

    return ArbitrageOpportunity(
        buy_exchange=buy_exchange.value,
        sell_exchange=sell_exchange.value,
        pair=pair,
        buy_price=buy_price,
        sell_price=sell_price,
        raw_spread_pct=round(raw_spread_pct, 6),
        profit_pct=round(net_profit_pct, 6),
    )


def _taker_fee(exchange: Exchange) -> float:
    """Return taker fee fraction for an exchange."""
    cfg = CONFIG.exchanges.get(exchange.value)
    if cfg is None:
        return 0.001  # default 0.1%
    return cfg.fees.taker_pct


def best_opportunity(
    prices: dict[Exchange, float],
    pair: str,
) -> ArbitrageOpportunity | None:
    """Return the single best arbitrage opportunity, or None.
    
    Only returns opportunities with positive net profit.
    """
    opportunities = find_arbitrage_opportunities(prices, pair)
    # Filter to profitable only
    profitable = [o for o in opportunities if o.profit_pct > 0]
    return profitable[0] if profitable else None

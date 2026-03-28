"""Arbitrage detection and profit calculation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import CONFIG
from ..models import ArbitrageOpportunity

logger = logging.getLogger(__name__)


@dataclass
class PriceQuote:
    """A single exchange price quote."""
    exchange: str
    symbol: str
    price: float


def compare_prices(
    buy_exchange: str,
    sell_exchange: str,
    pair: str,
    buy_price: float,
    sell_price: float,
) -> ArbitrageOpportunity | None:
    """Detect whether a profitable arbitrage exists between two exchanges.

    Args:
        buy_exchange:  Name of the exchange to buy on.
        sell_exchange: Name of the exchange to sell on.
        pair:          Trading pair symbol (e.g. "BTCUSDT").
        buy_price:     Price on the buy exchange.
        sell_price:    Price on the sell exchange.

    Returns:
        ArbitrageOpportunity if buy low / sell high is profitable after fees,
        None otherwise.
    """
    if buy_price <= 0 or sell_price <= 0:
        return None

    # Gross spread: how much extra we get selling vs buying
    raw_spread_pct = ((sell_price - buy_price) / buy_price) * 100

    # Net profit after exchange taker fees (0.1% per side = 0.001)
    fees_pct = CONFIG.binance_fees.taker_pct + CONFIG.coinbase_fees.taker_pct
    net_profit_pct = raw_spread_pct - (fees_pct * 100)

    opp = ArbitrageOpportunity(
        buy_exchange=buy_exchange,
        sell_exchange=sell_exchange,
        pair=pair,
        buy_price=buy_price,
        sell_price=sell_price,
        raw_spread_pct=round(raw_spread_pct, 6),
        profit_pct=round(net_profit_pct, 6),
        volume_hint=None,
    )

    logger.debug(
        "%s: raw spread=%.4f%%, net profit=%.4f%%",
        pair,
        raw_spread_pct,
        net_profit_pct,
    )
    return opp


def find_best_arbitrage(
    binance_price: float | None,
    coinbase_price: float | None,
    pair: str,
) -> ArbitrageOpportunity | None:
    """Given prices from both exchanges, find the best arbitrage direction.

    Checks both directions (buy Binance → sell Coinbase and vice versa)
    and returns whichever is more profitable.

    Returns None if prices are unavailable or both directions are unprofitable.
    """
    opportunities: list[ArbitrageOpportunity] = []

    if binance_price is not None and coinbase_price is not None:
        # Direction 1: buy Binance, sell Coinbase
        opp1 = compare_prices(
            "Binance", "Coinbase", pair, binance_price, coinbase_price
        )
        if opp1:
            opportunities.append(opp1)

        # Direction 2: buy Coinbase, sell Binance
        opp2 = compare_prices(
            "Coinbase", "Binance", pair, coinbase_price, binance_price
        )
        if opp2:
            opportunities.append(opp2)

    elif binance_price is not None:
        logger.warning("Coinbase price unavailable for %s", pair)

    elif coinbase_price is not None:
        logger.warning("Binance price unavailable for %s", pair)

    else:
        logger.warning("No price data available for %s", pair)
        return None

    if not opportunities:
        return None

    # Return the most profitable opportunity
    return max(opportunities, key=lambda o: o.profit_pct)

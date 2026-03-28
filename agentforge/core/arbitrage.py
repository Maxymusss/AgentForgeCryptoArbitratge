"""Multi-exchange arbitrage detection engine — uses real bid/ask prices for executable trades."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import CONFIG
from ..models import ArbitrageOpportunity, Exchange

logger = logging.getLogger(__name__)

# Minimum order amounts (in base currency, e.g. BTC) per exchange.
# These are reasonable defaults; real minimums vary by pair.
MIN_ORDER_AMOUNTS: dict[str, float] = {
    "binance":  0.0001,   # ~$10 at BTC $100k
    "coinbase": 0.0001,
    "kraken":   0.0001,
    "bybit":    0.0001,
    "okx":      0.0001,
    "gateio":   0.0001,
}

# Volume score weights per exchange (higher = more liquid).
# Normalised so the highest-volume exchange scores 100.
_VOLUME_SCORE_WEIGHTS: dict[str, float] = {
    "binance":  100.0,
    "coinbase":  80.0,
    "okx":       75.0,
    "gateio":    65.0,
    "bybit":     60.0,
    "kraken":    50.0,
}

DEFAULT_VOLUME_SCORE: float = 50.0


@dataclass
class BidAsk:
    """A single exchange's bid and ask prices."""
    exchange: Exchange
    bid: float | None
    ask: float | None


def find_arbitrage_opportunities(
    bid_asks: dict[Exchange, tuple[float | None, float | None]],
    pair: str,
) -> list[ArbitrageOpportunity]:
    """Find all executable arbitrage opportunities using real bid/ask prices.

    The key insight: to execute a trade, you must buy at ASK (offer) and sell at BID.
    So we find:
        - Best ASK across exchanges → where to BUY
        - Best BID across exchanges → where to SELL

    An opportunity exists when: max_bid > min_ask
    The gross spread = max_bid - min_ask

    Args:
        bid_asks: Dict mapping Exchange → (bid_price, ask_price).
        pair: Trading pair symbol, e.g. "BTCUSDT".

    Returns:
        List of ArbitrageOpportunity sorted by net_profit_pct descending.
    """
    opportunities: list[ArbitrageOpportunity] = []

    # Collect valid ASK prices → candidate buy exchanges
    asks: list[BidAsk] = []
    for exchange, (bid, ask) in bid_asks.items():
        if ask is not None and ask > 0:
            asks.append(BidAsk(exchange=exchange, bid=bid, ask=ask))

    # Collect valid BID prices → candidate sell exchanges
    bids: list[BidAsk] = []
    for exchange, (bid, ask) in bid_asks.items():
        if bid is not None and bid > 0:
            bids.append(BidAsk(exchange=exchange, bid=bid, ask=ask))

    # Try each exchange as buy (ASK), each other as sell (BID)
    for buy in asks:
        for sell in bids:
            if sell.exchange == buy.exchange:
                continue

            opp = _evaluate(buy, sell, pair)
            if opp:
                opportunities.append(opp)

    opportunities.sort(key=lambda o: o.profit_pct, reverse=True)
    return opportunities


def _evaluate(
    buy: BidAsk,
    sell: BidAsk,
    pair: str,
) -> ArbitrageOpportunity | None:
    """Evaluate buying at `buy.ask` and selling at `sell.bid`."""
    if buy.ask is None or sell.bid is None:
        return None
    if buy.ask <= 0 or sell.bid <= 0:
        return None

    buy_ex = buy.exchange
    sell_ex = sell.exchange
    buy_price = buy.ask     # what you PAY to buy
    sell_price = sell.bid   # what you RECEIVE when selling

    raw_spread = sell_price - buy_price
    raw_spread_pct = (raw_spread / buy_price) * 100

    buy_fee = _taker_fee(buy_ex)
    sell_fee = _taker_fee(sell_ex)
    total_fees_pct = (buy_fee + sell_fee) * 100

    net_profit_pct = raw_spread_pct - total_fees_pct

    return ArbitrageOpportunity(
        buy_exchange=buy_ex.value,
        sell_exchange=sell_ex.value,
        pair=pair,
        buy_price=buy_price,      # ASK = what you pay
        sell_price=sell_price,    # BID = what you receive
        raw_spread_pct=round(raw_spread_pct, 6),
        profit_pct=round(net_profit_pct, 6),
        min_order_amount=MIN_ORDER_AMOUNTS.get(buy_ex.value),
        volume_score=_VOLUME_SCORE_WEIGHTS.get(
            buy_ex.value, DEFAULT_VOLUME_SCORE
        ),
    )


def _taker_fee(exchange: Exchange) -> float:
    cfg = CONFIG.exchanges.get(exchange.value)
    if cfg is None:
        logger.warning(
            "Exchange %s not found in config — using default taker fee 0.1%%",
            exchange.value,
        )
        return 0.001
    return cfg.fees.taker_pct


def best_opportunity(
    bid_asks: dict[Exchange, tuple[float | None, float | None]],
    pair: str,
) -> ArbitrageOpportunity | None:
    """Return the single best executable arbitrage opportunity, or None."""
    opps = find_arbitrage_opportunities(bid_asks, pair)
    profitable = [o for o in opps if o.profit_pct > 0]
    return profitable[0] if profitable else None

"""Async multi-exchange monitor — polls all exchanges concurrently and emits opportunities."""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Callable

import httpx

from ..config import CONFIG
from ..exchanges import (
    binance_fetch,
    coinbase_fetch,
    kraken_fetch,
    bybit_fetch,
    okx_fetch,
    gateio_fetch,
    Exchange,
)
from ..models import ArbitrageOpportunity
from .arbitrage import find_arbitrage_opportunities

logger = logging.getLogger(__name__)

# Map Exchange → fetch function
_EXCHANGE_FETCHERS: dict[Exchange, Callable[[str], float | None]] = {
    Exchange.BINANCE:  binance_fetch,
    Exchange.COINBASE: coinbase_fetch,
    Exchange.KRAKEN:   kraken_fetch,
    Exchange.BYBIT:   bybit_fetch,
    Exchange.OKX:     okx_fetch,
    Exchange.GATEIO:  gateio_fetch,
}


async def fetch_all_prices(
    pair: str,
    exchanges: list[Exchange],
) -> dict[Exchange, float | None]:
    """Fetch prices from all exchanges concurrently using httpx async client.

    Args:
        pair: Binance-style symbol (e.g. "BTCUSDT").
        exchanges: List of exchanges to query.

    Returns:
        Dict mapping Exchange → price (or None if fetch failed).
    """
    async def fetch_one(exchange: Exchange) -> tuple[Exchange, float | None]:
        fetcher = _EXCHANGE_FETCHERS.get(exchange)
        if fetcher is None:
            return exchange, None
        # Run sync fetchers in thread pool (they use requests, not async)
        loop = asyncio.get_running_loop()
        price = await loop.run_in_executor(None, fetcher, pair)
        return exchange, price

    results = await asyncio.gather(*(fetch_one(ex) for ex in exchanges))
    return dict(results)


async def monitor_loop(
    pairs: list[str],
    interval: int | None = None,
    min_profit_pct: float | None = None,
    on_opportunity: Callable[[ArbitrageOpportunity], None] | None = None,
    enabled_exchanges: list[Exchange] | None = None,
) -> None:
    """Run the arbitrage monitoring loop.

    Args:
        pairs: List of trading pairs to monitor.
        interval: Poll interval in seconds.
        min_profit_pct: Minimum net profit % to flag.
        on_opportunity: Callback for each detected opportunity.
        enabled_exchanges: Which exchanges to query.
    """
    interval = interval or CONFIG.poll_interval
    min_profit = min_profit_pct if min_profit_pct is not None else CONFIG.min_profit_pct
    enabled = enabled_exchanges or [e for e in Exchange if CONFIG.exchanges.get(e.value, None)]

    iteration = 0
    running = True

    def stop():
        nonlocal running
        running = False

    # Handle Ctrl+C
    try:
        signal.signal(signal.SIGINT, lambda *_: stop())
    except Exception:
        pass

    while running:
        iteration += 1
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")

        all_opportunities: list[ArbitrageOpportunity] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for pair in pairs:
                prices = await fetch_all_prices(pair, enabled)
                opps = find_arbitrage_opportunities(prices, pair)

                # Filter to only viable ones
                viable = [o for o in opps if o.is_viable(min_profit)]
                all_opportunities.extend(viable)

        # Sort all across pairs by profit
        all_opportunities.sort(key=lambda o: o.profit_pct, reverse=True)

        # Emit top opportunities
        if all_opportunities and on_opportunity:
            for opp in all_opportunities[:5]:  # top 5
                on_opportunity(opp)

        await asyncio.sleep(interval)

    logger.info("Monitor stopped after %d iterations.", iteration)

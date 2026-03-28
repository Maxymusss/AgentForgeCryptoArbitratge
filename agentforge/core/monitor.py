"""Async multi-exchange monitor — polls all exchanges concurrently using real bid/ask prices."""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Callable

import httpx

from ..config import CONFIG
from ..exchanges import (
    binance_bid_ask,
    coinbase_bid_ask,
    kraken_bid_ask,
    bybit_bid_ask,
    okx_bid_ask,
    gateio_bid_ask,
    Exchange,
)
from ..models import ArbitrageOpportunity
from .arbitrage import find_arbitrage_opportunities

logger = logging.getLogger(__name__)

_EXCHANGE_FETCHERS = {
    Exchange.BINANCE:  binance_bid_ask,
    Exchange.COINBASE: coinbase_bid_ask,
    Exchange.KRAKEN:   kraken_bid_ask,
    Exchange.BYBIT:    bybit_bid_ask,
    Exchange.OKX:      okx_bid_ask,
    Exchange.GATEIO:   gateio_bid_ask,
}

# Semaphore to limit concurrent exchange requests (rate-limit protection)
_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(10)


async def fetch_all_bid_asks(
    pair: str,
    exchanges: list[Exchange],
) -> dict[Exchange, tuple[float | None, float | None]]:
    """Fetch bid/ask prices from all exchanges concurrently.

    Args:
        pair: Binance-style symbol.
        exchanges: List of exchanges to query.

    Returns:
        Dict mapping Exchange → (bid, ask).
    """
    async def fetch_one(exchange: Exchange):
        fetcher = _EXCHANGE_FETCHERS.get(exchange)
        if fetcher is None:
            return exchange, (None, None)
        async with _CONCURRENCY_SEMAPHORE:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, fetcher, pair)
        return exchange, result

    results = await asyncio.gather(*(fetch_one(ex) for ex in exchanges))
    return dict(results)


async def monitor_loop(
    pairs: list[str],
    interval: int | None = None,
    min_profit_pct: float | None = None,
    on_opportunity: Callable[[ArbitrageOpportunity], None] | None = None,
    enabled_exchanges: list[Exchange] | None = None,
    telegram_enabled: bool = False,
    max_results: int = 5,
) -> None:
    interval = interval or CONFIG.poll_interval
    min_profit = min_profit_pct if min_profit_pct is not None else CONFIG.min_profit_pct
    enabled = enabled_exchanges or [e for e in Exchange if CONFIG.exchanges.get(e.value)]

    # Lazy-import Telegram to avoid circular deps
    telegram_alerts = None
    if telegram_enabled:
        try:
            from ..alerts.telegram import send_opportunity as _telegram_send
            telegram_alerts = _telegram_send
        except Exception as exc:
            logger.warning("Failed to load Telegram alerts: %s", exc)

    iteration = 0
    running = True

    def stop():
        nonlocal running
        running = False

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
                bid_asks = await fetch_all_bid_asks(pair, enabled)
                opps = find_arbitrage_opportunities(bid_asks, pair)
                viable = [o for o in opps if o.is_viable(min_profit)]
                all_opportunities.extend(viable)

        all_opportunities.sort(key=lambda o: o.profit_pct, reverse=True)

        if all_opportunities:
            for opp in all_opportunities[:max_results]:
                if on_opportunity:
                    on_opportunity(opp)
                if telegram_alerts:
                    telegram_alerts(opp)

        await asyncio.sleep(interval)

    logger.info("Monitor stopped after %d iterations.", iteration)

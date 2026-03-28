"""Real-time price monitor — polls exchanges and detects arbitrage opportunities."""

from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Callable

from rich.console import Console
from rich.table import Table

from ..config import CONFIG
from ..exchanges import binance, coinbase
from ..models import ArbitrageOpportunity
from .arbitrage import find_best_arbitrage

logger = logging.getLogger(__name__)
console = Console()

# Flag to handle graceful shutdown
_running = True


def _signal_handler(signum: int, frame) -> None:
    global _running
    logger.info("Shutdown signal received — stopping monitor...")
    _running = False


def monitor(
    pairs: tuple[str, ...] | None = None,
    interval: int | None = None,
    min_profit_pct: float | None = None,
    on_opportunity: Callable[[ArbitrageOpportunity], None] | None = None,
) -> None:
    """Run the arbitrage monitoring loop.

    Args:
        pairs:          Trading pairs to monitor. Defaults to CONFIG.trading_pairs.
        interval:       Poll interval in seconds. Defaults to CONFIG.poll_interval.
        min_profit_pct: Minimum net profit % to flag. Defaults to CONFIG.min_profit_pct.
        on_opportunity: Optional callback for each detected opportunity.
    """
    global _running
    _running = True

    # Handle Ctrl+C / SIGINT gracefully
    signal.signal(signal.SIGINT, _signal_handler)

    pairs = pairs or CONFIG.trading_pairs
    interval = interval or CONFIG.poll_interval
    min_profit = min_profit_pct if min_profit_pct is not None else CONFIG.min_profit_pct

    console.print(f"\n🚀 [bold cyan]AgentForge Arbitrage Monitor[/bold cyan]")
    console.print(f"   Pairs:     {', '.join(pairs)}")
    console.print(f"   Interval:  {interval}s")
    console.print(f"   Min profit: {min_profit}%\n")

    header_printed = False
    iteration = 0

    while _running:
        iteration += 1
        timestamp = time.strftime("%H:%M:%S")

        table = Table(title=f"Arbitrage Scan #{iteration} — {timestamp}")
        table.add_column("Pair", style="cyan")
        table.add_column("Binance", justify="right", style="yellow")
        table.add_column("Coinbase", justify="right", style="magenta")
        table.add_column("Best Direction", style="green")
        table.add_column("Net Profit %", justify="right")
        table.add_column("Status", justify="center")

        found_viable = False

        for pair in pairs:
            binance_price = binance.fetch_price(pair)
            coinbase_price = coinbase.fetch_price(pair)

            if binance_price is None and coinbase_price is None:
                table.add_row(
                    pair,
                    "[red]ERR[/red]",
                    "[red]ERR[/red]",
                    "—",
                    "—",
                    "[red]NO DATA[/red]",
                )
                continue

            best = find_best_arbitrage(binance_price, coinbase_price, pair)

            if best:
                direction = f"{best.buy_exchange} → {best.sell_exchange}"
                profit_str = f"{best.profit_pct:+.4f}%"

                if best.profit_pct >= min_profit:
                    status = "[bold green]✅ VIABLE[/bold green]"
                    found_viable = True
                elif best.profit_pct > 0:
                    status = "[yellow]⚠️  MARGINAL[/yellow]"
                else:
                    status = "[dim]❌ BELOW FEE[/dim]"

                table.add_row(
                    pair,
                    f"{binance_price:,.4f}" if binance_price else "[dim]—[/dim]",
                    f"{coinbase_price:,.4f}" if coinbase_price else "[dim]—[/dim]",
                    direction,
                    profit_str,
                    status,
                )

                if best.is_viable(min_profit) and on_opportunity:
                    on_opportunity(best)
            else:
                table.add_row(
                    pair,
                    f"{binance_price:,.4f}" if binance_price else "[dim]—[/dim]",
                    f"{coinbase_price:,.4f}" if coinbase_price else "[dim]—[/dim]",
                    "—",
                    "—",
                    "[dim]NO ARB[/dim]",
                )

        console.print(table)

        if found_viable:
            console.print(
                "[bold green]💰 Viable opportunity detected! Check exchange balances and API limits before trading.[/bold green]\n"
            )

        # Sleep in small increments so we can exit quickly on signal
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    console.print("\n[bold red]Monitor stopped.[/bold red]")

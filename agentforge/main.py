"""AgentForge CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

from .config import CONFIG
from .core.monitor import monitor_loop
from .models import Exchange

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agentforge")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AgentForge — Multi-Exchange Crypto Arbitrage Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pair",
        type=str,
        default=None,
        help="Single trading pair (Binance-style, e.g. BTCUSDT).",
    )
    parser.add_argument(
        "--pairs",
        type=str,
        default=None,
        help="Comma-separated pairs (e.g. BTCUSDT,ETHUSDT).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Poll interval in seconds. Default: 1",
    )
    parser.add_argument(
        "--min-profit",
        type=float,
        default=None,
        help="Minimum net profit %% to flag. Default: 0.05",
    )
    parser.add_argument(
        "--exchanges",
        type=str,
        default=None,
        help="Comma-separated exchanges to use. Default: all enabled",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        default=False,
        help="Enable Telegram alerts.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve pairs
    if args.pairs:
        pairs = [p.strip().upper().replace("/", "") for p in args.pairs.split(",")]
    elif args.pair:
        pairs = [args.pair.strip().upper().replace("/", "")]
    else:
        pairs = list(CONFIG.trading_pairs)

    # Resolve exchanges
    if args.exchanges:
        exchanges = _parse_exchanges(args.exchanges)
    else:
        exchanges = None  # use all configured

    logger.info(
        "Starting monitor — pairs=%s, interval=%ss, min_profit=%s, telegram=%s",
        pairs,
        args.interval or CONFIG.poll_interval,
        args.min_profit or CONFIG.min_profit_pct,
        args.telegram,
    )

    try:
        asyncio.run(
            monitor_loop(
                pairs=pairs,
                interval=args.interval,
                min_profit_pct=args.min_profit,
                enabled_exchanges=exchanges,
            )
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        return 1

    return 0


def _parse_exchanges(raw: str) -> list[Exchange]:
    """Parse a comma-separated list of exchange names into Exchange enums."""
    result = []
    for name in raw.split(","):
        name = name.strip().lower()
        try:
            result.append(Exchange(name))
        except ValueError:
            logger.warning("Unknown exchange: %s — skipping", name)
    return result


if __name__ == "__main__":
    sys.exit(main())

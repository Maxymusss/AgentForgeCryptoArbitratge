"""AgentForge CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from .config import CONFIG
from .core.monitor import monitor

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agentforge")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AgentForge — Crypto Arbitrage Opportunity Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pair",
        type=str,
        default=None,
        help=(
            "Trading pair to monitor (Binance-style, e.g. BTCUSDT, ETHUSDT). "
            "Defaults to all pairs in TRADING_PAIRS env var or BTCUSDT,ETHUSDT,SOLUSDT."
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Poll interval in seconds. Default: from CONFIG or 10.",
    )
    parser.add_argument(
        "--min-profit",
        type=float,
        default=None,
        help="Minimum net profit percentage to flag as viable. Default: 0.1",
    )
    parser.add_argument(
        "--pairs",
        type=str,
        default=None,
        help="Comma-separated list of pairs (overrides --pair).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Resolve pairs
    if args.pairs:
        raw_pairs = [p.strip().upper().replace("/", "") for p in args.pairs.split(",")]
    elif args.pair:
        raw_pairs = (args.pair.strip().upper().replace("/", ""),)
    else:
        raw_pairs = CONFIG.trading_pairs

    logger.info(
        "Starting monitor — pairs=%s, interval=%s, min_profit=%s",
        raw_pairs,
        args.interval or CONFIG.poll_interval,
        args.min_profit or CONFIG.min_profit_pct,
    )

    try:
        monitor(
            pairs=raw_pairs,
            interval=args.interval,
            min_profit_pct=args.min_profit,
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as exc:
        logger.exception("Fatal error in monitor loop: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

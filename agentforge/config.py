"""Application configuration — loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final

from dotenv import load_dotenv

load_dotenv()


@dataclass
class FeeSchedule:
    """Exchange fee schedule."""

    maker_pct: float = 0.001   # 0.1%
    taker_pct: float = 0.001  # 0.1%


@dataclass
class Config:
    """Global application config."""

    # Exchange fee schedules
    binance_fees: FeeSchedule = field(default_factory=FeeSchedule)
    coinbase_fees: FeeSchedule = field(default_factory=FeeSchedule)

    # Trading pairs to monitor (use Binance-style symbols: BTCUSDT, ETHUSDT)
    trading_pairs: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

    # Poll interval in seconds
    poll_interval: int = 10

    # Minimum profit percentage to flag as an opportunity
    min_profit_pct: float = 0.1

    # API keys (optional for public endpoints)
    binance_api_key: str | None = os.getenv("BINANCE_API_KEY")
    binance_api_secret: str | None = os.getenv("BINANCE_API_SECRET")
    coinbase_api_key: str | None = os.getenv("COINBASE_API_KEY")
    coinbase_api_secret: str | None = os.getenv("COINBASE_API_SECRET")

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        pairs_raw = os.getenv("TRADING_PAIRS", "BTC/USDT,ETH/USDT,SOL/USDT")
        # Normalize "BTC/USDT" -> "BTCUSDT"
        pairs = tuple(p.replace("/", "") for p in pairs_raw.split(","))
        cfg = cls(trading_pairs=pairs)

        if interval := os.getenv("POLL_INTERVAL"):
            cfg.poll_interval = int(interval)
        if min_profit := os.getenv("MIN_PROFIT_PCT"):
            cfg.min_profit_pct = float(min_profit)

        return cfg


# Module-level singleton
CONFIG: Final[Config] = Config.from_env()

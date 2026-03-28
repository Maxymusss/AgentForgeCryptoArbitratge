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
    taker_pct: float = 0.001   # 0.1%


@dataclass
class ExchangeConfig:
    """Per-exchange configuration."""
    name: str
    enabled: bool = True
    fees: FeeSchedule = field(default_factory=FeeSchedule)


@dataclass
class Config:
    """Global application config."""

    # Exchange configurations
    exchanges: dict[str, ExchangeConfig] = field(default_factory=lambda: {
        "binance":  ExchangeConfig("Binance",  enabled=True,  fees=FeeSchedule(maker_pct=0.001, taker_pct=0.001)),
        "coinbase": ExchangeConfig("Coinbase", enabled=True,  fees=FeeSchedule(maker_pct=0.004, taker_pct=0.006)),
        "kraken":   ExchangeConfig("Kraken",   enabled=True,  fees=FeeSchedule(maker_pct=0.0016, taker_pct=0.0026)),
        "bybit":    ExchangeConfig("Bybit",    enabled=True,  fees=FeeSchedule(maker_pct=0.001, taker_pct=0.001)),
        "okx":      ExchangeConfig("OKX",       enabled=True,  fees=FeeSchedule(maker_pct=0.0008, taker_pct=0.001)),
        "gateio":   ExchangeConfig("Gate.io",  enabled=True,  fees=FeeSchedule(maker_pct=0.002, taker_pct=0.002)),
    })

    # Trading pairs to monitor (Binance-style: BTCUSDT, ETHUSDT)
    trading_pairs: tuple[str, ...] = (
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
        "BNBUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT",
        "DOTUSDT", "MATICUSDT", "LINKUSDT", "LTCUSDT",
        "UNIUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT",
        "FILUSDT", "NEARUSDT", "TRXUSDT", "DASHUSDT",
        "MANAUSDT", "AXSUSDT", "SANDUSDT", "CHZUSDT",
        "AAVEUSDT", "LRCUSDT", "ENJUSDT", "GALAUSDT",
        "APEUSDT", "SHIBUSDT", "KAVAUSDT", "KSMUSDT",
        "ZECUSDT", "XMRUSDT", "XTZUSDT", "EOSUSDT",
        "ALGOUSDT", "VETUSDT", "THETAUSDT", "FTMUSDT",
        "MKRUSDT", "COMPUSDT", "SNXUSDT", "YFIUSDT",
        "SUSHIUSDT", "CRVUSDT", "LDOUSDT", "APEUSDT",
        "GMXUSDT", "RUNEUSDT",
    )

    # How many of the top coins to scan (from CoinGecko)
    top_coins_limit: int = 50

    # Poll interval in seconds (1s for live arbitrage)
    poll_interval: int = 1

    # Minimum net profit percentage to flag as an opportunity
    min_profit_pct: float = 0.05

    # Telegram alerts
    telegram_enabled: bool = True
    telegram_bot_token: str = os.getenv(
        "TELEGRAM_BOT_TOKEN", "8782066565:AAHNlnYFgp0-7MeLpJ2S4BCLNx014uJ9aBA"
    )
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")

    # API keys (optional for public endpoints)
    binance_api_key: str | None = os.getenv("BINANCE_API_KEY")
    binance_api_secret: str | None = os.getenv("BINANCE_API_SECRET")
    coinbase_api_key: str | None = os.getenv("COINBASE_API_KEY")
    coinbase_api_secret: str | None = os.getenv("COINBASE_API_SECRET")

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        pairs_raw = os.getenv("TRADING_PAIRS")
        if pairs_raw:
            pairs = tuple(p.strip().upper().replace("/", "") for p in pairs_raw.split(","))
        else:
            pairs = cls().trading_pairs

        cfg = cls(trading_pairs=pairs)

        if interval := os.getenv("POLL_INTERVAL"):
            cfg.poll_interval = int(interval)
        if min_profit := os.getenv("MIN_PROFIT_PCT"):
            cfg.min_profit_pct = float(min_profit)

        return cfg


CONFIG: Final[Config] = Config.from_env()

"""Data models for AgentForge."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Exchange(Enum):
    BINANCE  = "binance"
    COINBASE = "coinbase"
    KRAKEN   = "kraken"
    BYBIT    = "bybit"
    OKX      = "okx"
    GATEIO   = "gateio"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def all(cls) -> list["Exchange"]:
        return list(cls)


@dataclass
class PriceTick:
    """A single price quote from one exchange."""
    exchange: Exchange
    symbol: str        # Binance-style: BTCUSDT
    price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"PriceTick({self.exchange.value} {self.symbol} {self.price:.4f})"


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity between two exchanges."""

    buy_exchange: str
    sell_exchange: str
    pair: str              # e.g. "BTCUSDT"
    buy_price: float       # Price paid on buy exchange
    sell_price: float      # Price received on sell exchange
    profit_pct: float      # Net profit percentage after fees
    raw_spread_pct: float  # Gross spread before fees
    volume_hint: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_viable(self, min_profit_pct: float) -> bool:
        """Check if opportunity meets minimum profit threshold."""
        return self.profit_pct >= min_profit_pct

    def __str__(self) -> str:
        flag = "✅ VIABLE" if self.profit_pct >= 0.1 else "⚠️  LOW"
        return (
            f"{flag} | {self.pair} | "
            f"Buy {self.buy_exchange} @ {self.buy_price:,.4f} → "
            f"Sell {self.sell_exchange} @ {self.sell_price:,.4f} | "
            f"Spread: {self.raw_spread_pct:+.4f}% | "
            f"Net: {self.profit_pct:+.4f}% | {self.timestamp:%H:%M:%S}"
        )

    def to_telegram(self) -> str:
        """Format for Telegram alert."""
        return (
            f"💰 <b>Arbitrage Opportunity</b>\n\n"
            f"Pair: <code>{self.pair}</code>\n"
            f"Buy:  <b>{self.buy_exchange}</b> @ ${self.buy_price:,.4f}\n"
            f"Sell: <b>{self.sell_exchange}</b> @ ${self.sell_price:,.4f}\n\n"
            f"Spread: <code>{self.raw_spread_pct:+.4f}%</code>\n"
            f"Net profit: <b>{self.profit_pct:+.4f}%</b>\n\n"
            f"⚠️ Verify balances & API limits before trading!"
        )

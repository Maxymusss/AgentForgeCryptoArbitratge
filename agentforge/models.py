"""Data models for AgentForge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity between two exchanges."""

    buy_exchange: str
    sell_exchange: str
    pair: str              # e.g. "BTCUSDT"
    buy_price: float      # Price paid on buy exchange
    sell_price: float     # Price received on sell exchange
    profit_pct: float      # Net profit percentage after fees
    raw_spread_pct: float # Gross spread before fees
    volume_hint: float | None  # Approximate 24h volume (if available)
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

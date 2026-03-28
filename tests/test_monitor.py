"""Tests for the monitor module."""

from __future__ import annotations

from agentforge.models import ArbitrageOpportunity


class TestArbitrageOpportunityModel:
    """Tests for the ArbitrageOpportunity dataclass."""

    def test_is_viable_above_threshold(self):
        opp = ArbitrageOpportunity(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="BTCUSDT",
            buy_price=100.0,
            sell_price=100.35,
            profit_pct=0.15,
            raw_spread_pct=0.35,
        )
        assert opp.is_viable(min_profit_pct=0.1) is True
        assert opp.is_viable(min_profit_pct=0.2) is False

    def test_is_viable_at_threshold(self):
        opp = ArbitrageOpportunity(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="ETHUSDT",
            buy_price=100.0,
            sell_price=100.20,
            profit_pct=0.0,
            raw_spread_pct=0.20,
        )
        assert opp.is_viable(min_profit_pct=0.0) is True
        assert opp.is_viable(min_profit_pct=0.1) is False

    def test_str_representation(self):
        opp = ArbitrageOpportunity(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="BTCUSDT",
            buy_price=100.0,
            sell_price=100.35,
            profit_pct=0.15,
            raw_spread_pct=0.35,
        )
        s = str(opp)
        assert "BTCUSDT" in s
        assert "Binance" in s
        assert "Coinbase" in s
        assert "0.3500%" in s  # raw spread
        assert "0.1500%" in s  # net profit

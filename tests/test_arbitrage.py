"""Tests for the arbitrage detection engine."""

from __future__ import annotations

import pytest

from agentforge.core.arbitrage import compare_prices, find_best_arbitrage
from agentforge.models import ArbitrageOpportunity


class TestComparePrices:
    """Unit tests for compare_prices()."""

    def test_no_profit_when_prices_equal(self):
        """Equal prices with 0.1% fee each should yield negative net profit."""
        opp = compare_prices(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="BTCUSDT",
            buy_price=100.0,
            sell_price=100.0,
        )
        assert opp is not None
        assert opp.raw_spread_pct == 0.0
        assert opp.profit_pct == pytest.approx(-0.2)  # 0.1% + 0.1% fees

    def test_profitable_opportunity(self):
        """0.3% spread with 0.2% total fees should yield ~0.1% net profit."""
        # Buy at 100 on Binance, sell at 100.30 on Coinbase
        opp = compare_prices(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="ETHUSDT",
            buy_price=100.0,
            sell_price=100.30,
        )
        assert opp is not None
        assert opp.raw_spread_pct == pytest.approx(0.3)
        assert opp.profit_pct == pytest.approx(0.1)  # 0.3 - 0.2

    def test_unprofitable_small_spread(self):
        """0.15% spread is not enough to cover 0.2% in fees."""
        opp = compare_prices(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="BTCUSDT",
            buy_price=100.0,
            sell_price=100.15,
        )
        assert opp is not None
        assert opp.profit_pct == pytest.approx(-0.05)  # 0.15 - 0.2

    def test_zero_price_returns_none(self):
        assert compare_prices("Binance", "Coinbase", "BTCUSDT", 0.0, 100.0) is None
        assert compare_prices("Binance", "Coinbase", "BTCUSDT", 100.0, 0.0) is None

    def test_negative_price_returns_none(self):
        assert compare_prices("Binance", "Coinbase", "BTCUSDT", -100.0, 100.0) is None

    def test_viable_opportunity(self):
        opp = compare_prices(
            buy_exchange="Binance",
            sell_exchange="Coinbase",
            pair="BTCUSDT",
            buy_price=100.0,
            sell_price=100.35,
        )
        assert opp is not None
        assert opp.profit_pct == pytest.approx(0.15)
        assert opp.is_viable(min_profit_pct=0.1) is True
        assert opp.is_viable(min_profit_pct=0.2) is False


class TestFindBestArbitrage:
    """Unit tests for find_best_arbitrage()."""

    def test_both_prices_none_returns_none(self):
        assert find_best_arbitrage(None, None, "BTCUSDT") is None

    def test_only_binance_price_logs_warning(self, caplog):
        result = find_best_arbitrage(100.0, None, "BTCUSDT")
        assert result is None
        assert "Coinbase price unavailable" in caplog.text

    def test_only_coinbase_price_logs_warning(self, caplog):
        result = find_best_arbitrage(None, 100.0, "BTCUSDT")
        assert result is None
        assert "Binance price unavailable" in caplog.text

    def test_returns_best_direction(self):
        """Binance cheaper -> buy Binance, sell Coinbase is best direction."""
        result = find_best_arbitrage(
            binance_price=100.0,
            coinbase_price=100.30,
            pair="BTCUSDT",
        )
        assert result is not None
        assert result.buy_exchange == "Binance"
        assert result.sell_exchange == "Coinbase"
        assert result.profit_pct == pytest.approx(0.1)  # spread 0.3% - 0.2% fees

    def test_reverse_direction_profitable(self):
        """Coinbase cheaper -> buy Coinbase, sell Binance is best direction."""
        result = find_best_arbitrage(
            binance_price=100.40,
            coinbase_price=100.0,
            pair="BTCUSDT",
        )
        assert result is not None
        assert result.buy_exchange == "Coinbase"
        assert result.sell_exchange == "Binance"
        assert result.profit_pct == pytest.approx(0.2)  # spread 0.4% - 0.2% fees

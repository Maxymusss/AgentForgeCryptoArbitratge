"""Tests for the multi-exchange arbitrage detection engine."""

from __future__ import annotations

import pytest

from agentforge.core.arbitrage import find_arbitrage_opportunities, best_opportunity
from agentforge.models import Exchange


class TestFindArbitrageOpportunities:
    """Unit tests for find_arbitrage_opportunities()."""

    def test_equal_prices_all_directions_returned(self):
        """With equal prices, all directional pairs are returned (fees make them negative)."""
        prices = {
            Exchange.BINANCE: 100.0,
            Exchange.COINBASE: 100.0,
        }
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        assert len(opps) == 2  # bin→coinbase, coinbase→bin
        for opp in opps:
            assert opp.raw_spread_pct == 0.0

    def test_spread_detected_correctly(self):
        """A 0.3% spread is correctly calculated."""
        prices = {
            Exchange.BINANCE: 100.0,
            Exchange.COINBASE: 100.30,
        }
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        buy_bnb = next((o for o in opps if o.buy_exchange == "binance"), None)
        assert buy_bnb is not None
        assert buy_bnb.raw_spread_pct == pytest.approx(0.3)

    def test_net_profit_after_fees(self):
        """Net = raw spread - binance taker (0.1%) - coinbase taker (0.6%) = 0.3 - 0.7 = -0.4%"""
        prices = {
            Exchange.BINANCE: 100.0,
            Exchange.COINBASE: 100.30,
        }
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        buy_bnb = next((o for o in opps if o.buy_exchange == "binance"), None)
        assert buy_bnb is not None
        # Fees: binance 0.1% + coinbase 0.6% = 0.7%
        # Spread 0.3% - 0.7% = -0.4%
        assert buy_bnb.profit_pct == pytest.approx(-0.4)

    def test_null_prices_skipped(self):
        """None prices are skipped without crashing."""
        prices = {
            Exchange.BINANCE: 100.0,
            Exchange.COINBASE: None,
            Exchange.KRAKEN: 100.2,
        }
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        # Should not reference coinbase as buy or sell
        for opp in opps:
            assert opp.buy_exchange != "coinbase" or opp.sell_exchange != "coinbase"

    def test_empty_prices_returns_empty(self):
        prices: dict[Exchange, float] = {}
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        assert opps == []

    def test_all_six_exchanges_nxn(self):
        """With 6 exchanges, 30 directional pairs (6×5)."""
        prices = {e: 100.0 for e in Exchange}
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        # 6 exchanges × 5 other exchanges = 30
        assert len(opps) == 30

    def test_viable_opportunity_coinbase_bybit(self):
        """Coinbase (buy 0.1%) + Bybit (sell 0.1%), 0.3% spread = 0.1% net."""
        prices = {
            Exchange.COINBASE: 100.0,
            Exchange.BYBIT: 100.30,
        }
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        buy_cb = next((o for o in opps if o.buy_exchange == "coinbase"), None)
        assert buy_cb is not None
        # Fees: coinbase 0.6% + bybit 0.1% = 0.7%
        # Spread 0.3% - 0.7% = -0.4%
        assert buy_cb.profit_pct == pytest.approx(-0.4)

    def test_sort_by_profit_descending(self):
        """Opportunities are sorted by profit_pct, most profitable first."""
        prices = {
            Exchange.BINANCE: 100.0,
            Exchange.COINBASE: 100.30,
            Exchange.KRAKEN: 100.05,
        }
        opps = find_arbitrage_opportunities(prices, "BTCUSDT")
        profits = [o.profit_pct for o in opps]
        assert profits == sorted(profits, reverse=True)


class TestBestOpportunity:
    """Unit tests for best_opportunity()."""

    def test_returns_none_when_all_unprofitable(self):
        """best_opportunity returns None when all spreads are eaten by fees."""
        prices = {e: 100.0 for e in Exchange}
        best = best_opportunity(prices, "BTCUSDT")
        assert best is None

    def test_returns_none_for_empty(self):
        best = best_opportunity({}, "BTCUSDT")
        assert best is None

    def test_returns_none_for_single_exchange(self):
        prices = {Exchange.BINANCE: 100.0}
        best = best_opportunity(prices, "BTCUSDT")
        assert best is None

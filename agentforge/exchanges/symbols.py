"""Symbol normalization utility — converts between exchange-specific symbol formats.

Examples:
    BTCUSDT (Binance/Bybit)  →  BTC-USD (Coinbase)
    BTCUSDT                  →  XXBTZUSD (Kraken)
    BTCUSDT                  →  BTC_USDT (Gate.io)
    BTCUSDT                  →  BTC-USDT (OKX)
"""

from __future__ import annotations

from enum import Enum


class Exchange(Enum):
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"
    OKX = "okx"
    GATEIO = "gateio"


# Base quote currencies to strip from symbol
_QUOTES = {"USDT", "USD", "USDC", "BUSD", "DAI"}

# Mapping: exchange → (quote_char, separator)
_EXCHANGE_FORMATS: dict[Exchange, tuple[str, str]] = {
    Exchange.BINANCE:  ("",    ""),      # BTCUSDT
    Exchange.COINBASE: ("-",   "-"),     # BTC-USD
    Exchange.KRAKEN:  ("X",   "Z"),     # XXBTZUSD  (base gets X prefix, USD gets Z prefix)
    Exchange.BYBIT:    ("",    ""),      # BTCUSDT
    Exchange.OKX:      ("-",   "-"),     # BTC-USDT
    Exchange.GATEIO:  ("_",   "_"),     # BTC_USDT
}


def normalize(symbol: str, to_exchange: Exchange) -> str:
    """Convert a base symbol (e.g. BTCUSDT) to the target exchange format.

    Args:
        symbol: Symbol in 'BTCUSDT' format (base + quote, no separator).
        to_exchange: Target exchange.

    Returns:
        Exchange-specific symbol string.

    Examples:
        normalize("BTCUSDT", Exchange.COINBASE) → "BTC-USD"
        normalize("BTCUSDT", Exchange.KRAKEN)     → "XXBTZUSD"
        normalize("ETHUSDT", Exchange.GATEIO)     → "ETH_USDT"
    """
    symbol = symbol.upper()

    # Extract base and quote
    base, quote = _split_base_quote(symbol)
    if base is None or quote is None:
        return symbol  # Fallback: return as-is

    fmt, sep = _EXCHANGE_FORMATS[to_exchange]

    if to_exchange == Exchange.KRAKEN:
        # Kraken has quirky format: XXBT for BTC, ZUSD for USD
        return f"X{base}Z{quote}"

    return f"{base}{sep}{quote}"


def _split_base_quote(symbol: str) -> tuple[str | None, str | None]:
    """Split a plain symbol like BTCUSDT into (BTC, USDT)."""
    for quote in _QUOTES:
        if symbol.endswith(quote):
            base = symbol[: -len(quote)]
            if base:
                return base, quote
    return None, None


def to_binance_style(symbol: str) -> str:
    """Convert any exchange symbol back to Binance/Bybit style (BTCUSDT)."""
    upper = symbol.upper()
    for quote in _QUOTES:
        if upper.endswith(quote):
            base = upper[: -len(quote)]
            if base:
                return f"{base}{quote}"
    return upper

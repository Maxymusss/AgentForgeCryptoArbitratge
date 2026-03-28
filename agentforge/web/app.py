"""AgentForge Web Dashboard — FastAPI + WebSocket server for live arbitrage monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import CONFIG
from ..exchanges import (
    binance_bid_ask, coinbase_bid_ask, kraken_bid_ask,
    bybit_bid_ask, okx_bid_ask, gateio_bid_ask,
    Exchange,
)
from ..models import ArbitrageOpportunity
from .arbitrage_web import find_arbitrage_opportunities

logger = logging.getLogger("agentforge.web")

app = FastAPI(title="AgentForge Dashboard")
app.mount("/static", StaticFiles(directory="agentforge/web/static"), name="static")

_EXCHANGE_FETCHERS = {
    Exchange.BINANCE:  binance_bid_ask,
    Exchange.COINBASE: coinbase_bid_ask,
    Exchange.KRAKEN:   kraken_bid_ask,
    Exchange.BYBIT:    bybit_bid_ask,
    Exchange.OKX:      okx_bid_ask,
    Exchange.GATEIO:   gateio_bid_ask,
}

_ENABLED_EXCHANGES = [
    e for e in Exchange
    if CONFIG.exchanges.get(e.value) and CONFIG.exchanges[e.value].enabled
]

# Top 50 fallback pairs when CoinGecko is rate-limited
_FALLBACK_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "XLMUSDT",
    "ETCUSDT", "FILUSDT", "NEARUSDT", "TRXUSDT", "MANAUSDT",
    "AXSUSDT", "SANDUSDT", "CHZUSDT", "AAVEUSDT", "LRCUSDT",
    "ENJUSDT", "GALAUSDT", "APEUSDT", "SHIBUSDT", "KAVAUSDT",
    "ZECUSDT", "XMRUSDT", "XTZUSDT", "EOSUSDT", "ALGOUSDT",
    "VETUSDT", "THETAUSDT", "FTMUSDT", "MKRUSDT", "COMPUSDT",
    "SNXUSDT", "YFIUSDT", "SUSHIUSDT", "CRVUSDT", "LDOUSDT",
    "GMXUSDT", "RUNEUSDT", "INCHUSDT", "BTCUSDC",
]

# ─── WebSocket manager ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, msg: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ─── Price fetch loop ─────────────────────────────────────────────────────────

async def fetch_bid_asks(pair: str) -> dict[str, dict[str, float | None]]:
    """Fetch bid/ask from all exchanges concurrently."""
    result: dict[str, dict[str, float | None]] = {}

    async def fetch_one(exchange: Exchange, fetcher):
        loop = asyncio.get_running_loop()
        bid, ask = await loop.run_in_executor(None, fetcher, pair)
        return exchange.value, {"bid": bid, "ask": ask}

    tasks = [fetch_one(ex, _EXCHANGE_FETCHERS[ex]) for ex in _ENABLED_EXCHANGES]
    results = await asyncio.gather(*tasks)
    for ex_name, prices in results:
        result[ex_name] = prices
    return result


async def price_fetch_loop():
    """Continuously fetch bid/ask from all exchanges and broadcast to WebSocket clients."""
    from ..api.coingecko import get_top_coins, get_binance_symbol

    # Try CoinGecko to get dynamic top-50 pairs
    loop = asyncio.get_running_loop()
    coins = []
    for attempt in range(3):
        coins = await loop.run_in_executor(None, lambda: get_top_coins(limit=50))
        if len(coins) >= 10:
            break
        logger.warning("CoinGecko returned only %d coins, retrying (%d/3)", len(coins), attempt + 2)
        await asyncio.sleep(2)

    STABLECOINS = {"USDT", "USDC", "BUSD", "DAI", "FDUSD", "PAX", "TUSD", "USDP"}
    coins = [c for c in coins if c.symbol not in STABLECOINS]

    if len(coins) >= 10:
        pairs = [get_binance_symbol(c) for c in coins]
        logger.info("Monitoring %d pairs from CoinGecko top 50", len(pairs))
    else:
        pairs = _FALLBACK_PAIRS
        logger.info("Using fallback list of %d pairs", len(pairs))

    while True:
        try:
            for pair in pairs:
                bid_asks = await fetch_bid_asks(pair)

                # Find arbitrage: buy at lowest ASK, sell at highest BID
                arb_opps: list[dict[str, Any]] = []
                for ex_name, prices in bid_asks.items():
                    bid = prices.get("bid")
                    ask = prices.get("ask")
                    if bid and ask:
                        pass  # price data available

                # Run arbitrage detection using bid-ask engine
                from ..models import Exchange as ExEnum
                exchange_enum_map = {e.value: e for e in _ENABLED_EXCHANGES}
                bid_ask_enums: dict[ExEnum, tuple[float | None, float | None]] = {}
                for ex_name, prices in bid_asks.items():
                    if ex_name in exchange_enum_map:
                        ex = exchange_enum_map[ex_name]
                        bid_ask_enums[ex] = (prices.get("bid"), prices.get("ask"))

                opps = find_arbitrage_opportunities(bid_ask_enums, pair)
                arb_opps = [
                    {
                        "buy_exchange": o.buy_exchange,
                        "sell_exchange": o.sell_exchange,
                        "pair": o.pair,
                        "buy_price": o.buy_price,
                        "sell_price": o.sell_price,
                        "raw_spread_pct": o.raw_spread_pct,
                        "profit_pct": o.profit_pct,
                    }
                    for o in opps
                    if o.profit_pct > 0
                ]

                payload = {
                    "type": "tick",
                    "pair": pair,
                    "prices": bid_asks,
                    "opportunities": arb_opps,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await manager.broadcast(json.dumps(payload))

            await asyncio.sleep(CONFIG.poll_interval)

        except Exception as exc:
            logger.warning("Price fetch error: %s", exc)
            await asyncio.sleep(5)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    asyncio.create_task(price_fetch_loop())


@app.get("/")
async def root():
    with open("agentforge/web/templates/dashboard.html") as f:
        return HTMLResponse(content=f.read())


@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

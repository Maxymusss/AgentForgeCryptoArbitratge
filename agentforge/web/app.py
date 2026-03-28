"""AgentForge Web Dashboard — FastAPI + WebSocket server for live arbitrage monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import CONFIG
from ..exchanges import (
    binance_fetch, coinbase_fetch, kraken_fetch,
    bybit_fetch, okx_fetch, gateio_fetch,
    Exchange,
)
from ..models import ArbitrageOpportunity
from .arbitrage_web import find_arbitrage_opportunities

logger = logging.getLogger("agentforge.web")

app = FastAPI(title="AgentForge Dashboard")
app.mount("/static", StaticFiles(directory="agentforge/web/static"), name="static")

# ─── WebSocket clients ──────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ─── Exchange fetchers ─────────────────────────────────────────────────────────

_EXCHANGE_FETCHERS = {
    Exchange.BINANCE:  binance_fetch,
    Exchange.COINBASE: coinbase_fetch,
    Exchange.KRAKEN:  kraken_fetch,
    Exchange.BYBIT:   bybit_fetch,
    Exchange.OKX:     okx_fetch,
    Exchange.GATEIO: gateio_fetch,
}

_ENABLED_EXCHANGES = [
    e for e in Exchange
    if CONFIG.exchanges.get(e.value, None) and CONFIG.exchanges[e.value].enabled
]


# ─── Price fetch loop ─────────────────────────────────────────────────────────

async def price_fetch_loop():
    """Continuously fetch prices and broadcast to all WebSocket clients."""
    pairs = list(CONFIG.trading_pairs)

    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for pair in pairs:
                    prices: dict[str, float | None] = {}
                    opps: list[dict[str, Any]] = []

                    for exchange in _ENABLED_EXCHANGES:
                        fetcher = _EXCHANGE_FETCHERS.get(exchange)
                        if fetcher:
                            loop = asyncio.get_running_loop()
                            price = await loop.run_in_executor(None, fetcher, pair)
                            prices[exchange.value] = price

                    # Find arbitrage opportunities
                    price_floats = {
                        e: prices[e.value]
                        for e in _ENABLED_EXCHANGES
                        if prices.get(e.value) is not None
                    }
                    arb_opps = find_arbitrage_opportunities(price_floats, pair)
                    opps = [
                        {
                            "buy_exchange": o.buy_exchange,
                            "sell_exchange": o.sell_exchange,
                            "pair": o.pair,
                            "buy_price": o.buy_price,
                            "sell_price": o.sell_price,
                            "raw_spread_pct": o.raw_spread_pct,
                            "profit_pct": o.profit_pct,
                        }
                        for o in arb_opps
                        if o.profit_pct > 0
                    ]

                    payload = {
                        "type": "tick",
                        "pair": pair,
                        "prices": prices,
                        "opportunities": opps,
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
            # Keep connection alive — client sends pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

"""AgentForge Web Dashboard — FastAPI + WebSocket server for live arbitrage monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
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

logger = logging.getLogger("agentforge.web")

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_STATIC_DIR = _BASE_DIR / "agentforge" / "web" / "static"
_TEMPLATE_DIR = _BASE_DIR / "agentforge" / "web" / "templates"

app = FastAPI(title="AgentForge Dashboard")
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_EXCHANGE_FETCHERS = {
    Exchange.BINANCE:  binance_bid_ask,
    Exchange.COINBASE: coinbase_bid_ask,
    Exchange.KRAKEN:   kraken_bid_ask,
    Exchange.BYBIT:    bybit_bid_ask,
    Exchange.OKX:      okx_bid_ask,
    Exchange.GATEIO:  gateio_bid_ask,
}

_ENABLED_EXCHANGES = [
    e for e in Exchange
    if CONFIG.exchanges.get(e.value) and CONFIG.exchanges[e.value].enabled
]

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


# ─── Price fetch ────────────────────────────────────────────────────────────

async def fetch_bid_asks(pair: str) -> dict[str, dict[str, float | None]]:
    """Fetch bid/ask from all enabled exchanges concurrently."""

    async def fetch_one(exchange: Exchange, fetcher) -> tuple[str, dict[str, float | None]]:
        loop = asyncio.get_running_loop()
        bid, ask = await loop.run_in_executor(None, fetcher, pair)
        return exchange.value, {"bid": bid, "ask": ask}

    tasks = [fetch_one(ex, _EXCHANGE_FETCHERS[ex]) for ex in _ENABLED_EXCHANGES]
    results = await asyncio.gather(*tasks)
    return dict(results)


async def price_fetch_loop():
    """Continuously fetch bid/ask from all exchanges and broadcast to WebSocket clients."""
    from ..api.coingecko import get_top_coins, get_binance_symbol

    loop = asyncio.get_running_loop()

    # Try CoinGecko first for dynamic top-50
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

    # Import arbitrage engine here to avoid circular import
    from ..core.arbitrage import find_arbitrage_opportunities as find_opps
    from ..alerts.telegram import send_opportunity as _telegram_send

    def _send_telegram_alert(opp: ArbitrageOpportunity):
        """Send alert if Telegram is configured and profit threshold is met."""
        if not CONFIG.telegram_enabled:
            return
        try:
            loop.run_in_executor(None, _telegram_send, opp)
        except Exception:
            pass

    while True:
        try:
            for pair in pairs:
                bid_asks = await fetch_bid_asks(pair)

                # Build exchange enum → (bid, ask) for arbitrage engine
                bid_ask_enums: dict[Exchange, tuple[float | None, float | None]] = {}
                for ex_name, prices in bid_asks.items():
                    for ex in _ENABLED_EXCHANGES:
                        if ex.value == ex_name:
                            bid_ask_enums[ex] = (prices.get("bid"), prices.get("ask"))
                            break

                opps: list[ArbitrageOpportunity] = find_opps(bid_ask_enums, pair)

                arb_opps = []
                for o in opps:
                    try:
                        profit = getattr(o, "profit_pct", None)
                        buy_ex = getattr(o, "buy_exchange", "")
                        sell_ex = getattr(o, "sell_exchange", "")
                        buy_ex_cfg = CONFIG.exchanges.get(buy_ex.lower())
                        sell_ex_cfg = CONFIG.exchanges.get(sell_ex.lower())
                        buy_fee = round(buy_ex_cfg.fees.taker_pct * 100, 4) if buy_ex_cfg else 0
                        sell_fee = round(sell_ex_cfg.fees.taker_pct * 100, 4) if sell_ex_cfg else 0
                        total_fees = buy_fee + sell_fee
                        raw_spread = getattr(o, "raw_spread_pct", 0)
                        arb_opps.append({
                            "buy_exchange": buy_ex,
                            "sell_exchange": sell_ex,
                            "pair": getattr(o, "pair", pair),
                            "buy_price": getattr(o, "buy_price", 0),
                            "sell_price": getattr(o, "sell_price", 0),
                            "raw_spread_pct": raw_spread,
                            "profit_pct": profit if profit is not None else 0,
                            "total_fees_pct": round(total_fees, 4),
                            "buy_fee_pct": round(buy_fee, 4),
                            "sell_fee_pct": round(sell_fee, 4),
                        })
                        # Fire Telegram alert if profit exceeds threshold
                        if profit is not None and profit >= CONFIG.min_profit_pct:
                            _send_telegram_alert(o)
                    except Exception:
                        pass

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
    with open(_TEMPLATE_DIR / "dashboard.html", encoding="utf-8") as f:
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


# ─── Settings API ─────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """Return current settings (public fields only)."""
    from ..config import CONFIG as _cfg
    return {
        "min_profit_pct": _cfg.min_profit_pct,
        "telegram_enabled": _cfg.telegram_enabled,
        "poll_interval": _cfg.poll_interval,
        "enabled_exchanges": [e.value for e in _ENABLED_EXCHANGES],
        "all_exchanges": [e.value for e in Exchange],
    }


@app.post("/api/settings")
async def update_settings(body: dict):
    """Update settings — writes to settings.json and reloads CONFIG._settings."""
    from ..config import CONFIG as _cfg, _load_settings, _save_settings
    settings = _load_settings()
    changed = False
    if "min_profit_pct" in body:
        v = float(body["min_profit_pct"])
        settings["min_profit_pct"] = v
        _cfg._settings["min_profit_pct"] = v
        changed = True
    if "telegram_enabled" in body:
        v = bool(body["telegram_enabled"])
        settings["telegram_enabled"] = v
        _cfg._settings["telegram_enabled"] = v
        changed = True
    if "poll_interval" in body:
        v = int(body["poll_interval"])
        settings["poll_interval"] = v
        _cfg.poll_interval = v
        changed = True
    if changed:
        _save_settings(settings)
    return {"ok": True}


@app.get("/api/balances")
async def get_balances():
    """Return current exchange balances."""
    from ..config import CONFIG as _cfg
    return _cfg.exchange_balances


@app.post("/api/balances")
async def update_balances(body: dict):
    """Update exchange balances (mock)."""
    from ..config import CONFIG as _cfg, _load_settings, _save_settings
    settings = _load_settings()
    balances = body.get("balances", {})
    # Validate: must be numeric and >= 0
    cleaned = {}
    for ex, val in balances.items():
        try:
            v = float(val)
            if v < 0:
                v = 0.0
            cleaned[str(ex)] = round(v, 2)
        except (TypeError, ValueError):
            pass
    settings["exchange_balances"] = cleaned
    _cfg._settings["exchange_balances"] = cleaned
    _save_settings(settings)
    return {"ok": True, "balances": cleaned}


@app.get("/settings")
async def settings_page():
    with open(_TEMPLATE_DIR / "settings.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

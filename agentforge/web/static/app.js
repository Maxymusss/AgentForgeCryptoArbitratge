// ─── AgentForge WebSocket Client — bid/ask version ─────────────────────────────────

const WS_URL = `ws://${location.host}/ws/prices`;
const EXCHANGES = ['binance', 'coinbase', 'kraken', 'bybit', 'okx', 'gateio'];

// State: pair → { prices: { ex: { bid, ask } }, opps: [], timestamp }
const state = {};
const pairs = new Set();
let tickCount = 0;
let bestSpread = null;
let lastUpdate = null;

const $ = (id) => document.getElementById(id);

// ─── WebSocket ───────────────────────────────────────────────────────────────

function connect() {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        updateStatus(true);
        console.log('[WS] Connected');
    };

    ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
            handleTick(JSON.parse(event.data));
        } catch (e) {
            console.error('[WS] parse error:', e);
        }
    };

    ws.onclose = () => {
        updateStatus(false);
        console.warn('[WS] disconnected — retrying in 3s');
        setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
        console.error('[WS] error:', err);
        ws.close();
    };
}

function handleTick(msg) {
    tickCount++;
    const { pair, prices, opportunities, timestamp } = msg;
    pairs.add(pair);
    state[pair] = { prices, opportunities, timestamp };
    lastUpdate = new Date();

    renderPriceGrid();
    renderArbList();
    updateStats();
    updateClock();
}

function updateStatus(connected) {
    const dot = document.querySelector('.dot');
    const label = document.querySelector('.dot-label');
    if (connected) {
        dot.classList.add('connected');
        label.textContent = 'CONNECTED';
    } else {
        dot.classList.remove('connected');
        label.textContent = 'DISCONNECTED';
    }
}

// ─── Price Grid — bid/ask per exchange ──────────────────────────────────────
// For each pair:
//   - Show ASK (what it costs to buy) for each exchange → GREEN = cheapest ASK
//   - Show BID (what you get selling) for each exchange → RED = highest BID
//   - Spread column: highest BID − lowest ASK

function renderPriceGrid() {
    const rows = $('price-rows');
    rows.innerHTML = '';

    const allPairs = Array.from(pairs).sort();

    for (const pair of allPairs) {
        const data = state[pair];
        if (!data || !data.prices) continue;

        const { prices } = data;

        // Find lowest ASK across exchanges
        const asks = EXCHANGES
            .map(ex => ({ ex, ask: prices[ex]?.ask }))
            .filter(x => x.ask !== null && x.ask !== undefined);

        // Find highest BID across exchanges
        const bids = EXCHANGES
            .map(ex => ({ ex, bid: prices[ex]?.bid }))
            .filter(x => x.bid !== null && x.bid !== undefined);

        const lowestAsk = asks.length ? asks.reduce((a, b) => a.ask < b.ask ? a : b) : null;
        const highestBid = bids.length ? bids.reduce((a, b) => a.bid > b.bid ? a : b) : null;

        // Spread = highest_bid - lowest_ask (executable arb spread)
        let spread = null;
        if (highestBid && lowestAsk) {
            spread = highestBid.bid - lowestAsk.ask;
            spread = (spread / lowestAsk.ask) * 100;  // as %
        }

        const row = document.createElement('div');
        row.className = 'price-row';
        row.id = `row-${pair}`;

        let cells = [];

        for (const ex of EXCHANGES) {
            const p = prices[ex];
            if (!p) {
                cells.push('<span class="price-cell na">—</span>');
                continue;
            }
            const { bid, ask } = p;

            if (ask !== null && ask !== undefined) {
                // Show ASK price, color by cheapest/tallest
                let cls = 'price-cell';
                if (lowestAsk && ex === lowestAsk.ex) cls += ' cheapest-ask';
                cells.push(`<span class="${cls}" title="ASK">${fmt(ask)}</span>`);
            } else if (bid !== null && bid !== undefined) {
                let cls = 'price-cell';
                if (highestBid && ex === highestBid.ex) cls += ' highest-bid';
                cells.push(`<span class="${cls}" title="BID">${fmt(bid)}</span>`);
            } else {
                cells.push('<span class="price-cell na">—</span>');
            }
        }

        if (spread !== null) {
            const cls = spread > 0 ? 'spread-cell positive' : 'spread-cell';
            cells.push(`<span class="${cls}">${spread >= 0 ? '+' : ''}${spread.toFixed(4)}%</span>`);
        } else {
            cells.push('<span class="spread-cell">—</span>');
        }

        row.innerHTML = `<span class="pair-symbol">${pair}</span>` + cells.join('');
        rows.appendChild(row);
    }
}

// ─── Arbitrage list: top 10 by spread ──────────────────────────────────────────
// Shows: pair | buy @ LOWEST ASK → sell @ HIGHEST BID

function renderArbList() {
    const list = $('arb-list');
    const noOpps = $('no-opps');
    const countBadge = $('opp-count');

    // Collect spread per pair: buy at lowest ask, sell at highest bid
    const pairData = [];

    for (const pair of Object.keys(state)) {
        const data = state[pair];
        if (!data || !data.prices) continue;

        const { prices } = data;

        const asks = EXCHANGES
            .map(ex => ({ ex, ask: prices[ex]?.ask }))
            .filter(x => x.ask !== null && x.ask !== undefined);

        const bids = EXCHANGES
            .map(ex => ({ ex, bid: prices[ex]?.bid }))
            .filter(x => x.bid !== null && x.bid !== undefined);

        if (asks.length < 1 || bids.length < 1) continue;

        const lowestAsk = asks.reduce((a, b) => a.ask < b.ask ? a : b);
        const highestBid = bids.reduce((a, b) => a.bid > b.bid ? a : b);
        if (lowestAsk.ex === highestBid.ex) continue;

        const grossSpread = highestBid.bid - lowestAsk.ask;
        const grossSpreadPct = (grossSpread / lowestAsk.ask) * 100;
        const netProfit = grossSpreadPct - 0.20;  // approx 0.1% + 0.1% fees

        pairData.push({
            pair,
            buy_exchange: lowestAsk.ex,
            sell_exchange: highestBid.ex,
            buy_price: lowestAsk.ask,
            sell_price: highestBid.bid,
            spread: grossSpreadPct,
            netProfit,
        });
    }

    pairData.sort((a, b) => b.spread - a.spread);
    const top10 = pairData.slice(0, 10);

    countBadge.textContent = top10.length;

    if (top10.length === 0) {
        list.innerHTML = '';
        noOpps.style.display = 'flex';
        return;
    }

    noOpps.style.display = 'none';
    list.innerHTML = '';

    for (const opp of top10) {
        const card = document.createElement('div');
        card.className = 'arb-card' + (opp.spread > 0.05 ? ' high' : '');

        card.innerHTML = `
            <div class="arb-pair">${opp.pair}</div>
            <div class="arb-flow">
                <span class="arb-exchange" style="background:${exColor(opp.buy_exchange)}">${opp.buy_exchange.toUpperCase()}</span>
                <span class="arb-arrow">→</span>
                <span class="arb-exchange" style="background:${exColor(opp.sell_exchange)}">${opp.sell_exchange.toUpperCase()}</span>
            </div>
            <div class="arb-prices">
                <span>${fmt(opp.buy_price)} ASK</span>
                <span>${fmt(opp.sell_price)} BID</span>
            </div>
            <div class="arb-metrics">
                <div class="metric">
                    <span class="metric-label">SPREAD</span>
                    <span class="metric-value spread">+${opp.spread.toFixed(4)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">NET PROFIT</span>
                    <span class="metric-value profit">${opp.netProfit >= 0 ? '+' : ''}${opp.netProfit.toFixed(4)}%</span>
                </div>
            </div>
        `;
        list.appendChild(card);
    }

    if (top10.length > 0) bestSpread = top10[0].spread;
}

// ─── Stats ──────────────────────────────────────────────────────────────────

function updateStats() {
    $('stat-pairs').textContent = pairs.size;
    $('stat-best-spread').textContent =
        bestSpread !== null ? `${bestSpread >= 0 ? '+' : ''}${bestSpread.toFixed(4)}%` : '—';
    $('stat-best-profit').textContent =
        bestSpread !== null ? `${bestSpread - 0.2 >= 0 ? '+' : ''}${(bestSpread - 0.2).toFixed(4)}%` : '—';
    if (lastUpdate) $('stat-last').textContent = lastUpdate.toLocaleTimeString();
}

function updateClock() {
    $('clock').textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
}

function exColor(ex) {
    const c = {
        binance: '#f0b90b', coinbase: '#0052ff', kraken: '#5741d9',
        bybit: '#f7a800', okx: '#ffffff', gateio: '#17e78c'
    };
    return c[ex] || '#333';
}

function fmt(v) {
    if (v === null || v === undefined) return '—';
    return v.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: v < 1 ? 6 : 4,
    });
}

// ─── Boot ───────────────────────────────────────────────────────────────────

setInterval(updateClock, 1000);
updateClock();
connect();

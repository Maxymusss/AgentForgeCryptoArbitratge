// ─── AgentForge WebSocket Client ───────────────────────────────────────────

const WS_URL = `ws://${location.host}/ws/prices`;
const EXCHANGES = ['binance', 'coinbase', 'kraken', 'bybit', 'okx', 'gateio'];

// State
let ws = null;
let connected = false;
let tickCount = 0;
let pairs = new Set();
let bestProfit = null;
let lastUpdate = null;

const state = {}; // pair → { prices: {}, opps: [], timestamp }

const $ = (id) => document.getElementById(id);

// ─── WebSocket ──────────────────────────────────────────────────────────────

function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        connected = true;
        updateStatus(true);
        console.log('[WS] Connected');
    };

    ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
            const msg = JSON.parse(event.data);
            handleTick(msg);
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };

    ws.onclose = () => {
        connected = false;
        updateStatus(false);
        console.warn('[WS] Disconnected — reconnecting in 3s');
        setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
        console.error('[WS] Error:', err);
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
    renderArbitrageList();
    updateStats();
    updateClock();
}

function updateStatus(isConnected) {
    const dot = document.querySelector('.dot');
    const label = document.querySelector('.dot-label');
    if (isConnected) {
        dot.classList.add('connected');
        label.textContent = 'CONNECTED';
    } else {
        dot.classList.remove('connected');
        label.textContent = 'DISCONNECTED';
    }
}

// ─── Render: Price Grid ────────────────────────────────────────────────────

function renderPriceGrid() {
    const rows = $('price-rows');
    const allPairs = Array.from(pairs).sort();

    rows.innerHTML = '';

    for (const pair of allPairs) {
        const data = state[pair];
        if (!data) continue;

        const { prices } = data;

        // Find cheapest and dearest
        const validPrices = Object.entries(prices)
            .filter(([, v]) => v !== null)
            .sort((a, b) => a[1] - b[1]);

        const cheapest = validPrices[0]?.[0] || null;
        const dearest = validPrices[validPrices.length - 1]?.[0] || null;

        // Spread between cheapest and dearest
        let spread = null;
        if (validPrices.length >= 2) {
            const lo = validPrices[0][1];
            const hi = validPrices[validPrices.length - 1][1];
            spread = ((hi - lo) / lo) * 100;
        }

        const row = document.createElement('div');
        row.className = 'price-row';
        row.id = `row-${pair}`;

        const cells = [pair];

        for (const ex of EXCHANGES) {
            const p = prices[ex];
            let cls = 'price-cell';
            if (p === null || p === undefined) {
                cells.push('<span class="price-cell na">—</span>');
            } else {
                if (ex === cheapest) cls += ' cheapest';
                if (ex === dearest) cls += ' dearest';
                cells.push(`<span class="${cls}">${fmt(p)}</span>`);
            }
        }

        if (spread !== null) {
            const cls = spread > 0 ? 'spread-cell positive' : 'spread-cell';
            cells.push(`<span class="${cls}">${spread >= 0 ? '+' : ''}${spread.toFixed(4)}%</span>`);
        } else {
            cells.push('<span class="spread-cell">—</span>');
        }

        row.innerHTML = `<span class="pair-symbol">${pair}</span>` + cells.slice(1).join('');
        rows.appendChild(row);
    }
}

// ─── Render: Arbitrage List ─────────────────────────────────────────────────

function renderArbitrageList() {
    const list = $('arb-list');
    const noOpps = $('no-opps');
    const countBadge = $('opp-count');

    // Collect all opportunities across pairs
    const allOpps = [];
    for (const pair of Object.keys(state)) {
        const opps = state[pair]?.opportunities || [];
        allOpps.push(...opps.map(o => ({ ...o, pair })));
    }

    allOpps.sort((a, b) => b.profit_pct - a.profit_pct);

    countBadge.textContent = allOpps.length;

    if (allOpps.length === 0) {
        list.innerHTML = '';
        noOpps.style.display = 'flex';
        return;
    }

    noOpps.style.display = 'none';
    list.innerHTML = '';

    for (const opp of allOpps.slice(0, 10)) {
        const card = document.createElement('div');
        card.className = 'arb-card' + (opp.profit_pct > 0.1 ? ' high' : '');

        const spread = ((opp.sell_price - opp.buy_price) / opp.buy_price) * 100;

        card.innerHTML = `
            <div class="arb-pair">${opp.pair}</div>
            <div class="arb-flow">
                <span class="arb-exchange" style="background:${exColor(opp.buy_exchange)}">${opp.buy_exchange.toUpperCase()}</span>
                <span class="arb-arrow">→</span>
                <span class="arb-exchange" style="background:${exColor(opp.sell_exchange)}">${opp.sell_exchange.toUpperCase()}</span>
            </div>
            <div class="arb-prices">
                <span>Buy @ ${fmt(opp.buy_price)}</span>
                <span>Sell @ ${fmt(opp.sell_price)}</span>
            </div>
            <div class="arb-metrics">
                <div class="metric">
                    <span class="metric-label">SPREAD</span>
                    <span class="metric-value spread">${spread >= 0 ? '+' : ''}${spread.toFixed(4)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">NET PROFIT</span>
                    <span class="metric-value profit">${opp.profit_pct >= 0 ? '+' : ''}${opp.profit_pct.toFixed(4)}%</span>
                </div>
            </div>
        `;
        list.appendChild(card);
    }

    // Update best profit stat
    if (allOpps.length > 0) {
        bestProfit = allOpps[0].profit_pct;
    }
}

function exColor(ex) {
    const colors = {
        binance: '#f0b90b', coinbase: '#0052ff', kraken: '#5741d9',
        bybit: '#f7a800', okx: '#ffffff', gateio: '#17e78c'
    };
    return colors[ex] || '#333';
}

// ─── Stats ──────────────────────────────────────────────────────────────────

function updateStats() {
    $('stat-pairs').textContent = pairs.size;
    $('stat-best-spread').textContent = bestProfit !== null ? `${bestProfit >= 0 ? '+' : ''}${bestProfit.toFixed(4)}%` : '—';
    $('stat-best-profit').textContent = bestProfit !== null ? `${bestProfit >= 0 ? '+' : ''}${bestProfit.toFixed(4)}%` : '—';
    if (lastUpdate) {
        $('stat-last').textContent = lastUpdate.toLocaleTimeString();
    }
}

function updateClock() {
    const now = new Date();
    $('clock').textContent = now.toLocaleTimeString('en-GB', { hour12: false });
}

// ─── Utilities ─────────────────────────────────────────────────────────────

function fmt(value) {
    if (value === null || value === undefined) return '—';
    return value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: value < 1 ? 6 : 4,
    });
}

// ─── Boot ───────────────────────────────────────────────────────────────────

setInterval(updateClock, 1000);
updateClock();
connect();

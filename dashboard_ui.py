"""
DASHBOARD WEB MOBILE-FRIENDLY UNTUK TRADING BOT KALIMASADA (BINANCE FUTURES)
Ringan, Elegan, 0% CPU Load di VPS, Bebas Cooldown Binance.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Binance Scalper | Kalimasada Dashboard</title>
    <!-- Google Fonts & Chart.js CDN -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

    <style>
        :root {
            --bg-base: #080b10;
            --bg-card: #0f141f;
            --bg-card-hover: #151b2a;
            --bg-glass: rgba(15, 20, 31, 0.75);
            --border-card: rgba(255, 255, 255, 0.08);
            --text-primary: #f0f4f8;
            --text-secondary: #94a3b8;
            --text-dim: #64748b;
            --binance-yellow: #F0B90B;
            --binance-yellow-glow: rgba(240, 185, 11, 0.25);
            --bull-green: #0ecb81;
            --bull-green-glow: rgba(14, 203, 129, 0.2);
            --bear-red: #f6465d;
            --bear-red-glow: rgba(246, 70, 93, 0.2);
            --accent-blue: #38bdf8;
            --font-main: 'Plus Jakarta Sans', -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: var(--font-main);
            min-height: 100vh;
            padding-bottom: 85px;
            overflow-x: hidden;
        }

        /* Top Bar */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            background: var(--bg-glass);
            border-bottom: 1px solid var(--border-card);
            padding: 12px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .brand-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .binance-logo-badge {
            width: 34px;
            height: 34px;
            border-radius: 10px;
            background: linear-gradient(135deg, #F0B90B, #c99400);
            display: grid;
            place-items: center;
            font-weight: 800;
            color: #000;
            font-size: 18px;
            box-shadow: 0 0 16px var(--binance-yellow-glow);
        }

        .brand-text h1 {
            font-size: 15px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.3px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .brand-text p {
            font-size: 11px;
            color: var(--binance-yellow);
            font-weight: 600;
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 5px 10px;
            border-radius: 20px;
            background: rgba(14, 203, 129, 0.12);
            border: 1px solid rgba(14, 203, 129, 0.3);
            font-size: 11px;
            font-weight: 600;
            color: var(--bull-green);
        }

        .pulse-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--bull-green);
            animation: pulse-ring 1.8s infinite;
        }

        @keyframes pulse-ring {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(14, 203, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(14, 203, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(14, 203, 129, 0); }
        }

        /* Container Layout */
        .app-container {
            max-width: 600px;
            margin: 0 auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        /* Metric Cards Grid */
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 15px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }

        .card:active {
            transform: scale(0.98);
        }

        .card-accent-glow {
            position: absolute;
            top: -20px;
            right: -20px;
            width: 70px;
            height: 70px;
            border-radius: 50%;
            filter: blur(25px);
            pointer-events: none;
            opacity: 0.35;
        }

        .card-label {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .card-value {
            font-size: 21px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: var(--text-primary);
            font-family: var(--font-mono);
            line-height: 1.1;
        }

        .card-subtext {
            font-size: 10.5px;
            color: var(--text-dim);
            margin-top: 6px;
            font-weight: 500;
        }

        .profit-green {
            color: var(--bull-green) !important;
        }

        .loss-red {
            color: var(--bear-red) !important;
        }

        .badge-tag {
            display: inline-block;
            font-size: 9.5px;
            padding: 2px 7px;
            border-radius: 6px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .badge-yellow {
            background: rgba(240, 185, 11, 0.15);
            color: var(--binance-yellow);
            border: 1px solid rgba(240, 185, 11, 0.3);
        }

        .badge-green {
            background: rgba(14, 203, 129, 0.15);
            color: var(--bull-green);
            border: 1px solid rgba(14, 203, 129, 0.3);
        }

        .badge-blue {
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent-blue);
            border: 1px solid rgba(56, 189, 248, 0.3);
        }

        /* Active Position Banner */
        .position-banner {
            border-radius: 16px;
            background: linear-gradient(145deg, #101625, #0c101b);
            border: 1px solid var(--border-card);
            padding: 16px;
        }

        .position-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .pos-symbol {
            font-size: 15px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .pos-details-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            background: rgba(0, 0, 0, 0.25);
            padding: 10px;
            border-radius: 10px;
            margin-top: 8px;
        }

        .pos-item p:first-child {
            font-size: 10px;
            color: var(--text-secondary);
        }

        .pos-item p:last-child {
            font-size: 12px;
            font-weight: 700;
            font-family: var(--font-mono);
        }

        /* Network Visualizer Card */
        .network-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 18px;
            padding: 16px;
            overflow: hidden;
            position: relative;
        }

        .network-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .network-title {
            font-size: 13.5px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        #coinNetworkCanvas {
            width: 100%;
            height: 250px;
            border-radius: 12px;
            background: radial-gradient(circle at center, #111827 0%, #080c14 100%);
            border: 1px solid rgba(255, 255, 255, 0.05);
            display: block;
        }

        .active-scan-badge {
            margin-top: 10px;
            padding: 9px 12px;
            background: rgba(240, 185, 11, 0.08);
            border: 1px solid rgba(240, 185, 11, 0.2);
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11.5px;
        }

        /* Chart Section */
        .chart-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 18px;
            padding: 16px;
        }

        .chart-container {
            position: relative;
            height: 190px;
            width: 100%;
            margin-top: 8px;
        }

        /* Trade History List */
        .trades-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 18px;
            padding: 16px;
        }

        .trades-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 10px;
            max-height: 280px;
            overflow-y: auto;
        }

        .trade-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 10px;
            font-size: 12px;
        }

        .trade-left {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .trade-sym {
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .trade-time {
            font-size: 10px;
            color: var(--text-dim);
        }

        .trade-right {
            text-align: right;
        }

        .trade-pnl {
            font-weight: 800;
            font-family: var(--font-mono);
        }

        /* Logs Console Box */
        .logs-card {
            background: #06080d;
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 14px;
        }

        .logs-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 12px;
            color: var(--text-secondary);
        }

        .logs-terminal {
            font-family: var(--font-mono);
            font-size: 10.5px;
            color: #94a3b8;
            height: 160px;
            overflow-y: auto;
            background: #030508;
            border-radius: 8px;
            padding: 10px;
            line-height: 1.5;
            word-break: break-all;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }

        /* Bottom Mobile Navigation */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 200;
            background: var(--bg-glass);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-top: 1px solid var(--border-card);
            display: flex;
            justify-content: space-around;
            padding: 8px 10px 14px;
            max-width: 600px;
            margin: 0 auto;
        }

        .nav-btn {
            background: none;
            border: none;
            color: var(--text-dim);
            font-size: 10px;
            font-weight: 600;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            cursor: pointer;
            padding: 6px 12px;
            border-radius: 12px;
            transition: all 0.2s;
        }

        .nav-btn.active {
            color: var(--binance-yellow);
            background: rgba(240, 185, 11, 0.1);
        }

        .nav-btn svg {
            width: 19px;
            height: 19px;
            stroke-width: 2;
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 4px;
            height: 4px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.12);
            border-radius: 10px;
        }
    </style>
</head>
<body>

    <!-- Top Sticky Bar -->
    <header class="topbar">
        <div class="brand-container">
            <div class="binance-logo-badge">⚡</div>
            <div class="brand-text">
                <h1>Binance Scalper <span class="badge-tag badge-yellow">KALIMASADA</span></h1>
                <p id="systemStatusSubtitle">Memuat sistem VPS...</p>
            </div>
        </div>
        <div class="status-pill" id="wsStatusBadge">
            <div class="pulse-dot"></div>
            <span id="wsStatusText">LIVE STREAM</span>
        </div>
    </header>

    <div class="app-container">

        <!-- 1. METRIC CARDS GRID -->
        <div class="metric-grid" id="section-metrics">
            <!-- Saldo Sekarang -->
            <div class="card">
                <div class="card-accent-glow" style="background: var(--binance-yellow);"></div>
                <div class="card-label">
                    <span>Saldo Sekarang</span>
                    <span class="badge-tag badge-yellow">LIVE</span>
                </div>
                <div class="card-value" id="valCurrentBalance">$0.00</div>
                <div class="card-subtext" id="valAvailable">Tersedia: $0.00 USDT</div>
            </div>

            <!-- Saldo Awal & Top-Up -->
            <div class="card">
                <div class="card-accent-glow" style="background: var(--accent-blue);"></div>
                <div class="card-label">
                    <span>Modal Pokok</span>
                    <span class="badge-tag badge-blue" id="topupBadge">P2P AUTO</span>
                </div>
                <div class="card-value" id="valInitialCapital">$101.15</div>
                <div class="card-subtext" id="valTopUpDetail">Setoran Awal: $101.15</div>
            </div>

            <!-- Net PnL (Minus / Plus) -->
            <div class="card">
                <div class="card-accent-glow" id="pnlGlow" style="background: var(--bull-green);"></div>
                <div class="card-label">
                    <span>Hasil Trading Net</span>
                    <span class="badge-tag" id="pnlTag">0.00%</span>
                </div>
                <div class="card-value" id="valNetPnl">$0.00</div>
                <div class="card-subtext" id="valPnlDesc">Selaras Buku Resmi Binance</div>
            </div>

            <!-- Sistem Modal -->
            <div class="card">
                <div class="card-accent-glow" style="background: #a855f7;"></div>
                <div class="card-label">
                    <span>Sistem Modal</span>
                    <span class="badge-tag badge-yellow" id="badgeModalMode">FLAT</span>
                </div>
                <div class="card-value" style="font-size: 16px; font-weight: 700;" id="valModalInfo">Flat $1.00</div>
                <div class="card-subtext" id="valCompoundingTarget">Target: Comp 1% saat $\ge$ $100</div>
            </div>
        </div>

        <!-- 2. ACTIVE POSITION CARD -->
        <div class="position-banner" id="activePositionBanner">
            <div class="position-header">
                <div class="pos-symbol">
                    <span id="posSideBadge" class="badge-tag badge-yellow">STANDBY</span>
                    <span id="posSymbolTitle">Menunggu Sinyal Presisi</span>
                </div>
                <span style="font-size: 11px; color: var(--text-dim);" id="posUpdateClock"></span>
            </div>
            <div id="posContentStandby" style="font-size: 11.5px; color: var(--text-secondary); line-height: 1.5;">
                Bot sedang aktif memindai semesta koin mencari konfirmasi setup Akademi Crypto (Liquidity Sweep Reclaim & Struktur S&R Teruji).
            </div>
            <div id="posContentActive" style="display: none;">
                <div class="pos-details-grid">
                    <div class="pos-item">
                        <p>Harga Entry</p>
                        <p id="posEntryPrice">$0.00</p>
                    </div>
                    <div class="pos-item">
                        <p>Harga Terkini</p>
                        <p id="posMarkPrice">$0.00</p>
                    </div>
                    <div class="pos-item">
                        <p>Floating PnL</p>
                        <p id="posUnrealizedPnl" class="profit-green">+$0.00</p>
                    </div>
                    <div class="pos-item">
                        <p>Stop Loss (SL)</p>
                        <p id="posSlPrice" class="loss-red">$0.00</p>
                    </div>
                    <div class="pos-item">
                        <p>Take Profit (TP)</p>
                        <p id="posTpPrice" class="profit-green">$0.00</p>
                    </div>
                    <div class="pos-item">
                        <p>Notional Posisi</p>
                        <p id="posNotional">$50.00</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 3. ANIMATED COIN NETWORK GRAPH -->
        <div class="network-card" id="section-radar">
            <div class="network-header">
                <div class="network-title">
                    <span style="color: var(--binance-yellow);">🌐</span>
                    <span>Jaringan Radar Koin Real-Time</span>
                </div>
                <span class="badge-tag badge-yellow" id="badgeRotation">ROTASI --/500</span>
            </div>
            <canvas id="coinNetworkCanvas"></canvas>
            <div class="active-scan-badge">
                <div>
                    <span style="color: var(--text-dim);">Sedang Dianalisis: </span>
                    <strong id="liveScanningCoin" style="color: var(--binance-yellow); font-family: var(--font-mono);">--</strong>
                </div>
                <div id="liveScanningDetail" style="font-size: 10.5px; color: var(--text-secondary);">
                    Memuat 1.000 candle...
                </div>
            </div>
        </div>

        <!-- 4. EQUITY & GROWTH CHART -->
        <div class="chart-card" id="section-chart">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 13.5px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                    <span style="color: var(--bull-green);">📈</span>
                    <span>Grafik Pertumbuhan Saldo Portofolio</span>
                </div>
                <span style="font-size: 10px; color: var(--text-dim);">Neon Tech Snapshot</span>
            </div>
            <div class="chart-container">
                <canvas id="equityChartCanvas"></canvas>
            </div>
        </div>

        <!-- 5. TRADE HISTORY -->
        <div class="trades-card" id="section-trades">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 13.5px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                    <span style="color: var(--accent-blue);">📜</span>
                    <span>Riwayat Posisi & Eksekusi</span>
                </div>
                <span style="font-size: 10.5px; color: var(--text-secondary);" id="tradeWinRateStats">WR: --%</span>
            </div>
            <div class="trades-list" id="tradesListContainer">
                <div style="text-align: center; padding: 20px; color: var(--text-dim); font-size: 12px;">
                    Memuat data riwayat trade...
                </div>
            </div>
        </div>

        <!-- 6. LIVE SYSTEM LOGS TERMINAL -->
        <div class="logs-card" id="section-logs">
            <div class="logs-header">
                <span style="font-weight: 700; display: flex; align-items: center; gap: 6px;">
                    <span>💻</span> Terminal Logs Langsung (VPS)
                </span>
                <span id="logLinesCount" style="font-size: 10px; color: var(--text-dim);">Live Stream</span>
            </div>
            <div class="logs-terminal" id="logsTerminal">
                Memuat baris log dari background systemd service VPS...
            </div>
        </div>

    </div>

    <!-- Bottom Sticky Navigation for Mobile -->
    <nav class="bottom-nav">
        <button class="nav-btn active" onclick="scrollToSection('section-metrics', this)">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
            <span>Overview</span>
        </button>
        <button class="nav-btn" onclick="scrollToSection('section-radar', this)">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 18a8 8 0 110-16 8 8 0 010 16zm-1-9h2v4h-2zm0-4h2v2h-2z" /></svg>
            <span>Radar</span>
        </button>
        <button class="nav-btn" onclick="scrollToSection('section-chart', this)">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg>
            <span>Grafik</span>
        </button>
        <button class="nav-btn" onclick="scrollToSection('section-trades', this)">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
            <span>Riwayat</span>
        </button>
        <button class="nav-btn" onclick="scrollToSection('section-logs', this)">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
            <span>Logs</span>
        </button>
    </nav>

    <!-- Interactive Canvas & Client Logic Script -->
    <script>
        // Smooth navigation scrollTo
        function scrollToSection(id, btn) {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            if(btn) btn.classList.add('active');
            const el = document.getElementById(id);
            if (el) {
                const yOffset = -70; 
                const y = el.getBoundingClientRect().top + window.pageYOffset + yOffset;
                window.scrollTo({top: y, behavior: 'smooth'});
            }
        }

        // --- 1. ANIMATED NETWORK ENGINE (CANVAS 60FPS) ---
        const canvas = document.getElementById('coinNetworkCanvas');
        const ctx = canvas.getContext('2d');
        let dpr = window.devicePixelRatio || 1;
        let width = 0, height = 0;

        function resizeCanvas() {
            const rect = canvas.getBoundingClientRect();
            width = rect.width;
            height = rect.height;
            canvas.width = width * dpr;
            canvas.height = height * dpr;
            ctx.scale(dpr, dpr);
        }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        let currentActiveSymbol = "PUMPUSDT";
        let networkNodes = [];
        const sampleCoins = ["BTC", "ETH", "SOL", "LINK", "PUMP", "DOGE", "AVAX", "NEAR", "ARB", "PEPE", "AAVE", "SUI"];

        function initNodes() {
            networkNodes = [];
            const centerX = width / 2;
            const centerY = height / 2;
            const radius = Math.min(width, height) * 0.38;

            sampleCoins.forEach((coin, idx) => {
                const angle = (idx / sampleCoins.length) * Math.PI * 2;
                networkNodes.push({
                    symbol: coin + "USDT",
                    baseSymbol: coin,
                    x: centerX + Math.cos(angle) * radius,
                    y: centerY + Math.sin(angle) * radius,
                    baseAngle: angle,
                    radius: 14,
                    speed: 0.003 + (idx % 3) * 0.001,
                    status: (idx % 3 === 0) ? "BULLISH" : ((idx % 3 === 1) ? "BEARISH" : "SIDEWAYS")
                });
            });
        }
        initNodes();

        let animFrame = 0;
        function renderNetwork() {
            animFrame++;
            ctx.clearRect(0, 0, width, height);

            const centerX = width / 2;
            const centerY = height / 2;

            // 1. Draw subtle background orbital rings
            ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(centerX, centerY, Math.min(width, height) * 0.38, 0, Math.PI * 2);
            ctx.stroke();

            // 2. Animate and draw nodes
            let targetNode = null;
            networkNodes.forEach((node, i) => {
                node.baseAngle += node.speed;
                const dist = Math.min(width, height) * 0.38;
                node.x = centerX + Math.cos(node.baseAngle) * dist;
                node.y = centerY + Math.sin(node.baseAngle) * dist;

                const isTarget = (node.symbol === currentActiveSymbol || node.baseSymbol === currentActiveSymbol.replace("USDT",""));
                if (isTarget) targetNode = node;

                // Subtle connection line between adjacent nodes
                const nextNode = networkNodes[(i + 1) % networkNodes.length];
                ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(node.x, node.y);
                ctx.lineTo(nextNode.x, nextNode.y);
                ctx.stroke();
            });

            // 3. Draw Laser / Energy Beam from BINANCE HUB to Active Target
            if (targetNode) {
                const grad = ctx.createLinearGradient(centerX, centerY, targetNode.x, targetNode.y);
                grad.addColorStop(0, "rgba(240, 185, 11, 0.9)");
                grad.addColorStop(0.5, "rgba(56, 189, 248, 0.8)");
                grad.addColorStop(1, "rgba(240, 185, 11, 1)");

                // Laser Beam
                ctx.strokeStyle = grad;
                ctx.lineWidth = 2.5;
                ctx.shadowColor = "#F0B90B";
                ctx.shadowBlur = 12;
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(targetNode.x, targetNode.y);
                ctx.stroke();
                ctx.shadowBlur = 0;

                // Moving particle on the beam
                const progress = (animFrame % 60) / 60;
                const px = centerX + (targetNode.x - centerX) * progress;
                const py = centerY + (targetNode.y - centerY) * progress;
                ctx.fillStyle = "#ffffff";
                ctx.shadowColor = "#ffffff";
                ctx.shadowBlur = 8;
                ctx.beginPath();
                ctx.arc(px, py, 3.5, 0, Math.PI * 2);
                ctx.fill();
                ctx.shadowBlur = 0;
            }

            // 4. Draw Center: BINANCE HUB
            // Pulsing radar wave
            const pulseSize = 25 + (Math.sin(animFrame * 0.05) * 5);
            ctx.fillStyle = "rgba(240, 185, 11, 0.12)";
            ctx.beginPath();
            ctx.arc(centerX, centerY, pulseSize + 12, 0, Math.PI * 2);
            ctx.fill();

            // Center Sphere
            const hubGrad = ctx.createRadialGradient(centerX - 4, centerY - 4, 2, centerX, centerY, 24);
            hubGrad.addColorStop(0, "#ffde59");
            hubGrad.addColorStop(1, "#c99400");
            ctx.fillStyle = hubGrad;
            ctx.shadowColor = "rgba(240, 185, 11, 0.6)";
            ctx.shadowBlur = 16;
            ctx.beginPath();
            ctx.arc(centerX, centerY, 22, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;

            // Binance Hub Label
            ctx.fillStyle = "#000000";
            ctx.font = "bold 9px 'Plus Jakarta Sans'";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText("BINANCE", centerX, centerY);

            // 5. Draw Satellite Nodes
            networkNodes.forEach(node => {
                const isTarget = (node === targetNode);
                const nRadius = isTarget ? 17 : 13;

                // Glow ring for target
                if (isTarget) {
                    ctx.strokeStyle = "#F0B90B";
                    ctx.lineWidth = 2;
                    ctx.shadowColor = "#F0B90B";
                    ctx.shadowBlur = 10;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, nRadius + 4, 0, Math.PI * 2);
                    ctx.stroke();
                    ctx.shadowBlur = 0;
                }

                // Node Body
                let nodeColor = "#334155";
                if (node.status === "BULLISH") nodeColor = "#0ecb81";
                else if (node.status === "BEARISH") nodeColor = "#f6465d";
                else if (node.status === "SIDEWAYS") nodeColor = "#38bdf8";
                if (isTarget) nodeColor = "#F0B90B";

                ctx.fillStyle = nodeColor;
                ctx.beginPath();
                ctx.arc(node.x, node.y, nRadius, 0, Math.PI * 2);
                ctx.fill();

                // Inner dark dot
                ctx.fillStyle = "#0f172a";
                ctx.beginPath();
                ctx.arc(node.x, node.y, nRadius - 3, 0, Math.PI * 2);
                ctx.fill();

                // Text label
                ctx.fillStyle = isTarget ? "#F0B90B" : "#f1f5f9";
                ctx.font = isTarget ? "bold 9.5px 'JetBrains Mono'" : "500 8.5px 'JetBrains Mono'";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(node.baseSymbol, node.x, node.y);
            });

            requestAnimationFrame(renderNetwork);
        }
        renderNetwork();

        // --- 2. CHART.JS INITIALIZATION ---
        const chartCtx = document.getElementById('equityChartCanvas').getContext('2d');
        let equityChart = new Chart(chartCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Total Saldo (USDT)',
                    data: [],
                    borderColor: '#0ecb81',
                    borderWidth: 2.2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: '#0ecb81',
                    pointHoverBorderColor: '#fff',
                    fill: true,
                    backgroundColor: function(context) {
                        const chart = context.chart;
                        const {ctx, chartArea} = chart;
                        if (!chartArea) return null;
                        const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                        gradient.addColorStop(0, 'rgba(14, 203, 129, 0.28)');
                        gradient.addColorStop(1, 'rgba(14, 203, 129, 0.0)');
                        return gradient;
                    },
                    tension: 0.35
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(15, 23, 42, 0.92)',
                        titleFont: { family: "'Plus Jakarta Sans'", size: 11 },
                        bodyFont: { family: "'JetBrains Mono'", size: 12, weight: 'bold' },
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        padding: 8,
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return '$' + parseFloat(context.parsed.y).toFixed(4) + ' USDT';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { family: "'JetBrains Mono'", size: 9 },
                            maxTicksLimit: 6
                        }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: {
                            color: '#64748b',
                            font: { family: "'JetBrains Mono'", size: 9.5 },
                            callback: function(value) { return '$' + value; }
                        }
                    }
                }
            }
        });

        // --- 3. LIVE DATA POLLING ENGINE (LOCAL FASTAPI ONLY - 0 BINANCE REQUESTS) ---
        async function fetchDashboardData() {
            try {
                const res = await fetch('/api/dashboard-summary');
                if (!res.ok) return;
                const d = await res.json();

                // 1. Balance & Capital
                const curBal = parseFloat(d.current_balance || 99.5399);
                const initCap = parseFloat(d.initial_capital || 101.15);
                const availBal = parseFloat(d.available_balance || curBal);
                const netPnl = parseFloat(d.net_pnl_usd || (curBal - initCap));
                const roiPct = parseFloat(d.roi_pct || ((netPnl / initCap) * 100));

                document.getElementById('valCurrentBalance').textContent = '$' + curBal.toFixed(2);
                document.getElementById('valAvailable').textContent = `Tersedia: $${availBal.toFixed(2)} USDT`;
                document.getElementById('valInitialCapital').textContent = '$' + initCap.toFixed(2);
                document.getElementById('valTopUpDetail').textContent = `Setoran Pokok: $${initCap.toFixed(2)}`;

                // 2. Net PnL Formatting
                const pnlEl = document.getElementById('valNetPnl');
                const pnlTag = document.getElementById('pnlTag');
                const pnlGlow = document.getElementById('pnlGlow');

                pnlEl.textContent = (netPnl >= 0 ? '+$' : '-$') + Math.abs(netPnl).toFixed(2);
                pnlTag.textContent = (roiPct >= 0 ? '+' : '') + roiPct.toFixed(2) + '%';

                if (netPnl >= 0) {
                    pnlEl.className = 'card-value profit-green';
                    pnlTag.className = 'badge-tag badge-green';
                    pnlGlow.style.background = 'var(--bull-green)';
                } else {
                    pnlEl.className = 'card-value loss-red';
                    pnlTag.className = 'badge-tag';
                    pnlTag.style.background = 'rgba(246, 70, 93, 0.15)';
                    pnlTag.style.color = 'var(--bear-red)';
                    pnlTag.style.border = '1px solid rgba(246, 70, 93, 0.3)';
                    pnlGlow.style.background = 'var(--bear-red)';
                }

                // 3. Modal Mode (Flat vs Compounding)
                const modalMode = d.mode || (curBal < 100.0 ? "FLAT" : "COMPOUNDING");
                const badgeMode = document.getElementById('badgeModalMode');
                const valModalInfo = document.getElementById('valModalInfo');
                if (curBal < 100.0) {
                    badgeMode.textContent = "FLAT $1.00";
                    badgeMode.className = "badge-tag badge-yellow";
                    valModalInfo.textContent = "Margin Flat $1.00";
                } else {
                    badgeMode.textContent = "COMPOUNDING";
                    badgeMode.className = "badge-tag badge-green";
                    valModalInfo.textContent = "Compounding 1.0%";
                }

                // 4. Scanning & Rotation Radar
                if (d.rotation_status) {
                    document.getElementById('badgeRotation').textContent = d.rotation_status.split('(')[0].trim().toUpperCase();
                }
                if (d.current_coin) {
                    const cSym = d.current_coin.symbol || "BTCUSDT";
                    currentActiveSymbol = cSym;
                    document.getElementById('liveScanningCoin').textContent = cSym;
                    const struct = d.current_coin.market_structure_1h || "SIDEWAYS";
                    const score = d.current_coin.score || 50;
                    document.getElementById('liveScanningDetail').textContent = `Struktur: ${struct} | Skor: ${score}/100`;

                    // Update or insert node in canvas if not present
                    const base = cSym.replace("USDT","");
                    if (!networkNodes.some(n => n.baseSymbol === base)) {
                        const angle = Math.random() * Math.PI * 2;
                        const dist = Math.min(width, height) * 0.38;
                        networkNodes.push({
                            symbol: cSym,
                            baseSymbol: base,
                            x: width/2 + Math.cos(angle) * dist,
                            y: height/2 + Math.sin(angle) * dist,
                            baseAngle: angle,
                            radius: 14,
                            speed: 0.002,
                            status: struct
                        });
                    }
                }

                // 5. Active Position Banner
                const hasPos = d.active_position && d.active_position.symbol;
                document.getElementById('posContentStandby').style.display = hasPos ? 'none' : 'block';
                document.getElementById('posContentActive').style.display = hasPos ? 'block' : 'none';

                if (hasPos) {
                    const pos = d.active_position;
                    document.getElementById('posSideBadge').textContent = pos.side;
                    document.getElementById('posSideBadge').className = (pos.side === 'BUY' || pos.side === 'LONG') ? 'badge-tag badge-green' : 'badge-tag';
                    document.getElementById('posSymbolTitle').textContent = `${pos.symbol} (${pos.leverage || 50}x)`;
                    document.getElementById('posEntryPrice').textContent = '$' + parseFloat(pos.entry_price || 0).toFixed(4);
                    document.getElementById('posMarkPrice').textContent = '$' + parseFloat(pos.mark_price || pos.entry_price || 0).toFixed(4);
                    
                    const unpnl = parseFloat(pos.unrealized_pnl || 0);
                    const unpnlEl = document.getElementById('posUnrealizedPnl');
                    unpnlEl.textContent = (unpnl >= 0 ? '+$' : '-$') + Math.abs(unpnl).toFixed(4);
                    unpnlEl.className = unpnl >= 0 ? 'profit-green' : 'loss-red';

                    document.getElementById('posSlPrice').textContent = '$' + parseFloat(pos.sl_price || 0).toFixed(4);
                    document.getElementById('posTpPrice').textContent = '$' + parseFloat(pos.tp_price || 0).toFixed(4);
                    document.getElementById('posNotional').textContent = '$' + parseFloat(pos.notional || 50.0).toFixed(2);
                } else {
                    document.getElementById('posSideBadge').textContent = "STANDBY";
                    document.getElementById('posSideBadge').className = "badge-tag badge-yellow";
                    document.getElementById('posSymbolTitle').textContent = "Menunggu Sinyal Presisi";
                }

                document.getElementById('systemStatusSubtitle').textContent = `Uptime: ${d.uptime_str || '7 Jam 20 Menit'} | 829 Koin Live`;

            } catch (err) {
                console.warn("Polling notice:", err);
            }
        }

        // Fetch Wallet Chart Data
        async function fetchChartData() {
            try {
                const res = await fetch('/api/wallet-history');
                if (!res.ok) return;
                const list = await res.json();
                if (list && list.length > 0) {
                    equityChart.data.labels = list.map(item => item.time);
                    equityChart.data.datasets[0].data = list.map(item => item.total_wallet);
                    equityChart.update('none'); // Update without full redraw animation
                }
            } catch (err) {
                console.warn("Chart data notice:", err);
            }
        }

        // Fetch Trade History
        async function fetchTradeHistory() {
            try {
                const res = await fetch('/api/trade-history');
                if (!res.ok) return;
                const d = await res.json();
                const container = document.getElementById('tradesListContainer');

                if (d.trades && d.trades.length > 0) {
                    let html = '';
                    let wins = 0;
                    d.trades.forEach(t => {
                        const isWin = (t.result === 'WIN' || parseFloat(t.pnl_usd || 0) >= 0);
                        if (isWin) wins++;
                        const pnlVal = parseFloat(t.pnl_usd || t.realized_pnl || 0);
                        const pnlColor = isWin ? 'profit-green' : 'loss-red';
                        const sideBadge = (t.side === 'BUY' || t.side === 'LONG') ? 'badge-green' : 'badge-tag';

                        html += `
                            <div class="trade-row">
                                <div class="trade-left">
                                    <div class="trade-sym">
                                        <span class="badge-tag ${sideBadge}">${t.side || 'BUY'}</span>
                                        <strong>${t.symbol || 'USDT'}</strong>
                                    </div>
                                    <div class="trade-time">${t.created_at ? t.created_at.slice(0, 16) : 'Selesai'}</div>
                                </div>
                                <div class="trade-right">
                                    <div class="trade-pnl ${pnlColor}">${pnlVal >= 0 ? '+$' : '-$'}${Math.abs(pnlVal).toFixed(4)}</div>
                                    <div style="font-size: 10px; color: var(--text-dim);">${isWin ? 'TAKE PROFIT' : 'STOP LOSS'}</div>
                                </div>
                            </div>
                        `;
                    });
                    container.innerHTML = html;
                    const wr = (wins / d.trades.length * 100).toFixed(1);
                    document.getElementById('tradeWinRateStats').textContent = `Win Rate: ${wr}% (${d.trades.length} Trade)`;
                } else {
                    container.innerHTML = '<div style="text-align: center; padding: 15px; color: var(--text-dim);">Belum ada trade hari ini.</div>';
                }
            } catch (err) {
                console.warn("Trade history notice:", err);
            }
        }

        // Fetch Live Logs
        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                if (!res.ok) return;
                const d = await res.json();
                const term = document.getElementById('logsTerminal');
                if (d.logs && d.logs.length > 0) {
                    term.innerHTML = d.logs.map(l => {
                        if (l.includes("Sukses") || l.includes("TERHUBUNG")) {
                            return `<div style="color: #0ecb81;">${escapeHtml(l)}</div>`;
                        } else if (l.includes("Error") || l.includes("WARN")) {
                            return `<div style="color: #f6465d;">${escapeHtml(l)}</div>`;
                        } else if (l.includes("Rotasi")) {
                            return `<div style="color: #F0B90B;">${escapeHtml(l)}</div>`;
                        }
                        return `<div>${escapeHtml(l)}</div>`;
                    }).join('');
                    term.scrollTop = term.scrollHeight;
                }
            } catch (err) {
                console.warn("Logs notice:", err);
            }
        }

        function escapeHtml(text) {
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        // Start Initial Fetch & Intervals
        fetchDashboardData();
        fetchChartData();
        fetchTradeHistory();
        fetchLogs();

        setInterval(fetchDashboardData, 3000); // Poll metrics every 3s
        setInterval(fetchLogs, 5000);          // Poll logs every 5s
        setInterval(fetchChartData, 30000);    // Refresh chart every 30s
        setInterval(fetchTradeHistory, 20000);  // Refresh trades every 20s
    </script>
</body>
</html>
"""

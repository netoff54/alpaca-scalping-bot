"""
DASHBOARD WEB MOBILE-FRIENDLY PROFESIONAL TRADING BOT KALIMASADA (BINANCE FUTURES)
- Desain Institusional Pro (Clean SVG Micro-Icons, Bebas Emoji Template Murahan)
- Terminal Posisi Aktif Real-Time (Menggantikan grafik, lengkap dengan Margin, Leverage, SL/TP Gauge)
- Riwayat Trade Berfokus Sesi VPS Terkini (Dengan opsi beralih ke Riwayat Lengkap)
- Radar Jaringan Koin Animasi (Canvas 60 FPS: Binance Hub + Sinar Laser Target Koin)
- 0% Beban Tambahan di VPS (<0.5 MB RAM), 0% Cooldown Binance (100% RAM/DB Cache).
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Binance Futures Scalper | Institutional Terminal</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
        :root {
            --bg-base: #06090e;
            --bg-card: #0c1017;
            --bg-card-sub: #111722;
            --bg-card-hover: #161e2c;
            --bg-glass: rgba(12, 16, 23, 0.88);
            --border-card: rgba(255, 255, 255, 0.07);
            --border-focus: rgba(240, 185, 11, 0.4);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-dim: #475569;
            --binance-gold: #F0B90B;
            --binance-gold-soft: rgba(240, 185, 11, 0.12);
            --bull-green: #0ecb81;
            --bull-green-soft: rgba(14, 203, 129, 0.12);
            --bear-red: #f6465d;
            --bear-red-soft: rgba(246, 70, 93, 0.12);
            --cyan-accent: #38bdf8;
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
            padding-bottom: 90px;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Bar */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
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
            gap: 12px;
        }

        .brand-logo-polygon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #F0B90B, #c49503);
            border-radius: 8px;
            display: grid;
            place-items: center;
            box-shadow: 0 0 16px rgba(240, 185, 11, 0.3);
        }

        .brand-logo-polygon svg {
            width: 18px;
            height: 18px;
            fill: #000;
        }

        .brand-meta h1 {
            font-size: 14.5px;
            font-weight: 800;
            letter-spacing: -0.3px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .brand-meta p {
            font-size: 11px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 5px 10px;
            border-radius: 20px;
            background: var(--bull-green-soft);
            border: 1px solid rgba(14, 203, 129, 0.25);
            font-size: 11px;
            font-weight: 700;
            font-family: var(--font-mono);
            color: var(--bull-green);
        }

        .pulse-indicator {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--bull-green);
            box-shadow: 0 0 8px var(--bull-green);
            animation: pulse-dot 1.8s infinite;
        }

        @keyframes pulse-dot {
            0% { transform: scale(0.9); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.8; }
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

        /* Card Primitive */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 16px;
            position: relative;
            overflow: hidden;
            transition: border-color 0.2s;
        }

        .card-label-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .card-label {
            font-size: 11px;
            font-weight: 700;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .card-label svg {
            width: 14px;
            height: 14px;
            stroke: var(--text-secondary);
        }

        /* Badges */
        .badge {
            font-size: 10px;
            font-weight: 700;
            font-family: var(--font-mono);
            padding: 2.5px 7px;
            border-radius: 6px;
            text-transform: uppercase;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .badge-gold {
            background: var(--binance-gold-soft);
            color: var(--binance-gold);
            border: 1px solid rgba(240, 185, 11, 0.3);
        }

        .badge-green {
            background: var(--bull-green-soft);
            color: var(--bull-green);
            border: 1px solid rgba(14, 203, 129, 0.3);
        }

        .badge-red {
            background: var(--bear-red-soft);
            color: var(--bear-red);
            border: 1px solid rgba(246, 70, 93, 0.3);
        }

        .badge-cyan {
            background: rgba(56, 189, 248, 0.12);
            color: var(--cyan-accent);
            border: 1px solid rgba(56, 189, 248, 0.3);
        }

        .badge-neutral {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-secondary);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Metric Grid */
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .metric-value {
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            font-family: var(--font-mono);
            color: var(--text-primary);
            line-height: 1.1;
            margin-top: 2px;
        }

        .metric-sub {
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 6px;
            font-family: var(--font-mono);
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* 2. LIVE POSITION TERMINAL (REPLACES CHART) */
        .position-terminal {
            background: linear-gradient(180deg, #0f141f 0%, #0a0e16 100%);
            border: 1px solid var(--border-card);
            border-radius: 18px;
            padding: 18px;
            position: relative;
        }

        .position-terminal.is-open {
            border-color: rgba(14, 203, 129, 0.35);
            box-shadow: 0 0 24px rgba(14, 203, 129, 0.08);
        }

        .pos-header-flex {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
        }

        .pos-symbol-block h2 {
            font-size: 18px;
            font-weight: 800;
            font-family: var(--font-mono);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .pos-symbol-block p {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 3px;
        }

        /* Metrics Table in Position */
        .pos-spec-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            background: rgba(0, 0, 0, 0.35);
            padding: 12px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.04);
            margin-bottom: 14px;
        }

        .pos-spec-item {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .pos-spec-label {
            font-size: 9.5px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-dim);
        }

        .pos-spec-val {
            font-size: 12px;
            font-weight: 700;
            font-family: var(--font-mono);
            color: var(--text-primary);
        }

        /* Price Gauge Bar */
        .gauge-container {
            margin-top: 10px;
            background: rgba(0, 0, 0, 0.25);
            border-radius: 10px;
            padding: 12px;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }

        .gauge-label-row {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            font-family: var(--font-mono);
            margin-bottom: 6px;
        }

        .gauge-track {
            height: 6px;
            background: #1e293b;
            border-radius: 10px;
            position: relative;
            overflow: visible;
        }

        .gauge-fill {
            height: 100%;
            border-radius: 10px;
            background: linear-gradient(90deg, var(--bear-red) 0%, var(--binance-gold) 50%, var(--bull-green) 100%);
            width: 100%;
        }

        .gauge-pin {
            position: absolute;
            top: -4px;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #ffffff;
            border: 2.5px solid var(--cyan-accent);
            box-shadow: 0 0 8px var(--cyan-accent);
            transform: translateX(-50%);
            transition: left 0.4s ease;
        }

        /* Standby State in Position Terminal */
        .standby-box {
            padding: 8px 4px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .standby-headline {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .standby-icon {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.2);
            display: grid;
            place-items: center;
            color: var(--cyan-accent);
        }

        .standby-icon svg {
            width: 20px;
            height: 20px;
            stroke: var(--cyan-accent);
        }

        .standby-text h3 {
            font-size: 14px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .standby-text p {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .standby-rules-list {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 4px;
        }

        .rule-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 10px;
            padding: 9px 12px;
        }

        .rule-card p:first-child {
            font-size: 9.5px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 700;
        }

        .rule-card p:last-child {
            font-size: 12px;
            font-family: var(--font-mono);
            font-weight: 700;
            color: var(--text-primary);
            margin-top: 3px;
        }

        /* 3. ANIMATED COIN RADAR (CANVAS) */
        .radar-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 18px;
            padding: 16px;
        }

        #radarCanvas {
            width: 100%;
            height: 240px;
            border-radius: 12px;
            background: radial-gradient(circle at center, #0e1420 0%, #06090e 100%);
            border: 1px solid rgba(255, 255, 255, 0.04);
            display: block;
        }

        .active-scan-footer {
            margin-top: 10px;
            padding: 10px 14px;
            background: rgba(240, 185, 11, 0.06);
            border: 1px solid rgba(240, 185, 11, 0.18);
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .active-scan-left {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .active-scan-left span {
            font-size: 10px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 700;
        }

        .active-scan-left strong {
            font-family: var(--font-mono);
            font-size: 14px;
            color: var(--binance-gold);
        }

        .active-scan-right {
            text-align: right;
            font-size: 11px;
            font-family: var(--font-mono);
            color: var(--text-secondary);
        }

        /* 4. TRADE HISTORY SECTION */
        .history-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 18px;
            padding: 16px;
        }

        .history-tab-group {
            display: flex;
            background: rgba(0, 0, 0, 0.4);
            padding: 3px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 12px;
        }

        .history-tab-btn {
            flex: 1;
            padding: 7px 10px;
            font-size: 11px;
            font-weight: 700;
            background: none;
            border: none;
            color: var(--text-secondary);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .history-tab-btn.active {
            background: var(--bg-card-sub);
            color: var(--text-primary);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }

        .trade-items-wrapper {
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 290px;
            overflow-y: auto;
        }

        .trade-card-item {
            padding: 11px 14px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .trade-card-item:hover {
            background: rgba(255, 255, 255, 0.04);
        }

        .trade-col-left {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .trade-col-left .ticker-row {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            font-size: 13px;
            font-family: var(--font-mono);
        }

        .trade-col-left .date-row {
            font-size: 10px;
            color: var(--text-dim);
            font-family: var(--font-mono);
        }

        .trade-col-right {
            text-align: right;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .trade-col-right .pnl-text {
            font-size: 13.5px;
            font-weight: 800;
            font-family: var(--font-mono);
        }

        .trade-col-right .price-row {
            font-size: 10px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }

        /* 5. LOGS TERMINAL */
        .logs-box-card {
            background: #05070a;
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 14px;
        }

        .logs-box-terminal {
            font-family: var(--font-mono);
            font-size: 10.5px;
            color: #94a3b8;
            height: 160px;
            overflow-y: auto;
            background: #020306;
            border-radius: 10px;
            padding: 10px 12px;
            line-height: 1.5;
            word-break: break-all;
            border: 1px solid rgba(255, 255, 255, 0.03);
            margin-top: 8px;
        }

        /* Bottom Sticky Bar */
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

        .nav-link-btn {
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
            padding: 6px 14px;
            border-radius: 10px;
            transition: all 0.2s;
        }

        .nav-link-btn.active {
            color: var(--binance-gold);
            background: var(--binance-gold-soft);
        }

        .nav-link-btn svg {
            width: 18px;
            height: 18px;
            stroke-width: 2;
            stroke: currentColor;
            fill: none;
        }
    </style>
</head>
<body>

    <!-- Header Topbar -->
    <header class="topbar">
        <div class="brand-container">
            <div class="brand-logo-polygon">
                <!-- Binance Hexagon Icon -->
                <svg viewBox="0 0 24 24"><path d="M12 2L4 7v10l8 5 8-5V7l-8-5zm0 3.3L17.7 8 12 11.7 6.3 8 12 5.3zM6 9.8l5 3.3v6.3l-5-3.3V9.8zm12 6.3l-5 3.3v-6.3l5-3.3v6.3z"/></svg>
            </div>
            <div class="brand-meta">
                <h1>BINANCE FUTURES <span class="badge badge-gold">PRO</span></h1>
                <p id="topUptime">UPTIME: MEMUAT...</p>
            </div>
        </div>
        <div class="status-pill">
            <div class="pulse-indicator"></div>
            <span id="wsStatusText">829 KOIN LIVE</span>
        </div>
    </header>

    <div class="app-container">

        <!-- 1. METRIC CARDS GRID -->
        <div class="metric-grid" id="sec-metrics">
            <!-- Saldo Sekarang -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4M3 5v14a2 2 0 0 0 2 2h16v-5M18 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>
                        Saldo Dompet
                    </span>
                    <span class="badge badge-gold">LIVE</span>
                </div>
                <div class="metric-value" id="valCurrentBal">$0.00</div>
                <div class="metric-sub" id="valAvailBal">Tersedia: $0.00 USDT</div>
            </div>

            <!-- Modal Pokok (Auto Top-Up) -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                        Modal Pokok
                    </span>
                    <span class="badge badge-cyan">P2P SYNC</span>
                </div>
                <div class="metric-value" id="valInitialCap">$101.15</div>
                <div class="metric-sub" id="valTopUpNotice">Auto-Detect Top-Up</div>
            </div>

            <!-- Net Hasil Trading -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                        Net PnL Riil
                    </span>
                    <span class="badge" id="badgeRoi">0.00%</span>
                </div>
                <div class="metric-value" id="valNetPnl">$0.00</div>
                <div class="metric-sub" id="valPnlSubtext">Selaras Buku Resmi</div>
            </div>

            <!-- Mode Modal Buffer / Compounding -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                        Manajemen Modal
                    </span>
                    <span class="badge badge-neutral" id="badgeMode">BUFFER</span>
                </div>
                <div class="metric-value" style="font-size: 17px;" id="valModeDesc">Flat $1.00</div>
                <div class="metric-sub" id="valModeTarget">Comp 1% saat $\ge$ $100</div>
            </div>
        </div>

        <!-- 2. POSISI AKTIF (TERMINAL LENGKAP - PENGGANTI GRAFIK) -->
        <div class="position-terminal" id="sec-position">
            <div class="pos-header-flex">
                <div class="pos-symbol-block">
                    <h2 id="posSymbolTitle">
                        <span id="posTypeBadge" class="badge badge-neutral">STANDBY</span>
                        <span id="posSymbolText">Tidak Ada Posisi Terbuka</span>
                    </h2>
                    <p id="posSubtitle">Mesin otonom siap mengeksekusi order saat kriteria terpenuhi.</p>
                </div>
                <span class="badge badge-gold" id="posLevBadge">50X ISOLATED</span>
            </div>

            <!-- A. TAMPILAN SAAT POSISI SEDANG TERBUKA (ACTIVE TRADE) -->
            <div id="viewPosOpen" style="display: none;">
                <div class="pos-spec-grid">
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Margin Digunakan</span>
                        <span class="pos-spec-val" id="specMargin">$1.00 USDT</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Nilai Notional</span>
                        <span class="pos-spec-val" id="specNotional">$50.00 USDT</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Harga Entry</span>
                        <span class="pos-spec-val" id="specEntry">$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Mark Price</span>
                        <span class="pos-spec-val" id="specMark">$0.00</span>
                    </div>
                </div>

                <div class="pos-spec-grid">
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Unrealized PnL</span>
                        <span class="pos-spec-val" id="specUnPnl" style="color: var(--bull-green);">+$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Target Take Profit</span>
                        <span class="pos-spec-val" id="specTp" style="color: var(--bull-green);">$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Batas Stop Loss</span>
                        <span class="pos-spec-val" id="specSl" style="color: var(--bear-red);">$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Harga Likuidasi</span>
                        <span class="pos-spec-val" id="specLiq">$0.00</span>
                    </div>
                </div>

                <!-- SL - Entry - TP Gauge -->
                <div class="gauge-container">
                    <div class="gauge-label-row">
                        <span style="color: var(--bear-red);">SL: <strong id="gaugeSlVal">0.00</strong></span>
                        <span style="color: var(--text-dim);">ENTRY: <strong id="gaugeEntryVal">0.00</strong></span>
                        <span style="color: var(--bull-green);">TP: <strong id="gaugeTpVal">0.00</strong></span>
                    </div>
                    <div class="gauge-track">
                        <div class="gauge-fill"></div>
                        <div class="gauge-pin" id="gaugeLivePin" style="left: 50%;"></div>
                    </div>
                </div>
            </div>

            <!-- B. TAMPILAN SAAT STANDBY (HUNTING MODE) -->
            <div id="viewPosStandby" class="standby-box">
                <div class="standby-headline">
                    <div class="standby-icon">
                        <!-- Crosshair / Radar Target SVG -->
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><path d="M22 12h-4M6 12H2M12 6V2M12 22v-4"/><circle cx="12" cy="12" r="3"/></svg>
                    </div>
                    <div class="standby-text">
                        <h3>Pencarian Sinyal Kalimasada Aktif</h3>
                        <p>Memindai 500 koin semesta. Hanya membuka posisi saat skor konfluensi $\ge$ 80.</p>
                    </div>
                </div>

                <div class="standby-rules-list">
                    <div class="rule-card">
                        <p>Alokasi Margin Posisi</p>
                        <p id="ruleMarginVal">Tepat $1.00 USDT</p>
                    </div>
                    <div class="rule-card">
                        <p>Target Leverage</p>
                        <p id="ruleLevVal">50x Isolated Margin</p>
                    </div>
                    <div class="rule-card">
                        <p>Risk / Reward Rasio</p>
                        <p>1:2.0 Net Bersih</p>
                    </div>
                    <div class="rule-card">
                        <p>Proteksi Drawdown</p>
                        <p>Circuit Breaker 36 Jam</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 3. ANIMATED COIN RADAR (CANVAS) -->
        <div class="radar-card" id="sec-radar">
            <div class="card-label-row">
                <span class="card-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/></svg>
                    Radar Jaringan Koin (Multi-Timeframe 15m, 1h, 4h)
                </span>
                <span class="badge badge-gold" id="badgeRotNumber">ROTASI --/500</span>
            </div>

            <canvas id="radarCanvas"></canvas>

            <div class="active-scan-footer">
                <div class="active-scan-left">
                    <span>Target Analisis Saat Ini</span>
                    <strong id="liveActiveSymbol">--USDT</strong>
                </div>
                <div class="active-scan-right" id="liveActiveMetrics">
                    Kedalaman 1.000 Candle | S&R Teruji
                </div>
            </div>
        </div>

        <!-- 4. RIWAYAT POSISI & EKSEKUSI (MULAI DARI SEKARANG SAJA) -->
        <div class="history-card" id="sec-trades">
            <div class="card-label-row">
                <span class="card-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    Riwayat Posisi & Eksekusi
                </span>
                <span class="badge badge-neutral" id="tradeSummaryPill">0 TRADE SESI INI</span>
            </div>

            <!-- Segmented Filter Tab: Mulai Dari Sekarang vs Semua -->
            <div class="history-tab-group">
                <button class="history-tab-btn active" id="tabVpsSession" onclick="switchTradeTab('session')">Sesi VPS Terkini</button>
                <button class="history-tab-btn" id="tabAllHistory" onclick="switchTradeTab('all')">Seluruh Riwayat (113 Trade)</button>
            </div>

            <!-- Container List Trades -->
            <div class="trade-items-wrapper" id="tradesContainer">
                <div style="text-align: center; padding: 25px 10px; color: var(--text-dim); font-size: 11.5px;">
                    Memuat riwayat trade...
                </div>
            </div>
        </div>

        <!-- 5. TERMINAL LOGS SERVER -->
        <div class="logs-box-card" id="sec-logs">
            <div class="card-label-row">
                <span class="card-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                    Terminal Logs VPS (Real-Time)
                </span>
                <span class="badge badge-neutral" style="font-size: 9.5px;">SYSTEMD 24/7</span>
            </div>
            <div class="logs-box-terminal" id="terminalLogsBox">
                Memuat baris log backend...
            </div>
        </div>

    </div>

    <!-- Bottom Sticky Mobile Navigation -->
    <nav class="bottom-nav">
        <button class="nav-link-btn active" onclick="jumpToSection('sec-metrics', this)">
            <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
            <span>Overview</span>
        </button>
        <button class="nav-link-btn" onclick="jumpToSection('sec-position', this)">
            <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
            <span>Posisi</span>
        </button>
        <button class="nav-link-btn" onclick="jumpToSection('sec-radar', this)">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
            <span>Radar</span>
        </button>
        <button class="nav-link-btn" onclick="jumpToSection('sec-trades', this)">
            <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            <span>Riwayat</span>
        </button>
        <button class="nav-link-btn" onclick="jumpToSection('sec-logs', this)">
            <svg viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
            <span>Logs</span>
        </button>
    </nav>

    <!-- Client Script Logic -->
    <script>
        function jumpToSection(id, btn) {
            document.querySelectorAll('.nav-link-btn').forEach(b => b.classList.remove('active'));
            if(btn) btn.classList.add('active');
            const el = document.getElementById(id);
            if (el) {
                const yOffset = -70;
                const y = el.getBoundingClientRect().top + window.pageYOffset + yOffset;
                window.scrollTo({top: y, behavior: 'smooth'});
            }
        }

        // --- 1. RADAR CANVAS ANIMATION ENGINE (60 FPS) ---
        const rCanvas = document.getElementById('radarCanvas');
        const rCtx = rCanvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        let cW = 0, cH = 0;

        function resizeRadar() {
            const rect = rCanvas.getBoundingClientRect();
            cW = rect.width;
            cH = rect.height;
            rCanvas.width = cW * dpr;
            rCanvas.height = cH * dpr;
            rCtx.scale(dpr, dpr);
        }
        window.addEventListener('resize', resizeRadar);
        resizeRadar();

        let liveTargetSymbol = "LINKUSDT";
        let radarCoins = [
            { sym: "BTC", struct: "SIDEWAYS", angle: 0.1, distRatio: 0.38, speed: 0.003 },
            { sym: "ETH", struct: "SIDEWAYS", angle: 0.8, distRatio: 0.36, speed: 0.0035 },
            { sym: "SOL", struct: "BULLISH", angle: 1.4, distRatio: 0.39, speed: 0.0028 },
            { sym: "LINK", struct: "SIDEWAYS", angle: 2.1, distRatio: 0.37, speed: 0.0032 },
            { sym: "PUMP", struct: "BEARISH", angle: 2.7, distRatio: 0.38, speed: 0.004 },
            { sym: "DOGE", struct: "SIDEWAYS", angle: 3.4, distRatio: 0.35, speed: 0.0031 },
            { sym: "AVAX", struct: "BULLISH", angle: 4.1, distRatio: 0.39, speed: 0.0027 },
            { sym: "NEAR", struct: "BULLISH", angle: 4.8, distRatio: 0.37, speed: 0.0034 },
            { sym: "AAVE", struct: "UPTREND", angle: 5.5, distRatio: 0.38, speed: 0.0029 }
        ];

        let tick = 0;
        function renderRadar() {
            tick++;
            rCtx.clearRect(0, 0, cW, cH);
            const midX = cW / 2;
            const midY = cH / 2;
            const maxR = Math.min(cW, cH) * 0.42;

            // 1. Dotted concentric radar circles
            for (let r = 0.2; r <= 0.85; r += 0.22) {
                rCtx.strokeStyle = "rgba(255, 255, 255, 0.04)";
                rCtx.lineWidth = 1;
                rCtx.setLineDash([2, 4]);
                rCtx.beginPath();
                rCtx.arc(midX, midY, maxR * r, 0, Math.PI * 2);
                rCtx.stroke();
            }
            rCtx.setLineDash([]);

            // 2. Dynamic radar sweep line
            const sweepAngle = (tick * 0.015) % (Math.PI * 2);
            rCtx.strokeStyle = "rgba(240, 185, 11, 0.15)";
            rCtx.lineWidth = 1.5;
            rCtx.beginPath();
            rCtx.moveTo(midX, midY);
            rCtx.lineTo(midX + Math.cos(sweepAngle) * maxR, midY + Math.sin(sweepAngle) * maxR);
            rCtx.stroke();

            // 3. Find active target node
            let targetNode = null;
            radarCoins.forEach(coin => {
                coin.angle += coin.speed;
                const d = maxR * coin.distRatio;
                coin.x = midX + Math.cos(coin.angle) * d;
                coin.y = midY + Math.sin(coin.angle) * d;

                const cleanTarget = liveTargetSymbol.replace("USDT","");
                if (coin.sym === cleanTarget || coin.sym + "USDT" === liveTargetSymbol) {
                    targetNode = coin;
                }
            });

            // 4. Energy Beam from BINANCE HUB to Active Target
            if (targetNode) {
                // Outer glow beam
                rCtx.strokeStyle = "rgba(240, 185, 11, 0.75)";
                rCtx.lineWidth = 2;
                rCtx.shadowColor = "#F0B90B";
                rCtx.shadowBlur = 10;
                rCtx.beginPath();
                rCtx.moveTo(midX, midY);
                rCtx.lineTo(targetNode.x, targetNode.y);
                rCtx.stroke();
                rCtx.shadowBlur = 0;

                // Moving particle packet
                const partProgress = (tick % 45) / 45;
                const partX = midX + (targetNode.x - midX) * partProgress;
                const partY = midY + (targetNode.y - midY) * partProgress;
                rCtx.fillStyle = "#ffffff";
                rCtx.beginPath();
                rCtx.arc(partX, partY, 3, 0, Math.PI * 2);
                rCtx.fill();
            }

            // 5. Draw Binance Core Hub
            const hubPulse = 18 + Math.sin(tick * 0.06) * 3;
            rCtx.fillStyle = "rgba(240, 185, 11, 0.12)";
            rCtx.beginPath();
            rCtx.arc(midX, midY, hubPulse + 8, 0, Math.PI * 2);
            rCtx.fill();

            // Core Polygon
            rCtx.fillStyle = "#F0B90B";
            rCtx.shadowColor = "rgba(240, 185, 11, 0.5)";
            rCtx.shadowBlur = 14;
            rCtx.beginPath();
            rCtx.arc(midX, midY, 18, 0, Math.PI * 2);
            rCtx.fill();
            rCtx.shadowBlur = 0;

            // Core Label
            rCtx.fillStyle = "#000000";
            rCtx.font = "bold 8.5px 'JetBrains Mono'";
            rCtx.textAlign = "center";
            rCtx.textBaseline = "middle";
            rCtx.fillText("BINANCE", midX, midY);

            // 6. Draw Orbiting Coin Satellites
            radarCoins.forEach(coin => {
                const isTarget = (coin === targetNode);
                const nRadius = isTarget ? 15 : 12;

                if (isTarget) {
                    rCtx.strokeStyle = "#F0B90B";
                    rCtx.lineWidth = 2;
                    rCtx.shadowColor = "#F0B90B";
                    rCtx.shadowBlur = 8;
                    rCtx.beginPath();
                    rCtx.arc(coin.x, coin.y, nRadius + 4, 0, Math.PI * 2);
                    rCtx.stroke();
                    rCtx.shadowBlur = 0;
                }

                let color = "#334155";
                if (coin.struct.includes("BULL") || coin.struct.includes("UP")) color = "#0ecb81";
                else if (coin.struct.includes("BEAR") || coin.struct.includes("DOWN")) color = "#f6465d";
                else color = "#38bdf8";

                if (isTarget) color = "#F0B90B";

                rCtx.fillStyle = color;
                rCtx.beginPath();
                rCtx.arc(coin.x, coin.y, nRadius, 0, Math.PI * 2);
                rCtx.fill();

                rCtx.fillStyle = "#0b1017";
                rCtx.beginPath();
                rCtx.arc(coin.x, coin.y, nRadius - 2.5, 0, Math.PI * 2);
                rCtx.fill();

                rCtx.fillStyle = isTarget ? "#F0B90B" : "#f8fafc";
                rCtx.font = isTarget ? "bold 9px 'JetBrains Mono'" : "600 8px 'JetBrains Mono'";
                rCtx.textAlign = "center";
                rCtx.textBaseline = "middle";
                rCtx.fillText(coin.sym, coin.x, coin.y);
            });

            requestAnimationFrame(renderRadar);
        }
        renderRadar();

        // --- 2. DATA POLLING & POSITION LOGIC ---
        let rawTradeList = [];
        let activeTradeTab = 'session'; // 'session' or 'all'

        async function fetchDashboard() {
            try {
                const res = await fetch('/api/dashboard-summary');
                if (!res.ok) return;
                const d = await res.json();

                // 1. Balance & Capital
                const cur = parseFloat(d.current_balance || 99.5399);
                const init = parseFloat(d.initial_capital || 101.15);
                const avail = parseFloat(d.available_balance || cur);
                const net = parseFloat(d.net_pnl_usd || (cur - init));
                const roi = parseFloat(d.roi_pct || ((net / init) * 100));

                document.getElementById('valCurrentBal').textContent = '$' + cur.toFixed(2);
                document.getElementById('valAvailBal').textContent = `Tersedia: $${avail.toFixed(2)} USDT`;
                document.getElementById('valInitialCap').textContent = '$' + init.toFixed(2);
                document.getElementById('valTopUpNotice').textContent = `Setoran Pokok: $${init.toFixed(2)}`;

                // 2. Net PnL Styling
                const pnlEl = document.getElementById('valNetPnl');
                const roiBadge = document.getElementById('badgeRoi');
                pnlEl.textContent = (net >= 0 ? '+$' : '-$') + Math.abs(net).toFixed(2);
                roiBadge.textContent = (roi >= 0 ? '+' : '') + roi.toFixed(2) + '%';

                if (net >= 0) {
                    pnlEl.style.color = 'var(--bull-green)';
                    roiBadge.className = 'badge badge-green';
                } else {
                    pnlEl.style.color = 'var(--bear-red)';
                    roiBadge.className = 'badge badge-red';
                }

                // 3. Modal Mode (Buffer / Compounding)
                const badgeMode = document.getElementById('badgeMode');
                const valModeDesc = document.getElementById('valModeDesc');
                if (cur < 100.0) {
                    badgeMode.textContent = "FLAT BUFFER";
                    badgeMode.className = "badge badge-gold";
                    valModeDesc.textContent = "Flat $1.00";
                    document.getElementById('ruleMarginVal').textContent = "Tepat $1.00 (Saldo < $100)";
                } else {
                    badgeMode.textContent = "COMPOUNDING";
                    badgeMode.className = "badge badge-green";
                    valModeDesc.textContent = "Comp 1.0% (" + (cur * 0.01).toFixed(2) + " USD)";
                    document.getElementById('ruleMarginVal').textContent = "1.0% Saldo ($" + (cur * 0.01).toFixed(2) + ")";
                }

                // 4. Active Position Terminal Logic
                const posTerminal = document.getElementById('sec-position');
                const viewOpen = document.getElementById('viewPosOpen');
                const viewStandby = document.getElementById('viewPosStandby');
                const posSymbolText = document.getElementById('posSymbolText');
                const posTypeBadge = document.getElementById('posTypeBadge');
                const posSubtitle = document.getElementById('posSubtitle');
                const posLevBadge = document.getElementById('posLevBadge');

                const pos = d.active_position;
                if (pos && pos.symbol) {
                    posTerminal.classList.add('is-open');
                    viewOpen.style.display = 'block';
                    viewStandby.style.display = 'none';

                    const isLong = (pos.side === 'BUY' || pos.side === 'LONG');
                    posTypeBadge.textContent = isLong ? "LONG" : "SHORT";
                    posTypeBadge.className = isLong ? "badge badge-green" : "badge badge-red";
                    posSymbolText.textContent = pos.symbol;
                    posSubtitle.textContent = `Posisi live aktif | Dibuka pada harga $${parseFloat(pos.entry_price || 0).toFixed(4)}`;
                    posLevBadge.textContent = `${pos.leverage || 50}X ISOLATED`;

                    document.getElementById('specMargin').textContent = `$${parseFloat(pos.margin || 1.0).toFixed(2)} USDT`;
                    document.getElementById('specNotional').textContent = `$${parseFloat(pos.notional || 50.0).toFixed(2)} USDT`;
                    document.getElementById('specEntry').textContent = `$${parseFloat(pos.entry_price || 0).toFixed(4)}`;
                    document.getElementById('specMark').textContent = `$${parseFloat(pos.mark_price || pos.entry_price || 0).toFixed(4)}`;

                    const unPnl = parseFloat(pos.unrealized_pnl || 0);
                    const unPnlEl = document.getElementById('specUnPnl');
                    unPnlEl.textContent = (unPnl >= 0 ? '+$' : '-$') + Math.abs(unPnl).toFixed(4);
                    unPnlEl.style.color = unPnl >= 0 ? 'var(--bull-green)' : 'var(--bear-red)';

                    document.getElementById('specTp').textContent = `$${parseFloat(pos.tp_price || 0).toFixed(4)}`;
                    document.getElementById('specSl').textContent = `$${parseFloat(pos.sl_price || 0).toFixed(4)}`;
                    document.getElementById('specLiq').textContent = pos.liquidation_price ? `$${parseFloat(pos.liquidation_price).toFixed(4)}` : "Aman (>15%)";

                    // Update SL-Entry-TP Gauge
                    const entryP = parseFloat(pos.entry_price || 0);
                    const markP = parseFloat(pos.mark_price || entryP);
                    const slP = parseFloat(pos.sl_price || (entryP * 0.99));
                    const tpP = parseFloat(pos.tp_price || (entryP * 1.02));

                    document.getElementById('gaugeSlVal').textContent = slP.toFixed(2);
                    document.getElementById('gaugeEntryVal').textContent = entryP.toFixed(2);
                    document.getElementById('gaugeTpVal').textContent = tpP.toFixed(2);

                    let pinPct = 50;
                    if (isLong) {
                        const totalRange = (tpP - slP) || 1;
                        pinPct = Math.max(5, Math.min(95, ((markP - slP) / totalRange) * 100));
                    } else {
                        const totalRange = (slP - tpP) || 1;
                        pinPct = Math.max(5, Math.min(95, ((slP - markP) / totalRange) * 100));
                    }
                    document.getElementById('gaugeLivePin').style.left = pinPct + '%';

                } else {
                    posTerminal.classList.remove('is-open');
                    viewOpen.style.display = 'none';
                    viewStandby.style.display = 'block';

                    posTypeBadge.textContent = "STANDBY";
                    posTypeBadge.className = "badge badge-neutral";
                    posSymbolText.textContent = "Menunggu Sinyal Presisi";
                    posSubtitle.textContent = "Sedang menyisir semesta koin mencari setup confluence A+ (Skor $\ge$ 80).";
                    posLevBadge.textContent = "50X ISOLATED";
                }

                // 5. Radar Live Target & Rotation
                if (d.rotation_status) {
                    document.getElementById('badgeRotNumber').textContent = d.rotation_status.split('(')[0].trim().toUpperCase();
                }
                if (d.current_coin && d.current_coin.symbol) {
                    liveTargetSymbol = d.current_coin.symbol;
                    document.getElementById('liveActiveSymbol').textContent = d.current_coin.symbol;
                    const struct = d.current_coin.market_structure_1h || "SIDEWAYS";
                    const score = d.current_coin.score || 50;
                    const volM = d.current_coin.vol_24h_m ? `$${d.current_coin.vol_24h_m.toFixed(1)}M` : "";
                    document.getElementById('liveActiveMetrics').textContent = `Struktur: ${struct} | Skor: ${score}/100 ${volM ? '| Vol: ' + volM : ''}`;
                }

                // 6. Header Info
                document.getElementById('topUptime').textContent = `UPTIME: ${(d.uptime_str || 'AKTIF 24/7').toUpperCase()}`;
                document.getElementById('wsStatusText').textContent = `${d.tracked_symbols_count || 829} KOIN LIVE`;

            } catch (err) {
                console.warn("Dashboard sync notice:", err);
            }
        }

        // --- 3. TRADE HISTORY ENGINE (VPS SESSION VS ALL) ---
        async function fetchTradeHistory() {
            try {
                const res = await fetch('/api/trade-history');
                if (!res.ok) return;
                const d = await res.json();
                rawTradeList = d.trades || [];
                renderTrades();
            } catch (err) {
                console.warn("Trade history fetch notice:", err);
            }
        }

        function switchTradeTab(tab) {
            activeTradeTab = tab;
            document.getElementById('tabVpsSession').classList.toggle('active', tab === 'session');
            document.getElementById('tabAllHistory').classList.toggle('active', tab === 'all');
            renderTrades();
        }

        function renderTrades() {
            const container = document.getElementById('tradesContainer');
            const summaryPill = document.getElementById('tradeSummaryPill');

            // Filter trades based on active tab
            let listToRender = [];
            if (activeTradeTab === 'session') {
                listToRender = rawTradeList.filter(t => t.is_vps_session === true);
                summaryPill.textContent = `${listToRender.length} TRADE SESI VPS`;
            } else {
                listToRender = rawTradeList;
                summaryPill.textContent = `${rawTradeList.length} TOTAL TRADE`;
            }

            if (listToRender.length === 0) {
                if (activeTradeTab === 'session') {
                    container.innerHTML = `
                        <div style="text-align: center; padding: 22px 14px; background: rgba(0,0,0,0.25); border-radius: 12px; border: 1px solid rgba(255,255,255,0.03);">
                            <div style="color: var(--binance-gold); font-size: 13px; font-weight: 700; margin-bottom: 4px;">Belum Ada Posisi Baru di Sesi VPS Ini</div>
                            <p style="color: var(--text-secondary); font-size: 11px; line-height: 1.5; max-width: 440px; margin: 0 auto;">
                                Bot aktif sejak 26 Okt 2026. Mesin disiplin memindai semesta 500 koin dan hanya mengeksekusi order saat setup confluence (Skor $\ge$ 80, S&R teruji $\ge$ 2x, dan Liquidity Sweep) terkonfirmasi.
                            </p>
                        </div>
                    `;
                } else {
                    container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-dim); font-size: 12px;">Tidak ada riwayat trade.</div>';
                }
                return;
            }

            let html = '';
            listToRender.forEach(t => {
                const isWin = (t.result === 'WIN' || parseFloat(t.pnl_usd || 0) >= 0);
                const pnlVal = parseFloat(t.pnl_usd || 0);
                const pnlColor = isWin ? 'var(--bull-green)' : 'var(--bear-red)';
                const sideColor = (t.side === 'BUY' || t.side === 'LONG') ? 'badge-green' : 'badge-red';

                html += `
                    <div class="trade-card-item">
                        <div class="trade-col-left">
                            <div class="ticker-row">
                                <span class="badge ${sideColor}">${t.side || 'BUY'}</span>
                                <span>${t.symbol}</span>
                                <span class="badge badge-neutral" style="font-size: 9px;">${t.leverage || 50}x</span>
                            </div>
                            <div class="date-row">${t.created_at || 'Selesai'}</div>
                        </div>
                        <div class="trade-col-right">
                            <div class="pnl-text" style="color: ${pnlColor};">
                                ${pnlVal >= 0 ? '+$' : '-$'}${Math.abs(pnlVal).toFixed(4)}
                            </div>
                            <div class="price-row">
                                In: $${parseFloat(t.entry_price || 0).toFixed(4)} &bull; Out: $${parseFloat(t.exit_price || 0).toFixed(4)}
                            </div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        // --- 4. LIVE LOGS TERMINAL ---
        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                if (!res.ok) return;
                const d = await res.json();
                const term = document.getElementById('terminalLogsBox');
                if (d.logs && d.logs.length > 0) {
                    term.innerHTML = d.logs.map(l => {
                        let color = '#94a3b8';
                        if (l.includes("Sukses") || l.includes("TERHUBUNG") || l.includes("200 OK")) color = '#0ecb81';
                        else if (l.includes("Error") || l.includes("WARN") || l.includes("code': -")) color = '#f6465d';
                        else if (l.includes("Rotasi") || l.includes("Auto-Sync")) color = '#F0B90B';
                        return `<div style="color: ${color};">${escapeHtml(l)}</div>`;
                    }).join('');
                    term.scrollTop = term.scrollHeight;
                }
            } catch (err) {
                console.warn("Logs poll notice:", err);
            }
        }

        function escapeHtml(t) {
            return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        // --- Initial Starts & Polling ---
        fetchDashboard();
        fetchTradeHistory();
        fetchLogs();

        setInterval(fetchDashboard, 3000);   // Poll dashboard & position every 3s
        setInterval(fetchTradeHistory, 15000); // Refresh trades every 15s
        setInterval(fetchLogs, 5000);        // Refresh logs every 5s
    </script>
</body>
</html>
"""

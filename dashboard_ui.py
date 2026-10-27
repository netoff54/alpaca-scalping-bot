"""
HTML & JavaScript Web Dashboard - Institutional Crypto Terminal (Mobile-First)
Antarmuka pemantauan 24/7 Binance Futures Autonomous Scalper.
Desain Dark Obsidian Glassmorphism dengan Konstelasi Bubble Jaringan Koin,
Terminal Posisi Aktif, Penjelasan Proteksi Drawdown & Margin Dinamis, serta Riwayat Win Rate.
"""

def get_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#070a10">
    <title>Binance Futures Scalper — Institutional Terminal</title>

    <!-- Google Fonts: Plus Jakarta Sans & JetBrains Mono -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">

    <style>
        :root {
            --bg-base: #06080e;
            --bg-card: #0c1017;
            --bg-card-sub: #131922;
            --border-card: rgba(255, 255, 255, 0.07);
            --border-card-subtle: rgba(255, 255, 255, 0.04);
            
            --binance-gold: #F0B90B;
            --binance-gold-hover: #fcd535;
            --gold-glow: rgba(240, 185, 11, 0.22);
            --bull-green: #0ecb81;
            --bull-glow: rgba(14, 203, 129, 0.25);
            --bear-red: #f6465d;
            --bear-glow: rgba(246, 70, 93, 0.25);
            --cyan-accent: #00e5ff;
            
            --text-primary: #eaecef;
            --text-secondary: #9aa4b2;
            --text-dim: #5a6677;

            --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
            font-family: var(--font-sans);
            font-size: 13px;
            line-height: 1.45;
            padding-bottom: 50px;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }

        /* Ambient subtle background glow */
        body::before {
            content: '';
            position: fixed;
            top: -120px;
            left: 50%;
            transform: translateX(-50%);
            width: 600px;
            height: 300px;
            background: radial-gradient(circle, rgba(240, 185, 11, 0.05) 0%, rgba(6, 8, 14, 0) 70%);
            pointer-events: none;
            z-index: 0;
        }

        .container {
            max-width: 680px;
            margin: 0 auto;
            padding: 12px 14px;
            position: relative;
            z-index: 1;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        /* 1. TOP NAVBAR / HEADER */
        .top-navbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid var(--border-card-subtle);
        }

        .brand-block {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .brand-icon {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            background: rgba(240, 185, 11, 0.12);
            border: 1px solid rgba(240, 185, 11, 0.35);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--binance-gold);
            box-shadow: 0 0 15px var(--gold-glow);
        }

        .brand-icon svg {
            width: 18px;
            height: 18px;
        }

        .brand-text h1 {
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.3px;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .brand-text p {
            font-size: 10px;
            color: var(--text-dim);
            font-family: var(--font-mono);
            letter-spacing: 0.2px;
        }

        .nav-right-meta {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .live-status-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 9px;
            background: rgba(14, 203, 129, 0.08);
            border: 1px solid rgba(14, 203, 129, 0.25);
            border-radius: 20px;
            font-size: 10px;
            font-weight: 700;
            color: var(--bull-green);
            font-family: var(--font-mono);
        }

        .live-dot {
            width: 6px;
            height: 6px;
            background: var(--bull-green);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--bull-green);
            animation: pulseDot 2s infinite ease-in-out;
        }

        @keyframes pulseDot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }

        .btn-refresh {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            color: var(--text-secondary);
            border-radius: 8px;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-refresh:active {
            transform: scale(0.92);
            color: var(--binance-gold);
            border-color: var(--binance-gold);
        }

        .btn-refresh svg {
            width: 14px;
            height: 14px;
        }

        /* 2. OVERVIEW METRICS GRID (4 CARDS) */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            transition: border-color 0.2s;
        }

        .card-label-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }

        .card-label {
            font-size: 10.5px;
            font-weight: 600;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.4px;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .card-label svg {
            width: 13px;
            height: 13px;
            opacity: 0.7;
        }

        .badge {
            font-size: 9px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: var(--font-mono);
            letter-spacing: 0.2px;
        }

        .badge-gold { background: rgba(240, 185, 11, 0.15); color: var(--binance-gold); border: 1px solid rgba(240, 185, 11, 0.3); }
        .badge-green { background: rgba(14, 203, 129, 0.12); color: var(--bull-green); border: 1px solid rgba(14, 203, 129, 0.3); }
        .badge-red { background: rgba(246, 70, 93, 0.12); color: var(--bear-red); border: 1px solid rgba(246, 70, 93, 0.3); }
        .badge-cyan { background: rgba(0, 229, 255, 0.12); color: var(--cyan-accent); border: 1px solid rgba(0, 229, 255, 0.3); }
        .badge-neutral { background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); border: 1px solid rgba(255, 255, 255, 0.08); }

        .metric-value {
            font-size: 19px;
            font-weight: 800;
            font-family: var(--font-mono);
            letter-spacing: -0.5px;
            color: #ffffff;
            margin: 2px 0;
        }

        .metric-sub {
            font-size: 10px;
            color: var(--text-secondary);
            font-family: var(--font-sans);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* 3. TERMINAL POSISI AKTIF / SINYAL PRESISI */
        .position-terminal {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 16px;
            position: relative;
            overflow: hidden;
        }

        .position-terminal.is-open {
            border-color: rgba(240, 185, 11, 0.4);
            box-shadow: 0 4px 20px rgba(240, 185, 11, 0.06);
        }

        .pos-header-flex {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }

        .pos-symbol-block {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .pos-symbol-row {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .pos-symbol-text {
            font-size: 16px;
            font-weight: 800;
            font-family: var(--font-mono);
            color: #ffffff;
            letter-spacing: 0.3px;
        }

        .pos-subtitle {
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        .pos-pnl-block {
            text-align: right;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .pos-pnl-val {
            font-size: 18px;
            font-weight: 800;
            font-family: var(--font-mono);
        }

        .pos-pnl-pct {
            font-size: 11px;
            font-family: var(--font-mono);
            font-weight: 600;
        }

        /* Grid Spesifikasi Posisi Terbuka */
        .pos-specs-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            background: var(--bg-card-sub);
            border-radius: 12px;
            padding: 12px;
            border: 1px solid var(--border-card-subtle);
            margin-bottom: 12px;
        }

        .pos-spec-item {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .pos-spec-label {
            font-size: 9.5px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 600;
        }

        .pos-spec-val {
            font-size: 12.5px;
            font-weight: 700;
            font-family: var(--font-mono);
            color: var(--text-primary);
        }

        /* Gauge SL / TP */
        .gauge-container {
            background: rgba(0, 0, 0, 0.35);
            border-radius: 10px;
            padding: 10px 12px;
            border: 1px solid var(--border-card-subtle);
        }

        .gauge-label-row {
            display: flex;
            justify-content: space-between;
            font-size: 10.5px;
            font-family: var(--font-mono);
            margin-bottom: 6px;
        }

        .gauge-track {
            height: 6px;
            background: #1a2230;
            border-radius: 3px;
            position: relative;
            overflow: visible;
        }

        .gauge-fill {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            background: linear-gradient(90deg, var(--bear-red) 0%, #f0b90b 50%, var(--bull-green) 100%);
            border-radius: 3px;
            width: 100%;
            opacity: 0.6;
        }

        .gauge-pin {
            position: absolute;
            top: -5px;
            width: 6px;
            height: 16px;
            background: #ffffff;
            border: 2px solid var(--binance-gold);
            border-radius: 3px;
            transform: translateX(-50%);
            box-shadow: 0 0 8px rgba(240, 185, 11, 0.8);
            transition: left 0.3s;
        }

        /* Standby Hunting Box */
        .standby-box {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .standby-headline {
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-card-subtle);
        }

        .standby-icon {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            background: rgba(240, 185, 11, 0.08);
            border: 1px solid rgba(240, 185, 11, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--binance-gold);
            flex-shrink: 0;
        }

        .standby-icon svg {
            width: 20px;
            height: 20px;
        }

        .standby-text h3 {
            font-size: 13.5px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .standby-text p {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 2px;
            line-height: 1.4;
        }

        .standby-rules-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }

        .rule-card {
            background: rgba(0, 0, 0, 0.25);
            border: 1px solid var(--border-card-subtle);
            border-radius: 10px;
            padding: 10px 12px;
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .rule-card .rule-title {
            font-size: 9.5px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.3px;
        }

        .rule-card .rule-val {
            font-size: 12px;
            font-family: var(--font-mono);
            font-weight: 700;
            color: var(--text-primary);
        }

        .rule-card .rule-desc {
            font-size: 10px;
            color: var(--text-secondary);
            line-height: 1.35;
            margin-top: 2px;
        }

        /* 4. KONSTELASI JARINGAN BUBBLE KOIN (BUKAN RADAR) */
        .bubble-net-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 16px;
        }

        .bubble-canvas-wrapper {
            position: relative;
            width: 100%;
            height: 380px;
            background: #070a10;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            overflow: hidden;
            margin-top: 10px;
        }

        #bubbleCanvas {
            width: 100%;
            height: 100%;
            display: block;
        }

        .active-scan-footer {
            margin-top: 10px;
            padding: 10px 14px;
            background: rgba(240, 185, 11, 0.05);
            border: 1px solid rgba(240, 185, 11, 0.16);
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
            font-size: 9.5px;
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
            font-size: 10.5px;
            font-family: var(--font-mono);
            color: var(--text-secondary);
            line-height: 1.4;
        }

        /* 5. RIWAYAT POSISI & EKSEKUSI + WIN RATE */
        .history-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 16px;
        }

        .history-tab-group {
            display: flex;
            background: rgba(0, 0, 0, 0.4);
            padding: 3px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin: 10px 0;
        }

        .history-tab-btn {
            flex: 1;
            padding: 8px 10px;
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
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        /* Win Rate & Performance Mini Strip */
        .stats-overview-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
            margin-bottom: 12px;
        }

        .stat-mini-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-card-subtle);
            border-radius: 8px;
            padding: 7px 6px;
            text-align: center;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .stat-mini-label {
            font-size: 8.5px;
            color: var(--text-dim);
            font-weight: 700;
            text-transform: uppercase;
        }

        .stat-mini-val {
            font-size: 12px;
            font-family: var(--font-mono);
            font-weight: 800;
            color: #ffffff;
        }

        .trade-items-wrapper {
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 310px;
            overflow-y: auto;
        }

        .trade-card-item {
            padding: 10px 12px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .trade-col-left {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .trade-col-left .ticker-row {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 700;
            font-size: 12.5px;
            font-family: var(--font-mono);
        }

        .trade-col-left .date-row {
            font-size: 9.5px;
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
            font-size: 13px;
            font-weight: 800;
            font-family: var(--font-mono);
        }

        .trade-col-right .price-row {
            font-size: 9.5px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }

        /* 6. LOGS TERMINAL (LINUX VPS MATRIX GREEN) */
        .logs-box-card {
            background: #020603;
            border: 1px solid rgba(0, 255, 102, 0.2);
            border-radius: 16px;
            padding: 14px;
            box-shadow: 0 4px 20px rgba(0, 255, 102, 0.04);
        }

        .logs-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .logs-content {
            background: #010402;
            border: 1px solid rgba(0, 255, 102, 0.15);
            border-radius: 10px;
            padding: 12px;
            font-family: var(--font-mono);
            font-size: 10.5px;
            color: #00ff66;
            text-shadow: 0 0 3px rgba(0, 255, 102, 0.35);
            height: 190px;
            overflow-y: auto;
            line-height: 1.55;
            white-space: pre-wrap;
            word-break: break-all;
        }

        .logs-content::-webkit-scrollbar-thumb {
            background: rgba(0, 255, 102, 0.3);
            border-radius: 4px;
        }
        .logs-content::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 255, 102, 0.6);
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.25); }

        @media (max-width: 480px) {
            .container { padding: 10px 12px; gap: 12px; }
            .metric-value { font-size: 17px; }
            .bubble-canvas-wrapper { height: 340px; }
            .stats-overview-grid { grid-template-columns: repeat(2, 1fr); gap: 6px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 1. TOP NAVBAR -->
        <header class="top-navbar">
            <div class="brand-block">
                <div class="brand-icon">
                    <!-- Binance Diamond Monogram SVG -->
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2L6 8l2.5 2.5L12 7l3.5 3.5L18 8l-6-6zm0 15l-3.5-3.5L6 16l6 6 6-6-2.5-2.5L12 17zm-6-7l-3.5 3.5L6 17l2.5-2.5L5 11l1-1zm12 0l-1 1 2.5 2.5L18 17l3.5-3.5L18 10zM12 9l-2.5 2.5L12 14l2.5-2.5L12 9z"/>
                    </svg>
                </div>
                <div class="brand-text">
                    <h1>BINANCE PRO <span class="badge badge-gold">AUTONOMOUS</span></h1>
                    <p id="topUptime">UPTIME: MEMUAT...</p>
                </div>
            </div>
            <div class="nav-right-meta">
                <div class="live-status-pill">
                    <span class="live-dot"></span>
                    <span id="wsStatusText">427 KOIN LIVE</span>
                </div>
                <button class="btn-refresh" onclick="forceSync()" title="Refresh Dashboard">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                    </svg>
                </button>
            </div>
        </header>

        <!-- 2. OVERVIEW METRICS GRID (4 CARDS) -->
        <section class="metrics-grid">
            <!-- Card 1: Saldo Dompet -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4M3 5v14a2 2 0 0 0 2 2h16v-5M18 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>
                        Saldo Dompet
                    </span>
                    <span class="badge badge-gold">LIVE</span>
                </div>
                <div class="metric-value" id="valCurrentBal">$0.00</div>
                <div class="metric-sub" id="valAvailBal">Tersedia: $0.00 USDT</div>
            </div>

            <!-- Card 2: Modal Pokok -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                        Modal Pokok
                    </span>
                    <span class="badge badge-cyan">P2P SYNC</span>
                </div>
                <div class="metric-value" id="valInitialCap">$101.15</div>
                <div class="metric-sub" id="valTopUpNotice">Sinkronisasi Otomatis Top-Up</div>
            </div>

            <!-- Card 3: Net PnL -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                        Hasil Bersih
                    </span>
                    <span class="badge" id="badgeRoi">0.00%</span>
                </div>
                <div class="metric-value" id="valNetPnl">$0.00</div>
                <div class="metric-sub" id="valPnlSubtext">Selaras Buku Resmi Binance</div>
            </div>

            <!-- Card 4: Manajemen Modal -->
            <div class="card">
                <div class="card-label-row">
                    <span class="card-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                        Aturan Modal
                    </span>
                    <span class="badge badge-neutral" id="badgeMode">BUFFER AKTIF</span>
                </div>
                <div class="metric-value" style="font-size: 16px;" id="valModeDesc">Flat $1.00 USDT</div>
                <div class="metric-sub" id="valModeTarget">Compounding 1% aktif saat saldo mencapai $100</div>
            </div>
        </section>

        <!-- 3. TERMINAL POSISI AKTIF & STATUS HUNTING -->
        <section class="position-terminal" id="sec-position">
            <div class="pos-header-flex">
                <div class="pos-symbol-block">
                    <div class="pos-symbol-row">
                        <span class="badge badge-neutral" id="posTypeBadge">STANDBY</span>
                        <span class="pos-symbol-text" id="posSymbolText">Menunggu Sinyal Presisi</span>
                        <span class="badge badge-gold" id="posLevBadge">50X ISOLATED</span>
                    </div>
                    <div class="pos-subtitle" id="posSubtitle">
                        Sedang menyisir semesta koin mencari setup konfluensi tinggi (Minimal Skor 80/100).
                    </div>
                </div>
                <div class="pos-pnl-block" id="posPnlBlock" style="display: none;">
                    <span class="pos-pnl-val" id="posPnlVal">$0.00</span>
                    <span class="pos-pnl-pct" id="posPnlPct">0.00%</span>
                </div>
            </div>

            <!-- A. POSISI TERBUKA (LIVE TRADE) -->
            <div id="viewPosOpen" style="display: none;">
                <div class="pos-specs-grid">
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Margin Terpakai</span>
                        <span class="pos-spec-val" id="specMargin">$0.00 USDT</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Ukuran Posisi (Notional)</span>
                        <span class="pos-spec-val" id="specNotional">$0.00 USDT</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Harga Entry</span>
                        <span class="pos-spec-val" id="specEntry">$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Harga Pasar Terkini</span>
                        <span class="pos-spec-val" id="specMark">$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Target Take Profit (+2.5%)</span>
                        <span class="pos-spec-val" style="color: var(--bull-green);" id="specTp">$0.00</span>
                    </div>
                    <div class="pos-spec-item">
                        <span class="pos-spec-label">Batas Stop Loss (-1.0%)</span>
                        <span class="pos-spec-val" style="color: var(--bear-red);" id="specSl">$0.00</span>
                    </div>
                    <div class="pos-spec-item" style="grid-column: span 2;">
                        <span class="pos-spec-label">Estimasi Harga Likuidasi</span>
                        <span class="pos-spec-val" id="specLiq" style="color: var(--binance-gold);">$0.00</span>
                    </div>
                </div>

                <!-- SL - Entry - TP Visual Gauge -->
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

            <!-- B. TAMPILAN STANDBY (PENCARIAN SINYAL AKTIF) -->
            <div id="viewPosStandby" class="standby-box">
                <div class="standby-headline">
                    <div class="standby-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/><path d="M22 12h-4M6 12H2M12 6V2M12 22v-4"/><circle cx="12" cy="12" r="3"/>
                        </svg>
                    </div>
                    <div class="standby-text">
                        <h3>Pencarian Sinyal Kalimasada Aktif</h3>
                        <p>Memindai 500 koin semesta 24/7. Hanya membuka posisi saat skor konfluensi mencapai minimal 80 dari 100.</p>
                    </div>
                </div>

                <div class="standby-rules-list">
                    <!-- Rule 1: Margin -->
                    <div class="rule-card">
                        <span class="rule-title">Alokasi Margin Posisi</span>
                        <span class="rule-val" id="ruleMarginVal">Tepat $1.00 USDT</span>
                        <span class="rule-desc" id="ruleMarginDesc">Mode Buffer: Saldo di bawah $100 USDT, alokasi dipatok tetap $1.00 per posisi agar modal aman.</span>
                    </div>

                    <!-- Rule 2: Leverage -->
                    <div class="rule-card">
                        <span class="rule-title">Target Leverage Adaptif</span>
                        <span class="rule-val" id="ruleLevVal">Maksimal 50x (20x - 50x)</span>
                        <span class="rule-desc" id="ruleLevDesc">Sistem menembak 50x. Jika Binance membatasi koin tersebut, bot otomatis menurunkan bertahap hingga batas izin (minimal 20x).</span>
                    </div>

                    <!-- Rule 3: Rasio Profit & Rugi -->
                    <div class="rule-card">
                        <span class="rule-title">Target Profit & Stop Loss</span>
                        <span class="rule-val">TP +2.5% | SL -1.0%</span>
                        <span class="rule-desc">Rasio Risk to Reward 1 : 2.5 (Potensi profit 2.5 kali lebih besar dari risiko kerugian).</span>
                    </div>

                    <!-- Rule 4: Proteksi Drawdown -->
                    <div class="rule-card">
                        <span class="rule-title">Proteksi Drawdown Modal</span>
                        <span class="rule-val">Stop Loss 1% & Circuit Breaker</span>
                        <span class="rule-desc">Posisi langsung dipotong rugi jika minus 1% dari margin ($0.01 saat margin $1.00). Jeda otomatis jika 3 kali rugi beruntun.</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- 4. KONSTELASI JARINGAN BUBBLE KOIN (BUKAN RADAR) -->
        <section class="bubble-net-card" id="sec-bubbles">
            <div class="card-label-row">
                <span class="card-label">
                    <!-- Connected Nodes / Constellation SVG -->
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                    </svg>
                    Jaringan Konstelasi Bubble Koin (Multi-Timeframe)
                </span>
                <span class="badge badge-gold" id="badgeRotNumber">ROTASI --/500</span>
            </div>

            <!-- Canvas Jaringan Bubble Luas & Renggang -->
            <div class="bubble-canvas-wrapper">
                <canvas id="bubbleCanvas"></canvas>
            </div>

            <div class="active-scan-footer">
                <div class="active-scan-left">
                    <span>Koin yang Sedang Dianalisis</span>
                    <strong id="liveActiveSymbol">--USDT</strong>
                </div>
                <div class="active-scan-right" id="liveActiveMetrics">
                    Memuat Analisis Multi-Timeframe 15m, 1h, 4h...
                </div>
            </div>
        </section>

        <!-- 5. RIWAYAT POSISI & EKSEKUSI (DENGAN WIN RATE) -->
        <section class="history-card" id="sec-trades">
            <div class="card-label-row">
                <span class="card-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                    Riwayat Posisi & Eksekusi
                </span>
                <span class="badge badge-neutral" id="tradeSummaryPill">0 TRADE</span>
            </div>

            <!-- Tab Switcher: Sesi VPS Terkini vs Seluruh Riwayat -->
            <div class="history-tab-group">
                <button class="history-tab-btn active" id="tabVpsSession" onclick="switchTradeTab('session')">Sesi VPS Terkini</button>
                <button class="history-tab-btn" id="tabAllHistory" onclick="switchTradeTab('all')">Seluruh Riwayat (113 Trade)</button>
            </div>

            <!-- Performance Win Rate Mini Strip -->
            <div class="stats-overview-grid">
                <div class="stat-mini-card">
                    <span class="stat-mini-label">WIN RATE</span>
                    <span class="stat-mini-val" id="statWinRate" style="color: var(--bull-green);">0.0%</span>
                </div>
                <div class="stat-mini-card">
                    <span class="stat-mini-label">TOTAL EKSEKUSI</span>
                    <span class="stat-mini-val" id="statTotalTrades">0 Trade</span>
                </div>
                <div class="stat-mini-card">
                    <span class="stat-mini-label">WIN / LOSS</span>
                    <span class="stat-mini-val" id="statWinLoss">0W / 0L</span>
                </div>
                <div class="stat-mini-card">
                    <span class="stat-mini-label">TOTAL PNL</span>
                    <span class="stat-mini-val" id="statNetPnlTrade">$0.00</span>
                </div>
            </div>

            <!-- Kontainer Daftar Transaksi -->
            <div class="trade-items-wrapper" id="tradesContainer">
                <div style="text-align: center; padding: 24px; color: var(--text-dim); font-size: 11px;">
                    Memuat riwayat transaksi...
                </div>
            </div>
        </section>

        <!-- 6. LIVE ENGINE LOGS -->
        <section class="logs-box-card" id="sec-logs">
            <div class="logs-header-row">
                <span class="card-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
                    </svg>
                    Feed Log Mesin VPS
                </span>
                <span class="badge" id="logScrollBadge" style="background: rgba(0, 255, 102, 0.1); color: #00ff66; border: 1px solid rgba(0, 255, 102, 0.3);">LIVE TERMINAL</span>
            </div>
            <div class="logs-content" id="terminalLogs">Menghubungkan stream log...</div>
        </section>
    </div>

    <script>
        // --- GLOBAL APP STATE ---
        let rawTradeList = [];
        let activeTradeTab = 'session';
        let liveTargetSymbol = 'BTCUSDT';
        let currentCoinData = null;
        let lastKnownWallet = 99.54;
        let tick = 0;

        // --- 1. JARINGAN KONSTELASI BUBBLE KOIN (BUKAN RADAR) ---
        const canvas = document.getElementById('bubbleCanvas');
        const ctx = canvas.getContext('2d');

        // Kumpulan awal koin-koin crypto semesta populer
        const INITIAL_COINS = [
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LINK', 'SUI',
            'NEAR', 'PEPE', 'WIF', 'TIA', 'INJ', 'OP', 'ARB', 'APT', 'RENDER', 'FET',
            'FTM', 'SEI', 'GALA', 'STX', 'LDO', 'AR', 'RUNE', 'KAS', 'DYDX', 'JUP',
            'PYTH', 'WLD', 'AAVE', 'UNI', 'PENDLE', 'TON', 'LTC', 'BCH', 'FIL', 'ATOM',
            'DOT', 'CRV', 'BLUR', 'SAND', 'MANA', 'GRT', 'ALGO', 'ICP', 'QNT', 'THETA'
        ];

        let bubbleList = [];
        let canvasW = 600;
        let canvasH = 380;

        function resizeCanvas() {
            const rect = canvas.parentElement.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            canvasW = rect.width;
            canvasH = rect.height;
            canvas.width = canvasW * dpr;
            canvas.height = canvasH * dpr;
            ctx.scale(dpr, dpr);
            redistributeBubblesIfEmpty();
        }

        window.addEventListener('resize', resizeCanvas);

        // Otomatis menyesuaikan ukuran bubble agar fleksibel dan tidak sesak seiring bertambahnya bubble
        function getDynamicBaseRadius() {
            const total = bubbleList.length || 50;
            if (total <= 40) return 13.5;
            if (total <= 70) return 11.5;
            if (total <= 110) return 9.5;
            if (total <= 160) return 8.0;
            if (total <= 220) return 6.8;
            return 5.8;
        }

        // Inisialisasi bubble dengan penyebaran luas (jarak lega, tidak mepet)
        function initBubbles() {
            bubbleList = [];
            const centerX = canvasW / 2;
            const centerY = canvasH / 2;
            const minCenterDist = 65; // Jarak minimal dari hub Binance tengah

            INITIAL_COINS.forEach((sym) => {
                const b = createSpacedBubble(sym, centerX, centerY, minCenterDist);
                bubbleList.push(b);
            });
        }

        function createSpacedBubble(sym, centerX, centerY, minCenterDist) {
            let posX = 0, posY = 0, valid = false, attempts = 0;
            const margin = 26;
            const curR = getDynamicBaseRadius();
            const minOtherDist = Math.max(16, curR * 2.6);

            while (!valid && attempts < 120) {
                attempts++;
                posX = margin + Math.random() * (canvasW - margin * 2);
                posY = margin + Math.random() * (canvasH - margin * 2);

                const distCenter = Math.hypot(posX - centerX, posY - centerY);
                if (distCenter < minCenterDist) continue;

                // Cek jarak dengan bubble lain agar tidak mepet
                let tooClose = false;
                for (let other of bubbleList) {
                    if (Math.hypot(posX - other.baseX, posY - other.baseY) < minOtherDist) {
                        tooClose = true;
                        break;
                    }
                }
                if (!tooClose) valid = true;
            }

            return {
                sym: sym,
                baseX: posX,
                baseY: posY,
                x: posX,
                y: posY,
                floatSpeedX: 0.012 + Math.random() * 0.01,
                floatSpeedY: 0.01 + Math.random() * 0.012,
                phaseX: Math.random() * Math.PI * 2,
                phaseY: Math.random() * Math.PI * 2,
                ampX: 6 + Math.random() * 4,
                ampY: 5 + Math.random() * 4,
                analyzed: false,
                score: 50
            };
        }

        function redistributeBubblesIfEmpty() {
            if (bubbleList.length === 0) {
                initBubbles();
            } else {
                // Skala ulang posisi dasar bubble mengikuti dimensi canvas baru
                const centerX = canvasW / 2;
                const centerY = canvasH / 2;
                bubbleList.forEach(b => {
                    b.baseX = Math.min(canvasW - 30, Math.max(30, b.baseX));
                    b.baseY = Math.min(canvasH - 30, Math.max(30, b.baseY));
                });
            }
        }

        // Animasi Loop Konstelasi Bubble Koin (60 FPS)
        function animateBubbleNetwork() {
            tick++;
            ctx.clearRect(0, 0, canvasW, canvasH);

            const centerX = canvasW / 2;
            const centerY = canvasH / 2;

            // 1. Gambar latar belakang halus bintang / partikel redup
            ctx.fillStyle = "rgba(255, 255, 255, 0.03)";
            for (let i = 0; i < 20; i++) {
                const sx = (Math.sin(i * 99 + tick * 0.002) * 0.5 + 0.5) * canvasW;
                const sy = (Math.cos(i * 77 + tick * 0.002) * 0.5 + 0.5) * canvasH;
                ctx.fillRect(sx, sy, 1.5, 1.5);
            }

            // 2. Tentukan target bubble yang sedang dianalisis
            const cleanTarget = liveTargetSymbol.replace("USDT", "").trim();
            let activeBubble = null;

            // Cari di daftar bubble, jika belum ada, buat bubble baru (bubble tetap standby)
            for (let b of bubbleList) {
                if (b.sym === cleanTarget) {
                    activeBubble = b;
                    break;
                }
            }

            if (!activeBubble && cleanTarget && cleanTarget !== "--") {
                activeBubble = createSpacedBubble(cleanTarget, centerX, centerY, 65);
                activeBubble.sym = cleanTarget;
                bubbleList.push(activeBubble);
            }

            // 3. Update posisi gerak apung alami seluruh bubble
            bubbleList.forEach(b => {
                b.x = b.baseX + Math.sin(tick * b.floatSpeedX + b.phaseX) * b.ampX;
                b.y = b.baseY + Math.cos(tick * b.floatSpeedY + b.phaseY) * b.ampY;

                // Batas kanvas agar tidak keluar area
                b.x = Math.max(20, Math.min(canvasW - 20, b.x));
                b.y = Math.max(20, Math.min(canvasH - 20, b.y));
            });

            // 4. GAMBAR TALI JARINGAN KONEKSI DARI BINANCE KE KOIN AKTIF
            if (activeBubble) {
                activeBubble.analyzed = true;
                if (currentCoinData && currentCoinData.score) {
                    activeBubble.score = currentCoinData.score;
                }

                // A. Garis luar bercahaya emas (Aura Glow Line)
                ctx.strokeStyle = "rgba(240, 185, 11, 0.35)";
                ctx.lineWidth = 4;
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(activeBubble.x, activeBubble.y);
                ctx.stroke();

                // B. Tali inti bersinar (Core Beam)
                ctx.strokeStyle = "rgba(255, 235, 150, 0.95)";
                ctx.lineWidth = 1.5;
                ctx.shadowColor = "#f0b90b";
                ctx.shadowBlur = 8;
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(activeBubble.x, activeBubble.y);
                ctx.stroke();
                ctx.shadowBlur = 0;

                // C. Partikel data bergerak mengalir di tali dari Binance ke koin
                const particleCount = 2;
                for (let p = 0; p < particleCount; p++) {
                    const progress = ((tick * 1.5 + p * 30) % 60) / 60;
                    const px = centerX + (activeBubble.x - centerX) * progress;
                    const py = centerY + (activeBubble.y - centerY) * progress;

                    ctx.fillStyle = "#ffffff";
                    ctx.shadowColor = "#ffffff";
                    ctx.shadowBlur = 6;
                    ctx.beginPath();
                    ctx.arc(px, py, 2.5, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.shadowBlur = 0;
                }

                // D. Gelombang pulsa melingkar di koin target (Expanding Ripple)
                const ripple = (tick % 40) / 40;
                ctx.strokeStyle = `rgba(240, 185, 11, ${1 - ripple})`;
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.arc(activeBubble.x, activeBubble.y, 16 + ripple * 16, 0, Math.PI * 2);
                ctx.stroke();
            }

            // 5. GAMBAR SELURUH BUBBLE KOIN (STANDBY DI KANVAS & UKURAN FLEKSIBEL OTOMATIS)
            const currentBaseR = getDynamicBaseRadius();

            bubbleList.forEach(b => {
                const isActive = (b === activeBubble);
                // Ukuran dinamis: jika aktif membesar 1.5x, jika standby mengikuti ukuran dinamis fleksibel
                const r = isActive ? Math.max(14, currentBaseR * 1.5) + Math.sin(tick * 0.08) * 1.5 : currentBaseR;

                // A. Background Lingkaran Bubble
                ctx.beginPath();
                ctx.arc(b.x, b.y, r, 0, Math.PI * 2);

                if (isActive) {
                    ctx.fillStyle = "rgba(240, 185, 11, 0.25)";
                    ctx.shadowColor = "rgba(240, 185, 11, 0.6)";
                    ctx.shadowBlur = 12;
                } else if (b.analyzed && b.score >= 65) {
                    ctx.fillStyle = "rgba(14, 203, 129, 0.14)";
                    ctx.shadowBlur = 0;
                } else {
                    ctx.fillStyle = "rgba(18, 24, 35, 0.85)";
                    ctx.shadowBlur = 0;
                }
                ctx.fill();

                // B. Border Lingkaran
                ctx.lineWidth = isActive ? 1.8 : 1;
                if (isActive) {
                    ctx.strokeStyle = "#F0B90B";
                } else if (b.analyzed && b.score >= 65) {
                    ctx.strokeStyle = "rgba(14, 203, 129, 0.4)";
                } else {
                    ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
                }
                ctx.stroke();
                ctx.shadowBlur = 0;

                // C. Teks Simbol Koin di Tengah Bubble (Otomatis skala font)
                let fontSize = 8.5;
                if (currentBaseR < 7.0) {
                    fontSize = 0; // Jika koin sudah ratusan dan sangat padat, teks hanya untuk koin aktif
                } else if (currentBaseR < 9.0) {
                    fontSize = 6.5;
                } else if (currentBaseR < 11.0) {
                    fontSize = 7.5;
                }

                if (isActive) {
                    ctx.font = "bold 9px 'JetBrains Mono'";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillStyle = "#FFFFFF";
                    ctx.fillText(b.sym, b.x, b.y);
                } else if (fontSize > 0) {
                    ctx.font = `600 ${fontSize}px 'JetBrains Mono'`;
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillStyle = "rgba(234, 236, 239, 0.75)";
                    ctx.fillText(b.sym, b.x, b.y);
                }

                // D. Skor kecil di atas bubble jika aktif
                if (isActive && currentCoinData && currentCoinData.score) {
                    ctx.font = "bold 8px 'JetBrains Mono'";
                    ctx.fillStyle = "#F0B90B";
                    ctx.fillText(`${currentCoinData.score}/100`, b.x, b.y - r - 5);
                }
            });

            // 6. GAMBAR NODE HUB PUSAT BINANCE CORE
            const hubPulse = 20 + Math.sin(tick * 0.05) * 2;
            
            // Outer Halo
            ctx.fillStyle = "rgba(240, 185, 11, 0.12)";
            ctx.beginPath();
            ctx.arc(centerX, centerY, hubPulse + 8, 0, Math.PI * 2);
            ctx.fill();

            // Core Solid
            ctx.fillStyle = "#121721";
            ctx.strokeStyle = "#F0B90B";
            ctx.lineWidth = 2;
            ctx.shadowColor = "rgba(240, 185, 11, 0.6)";
            ctx.shadowBlur = 14;
            ctx.beginPath();
            ctx.arc(centerX, centerY, 20, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            ctx.shadowBlur = 0;

            // Center Monogram Text
            ctx.font = "bold 9px 'Plus Jakarta Sans'";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "#F0B90B";
            ctx.fillText("BINANCE", centerX, centerY);

            requestAnimationFrame(animateBubbleNetwork);
        }

        // --- 2. LIVE DASHBOARD DATA SYNC ---
        async function fetchDashboardSummary() {
            try {
                const res = await fetch('/api/dashboard-summary');
                if (!res.ok) return;
                const d = await res.json();

                // 1. Saldo Dompet & Modal Pokok
                const curBal = parseFloat(d.current_balance || 99.54);
                lastKnownWallet = curBal;
                document.getElementById('valCurrentBal').textContent = `$${curBal.toFixed(2)}`;
                document.getElementById('valAvailBal').textContent = `Tersedia: $${parseFloat(d.available_balance || curBal).toFixed(2)} USDT`;

                const initCap = parseFloat(d.initial_capital || 101.15);
                document.getElementById('valInitialCap').textContent = `$${initCap.toFixed(2)}`;

                // 2. Net PnL & ROI
                const netPnl = parseFloat(d.net_pnl_usd || (curBal - initCap));
                const roiPct = parseFloat(d.roi_pct || ((netPnl / initCap) * 100));
                const elPnl = document.getElementById('valNetPnl');
                const badgeRoi = document.getElementById('badgeRoi');

                const pnlSign = netPnl >= 0 ? '+' : '';
                elPnl.textContent = `${pnlSign}$${netPnl.toFixed(2)} USDT`;
                badgeRoi.textContent = `${pnlSign}${roiPct.toFixed(2)}%`;

                if (netPnl >= 0) {
                    elPnl.style.color = "var(--bull-green)";
                    badgeRoi.className = "badge badge-green";
                } else {
                    elPnl.style.color = "var(--bear-red)";
                    badgeRoi.className = "badge badge-red";
                }

                // 3. Manajemen Modal Dinamis (Buffer vs Compounding)
                const badgeMode = document.getElementById('badgeMode');
                const valModeDesc = document.getElementById('valModeDesc');
                const valModeTarget = document.getElementById('valModeTarget');
                const ruleMarginVal = document.getElementById('ruleMarginVal');
                const ruleMarginDesc = document.getElementById('ruleMarginDesc');

                if (curBal < 100.0) {
                    badgeMode.textContent = "BUFFER AKTIF";
                    badgeMode.className = "badge badge-neutral";
                    valModeDesc.textContent = "Flat $1.00 USDT";
                    valModeTarget.textContent = "Compounding 1% aktif saat saldo mencapai $100";
                    
                    ruleMarginVal.textContent = "Tepat $1.00 USDT";
                    ruleMarginDesc.textContent = `Mode Buffer: Saldo saat ini $${curBal.toFixed(2)} (di bawah $100 USDT). Alokasi dipatok tetap $1.00 per posisi agar modal aman.`;
                } else {
                    const compMargin = (curBal * 0.01).toFixed(2);
                    badgeMode.textContent = "COMPOUNDING 1%";
                    badgeMode.className = "badge badge-gold";
                    valModeDesc.textContent = `1.0% = $${compMargin} USDT`;
                    valModeTarget.textContent = "Bunga berbunga aktif dari total saldo";

                    ruleMarginVal.textContent = `1.0% = $${compMargin} USDT`;
                    ruleMarginDesc.textContent = `Mode Compounding: Saldo di atas $100 USDT (atau setelah top-up). Alokasi modal otomatis bertumbuh 1.0% dari saldo.`;
                }

                // 4. Target Leverage Adaptif
                const maxCoinLev = d.coin_max_leverage || 50;
                document.getElementById('ruleLevVal').textContent = `Maksimal 50x (Adaptif 20x - 50x)`;
                document.getElementById('ruleLevDesc').textContent = `Sistem menembak 50x. Jika Binance membatasi koin tersebut, bot otomatis menurunkan ke 49x, 48x, hingga batas yang diizinkan (minimal aman 20x). Koin saat ini mendukung hingga: ${maxCoinLev}x.`;

                // 5. Status Terminal Posisi Aktif
                const posTerminal = document.getElementById('sec-position');
                const viewOpen = document.getElementById('viewPosOpen');
                const viewStandby = document.getElementById('viewPosStandby');
                const posPnlBlock = document.getElementById('posPnlBlock');
                const posTypeBadge = document.getElementById('posTypeBadge');
                const posSymbolText = document.getElementById('posSymbolText');
                const posSubtitle = document.getElementById('posSubtitle');
                const posLevBadge = document.getElementById('posLevBadge');

                const pos = d.active_position;
                if (pos && pos.symbol) {
                    posTerminal.classList.add('is-open');
                    viewOpen.style.display = 'block';
                    viewStandby.style.display = 'none';
                    posPnlBlock.style.display = 'flex';

                    const isBuy = (pos.side === 'BUY' || pos.side === 'LONG');
                    posTypeBadge.textContent = isBuy ? 'LONG' : 'SHORT';
                    posTypeBadge.className = isBuy ? 'badge badge-green' : 'badge badge-red';

                    posSymbolText.textContent = pos.symbol;
                    posSubtitle.textContent = `Posisi aktif dieksekusi pada ${pos.entry_time || 'Baru saja'}.`;
                    posLevBadge.textContent = `${pos.leverage || 50}X ISOLATED`;

                    // PnL Kalkulasi Live
                    const unrPnl = parseFloat(pos.unrealized_pnl_usd || 0.0);
                    const unrPct = parseFloat(pos.unrealized_pnl_pct || 0.0);
                    const pnlSignPos = unrPnl >= 0 ? '+' : '';
                    
                    document.getElementById('posPnlVal').textContent = `${pnlSignPos}$${unrPnl.toFixed(4)}`;
                    document.getElementById('posPnlVal').style.color = unrPnl >= 0 ? 'var(--bull-green)' : 'var(--bear-red)';
                    document.getElementById('posPnlPct').textContent = `${pnlSignPos}${unrPct.toFixed(2)}%`;
                    document.getElementById('posPnlPct').style.color = unrPnl >= 0 ? 'var(--bull-green)' : 'var(--bear-red)';

                    // Spesifikasi Posisi
                    document.getElementById('specMargin').textContent = `$${parseFloat(pos.margin_used || 1.0).toFixed(2)} USDT`;
                    document.getElementById('specNotional').textContent = `$${parseFloat(pos.notional_value || 50.0).toFixed(2)} USDT`;
                    document.getElementById('specEntry').textContent = `$${parseFloat(pos.entry_price || 0.0).toFixed(4)}`;
                    document.getElementById('specMark').textContent = `$${parseFloat(pos.current_price || pos.entry_price || 0.0).toFixed(4)}`;
                    document.getElementById('specTp').textContent = `$${parseFloat(pos.tp_price || 0.0).toFixed(4)}`;
                    document.getElementById('specSl').textContent = `$${parseFloat(pos.sl_price || 0.0).toFixed(4)}`;
                    document.getElementById('specLiq').textContent = pos.liquidation_price ? `$${parseFloat(pos.liquidation_price).toFixed(4)}` : 'Aman (Jauh)';

                    // Visual Gauge
                    document.getElementById('gaugeEntryVal').textContent = parseFloat(pos.entry_price || 0.0).toFixed(4);
                    document.getElementById('gaugeSlVal').textContent = parseFloat(pos.sl_price || 0.0).toFixed(4);
                    document.getElementById('gaugeTpVal').textContent = parseFloat(pos.tp_price || 0.0).toFixed(4);

                    const ep = parseFloat(pos.entry_price || 0.0);
                    const cp = parseFloat(pos.current_price || ep);
                    const sl = parseFloat(pos.sl_price || (ep * 0.99));
                    const tp = parseFloat(pos.tp_price || (ep * 1.025));

                    let pinPct = 50;
                    if (tp !== sl) {
                        pinPct = Math.max(5, Math.min(95, ((cp - sl) / (tp - sl)) * 100));
                    }
                    document.getElementById('gaugeLivePin').style.left = pinPct + '%';

                } else {
                    posTerminal.classList.remove('is-open');
                    viewOpen.style.display = 'none';
                    viewStandby.style.display = 'block';
                    posPnlBlock.style.display = 'none';

                    posTypeBadge.textContent = "STANDBY";
                    posTypeBadge.className = "badge badge-neutral";
                    posSymbolText.textContent = "Menunggu Sinyal Presisi";
                    posSubtitle.textContent = "Sedang menyisir semesta koin mencari setup konfluensi tinggi (Minimal Skor 80/100).";
                    posLevBadge.textContent = "50X ISOLATED";
                }

                // 6. Target Analisis & Rotasi Koin
                if (d.rotation_status) {
                    document.getElementById('badgeRotNumber').textContent = d.rotation_status.split('(')[0].trim().toUpperCase();
                }
                if (d.current_coin && d.current_coin.symbol) {
                    liveTargetSymbol = d.current_coin.symbol;
                    currentCoinData = d.current_coin;
                    document.getElementById('liveActiveSymbol').textContent = d.current_coin.symbol;

                    const struct = d.current_coin.market_structure_1h || "SIDEWAYS";
                    const macro = d.current_coin.macro_trend_4h || "NETRAL";
                    const score = d.current_coin.score || 50;
                    const price = d.current_coin.price ? `$${d.current_coin.price}` : "";
                    document.getElementById('liveActiveMetrics').textContent = `Struktur: ${struct} | Makro 4h: ${macro} | Skor: ${score}/100 ${price ? '| ' + price : ''}`;
                }

                // 7. Navbar Info
                document.getElementById('topUptime').textContent = `UPTIME: ${(d.uptime_str || 'AKTIF 24/7').toUpperCase()}`;
                document.getElementById('wsStatusText').textContent = `${d.tracked_symbols_count || 427} KOIN LIVE`;

            } catch (err) {
                console.warn("Dashboard sync notice:", err);
            }
        }

        // --- 3. TRADE HISTORY & WIN RATE ENGINE ---
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

            // Filter riwayat berdasarkan tab yang aktif
            let listToRender = [];
            if (activeTradeTab === 'session') {
                listToRender = rawTradeList.filter(t => t.is_vps_session === true);
                summaryPill.textContent = `${listToRender.length} TRADE SESI VPS`;
            } else {
                listToRender = rawTradeList;
                summaryPill.textContent = `${rawTradeList.length} TOTAL TRADE`;
            }

            // Hitung Statistik Win Rate & PnL
            let winCount = 0;
            let lossCount = 0;
            let totalPnl = 0.0;

            listToRender.forEach(t => {
                const pnl = parseFloat(t.pnl_usd || 0.0);
                const pnlPct = parseFloat(t.pnl_pct || 0.0);
                totalPnl += pnl;

                // ATURAN USER: Stop Loss BEP (SL BEP) tetap dihitung LOSS karena berstatus Stop Loss.
                // Hanya trade yang mencapai Take Profit penuh (+1.5% ke atas) yang dihitung WIN murni.
                const isRealWin = (pnl > 0 && pnlPct >= 1.5);

                if (isRealWin) {
                    winCount++;
                } else {
                    lossCount++;
                }
            });

            const totalTrades = listToRender.length;
            const winRate = totalTrades > 0 ? ((winCount / totalTrades) * 100).toFixed(1) : "0.0";

            document.getElementById('statWinRate').textContent = `${winRate}%`;
            document.getElementById('statTotalTrades').textContent = `${totalTrades} Trade`;
            document.getElementById('statWinLoss').textContent = `${winCount}W / ${lossCount}L`;

            const pnlSign = totalPnl >= 0 ? '+' : '';
            const elStatPnl = document.getElementById('statNetPnlTrade');
            elStatPnl.textContent = `${pnlSign}$${totalPnl.toFixed(2)}`;
            elStatPnl.style.color = totalPnl >= 0 ? 'var(--bull-green)' : 'var(--bear-red)';

            // Tampilan jika belum ada transaksi di sesi ini
            if (listToRender.length === 0) {
                if (activeTradeTab === 'session') {
                    container.innerHTML = `
                        <div style="text-align: center; padding: 22px 14px; background: rgba(0,0,0,0.25); border-radius: 12px; border: 1px solid rgba(255,255,255,0.03);">
                            <div style="color: var(--binance-gold); font-size: 13px; font-weight: 700; margin-bottom: 4px;">Belum Ada Posisi Baru di Sesi VPS Ini</div>
                            <p style="color: var(--text-secondary); font-size: 11px; line-height: 1.5; max-width: 440px; margin: 0 auto;">
                                Bot aktif sejak 26 Oktober 2026. Mesin disiplin memindai 500 koin semesta dan hanya mengeksekusi order jika seluruh kriteria terpenuhi: Minimal Skor 80 dari 100, pantulan Support & Resistance teruji minimal 2 kali, dan konfirmasi Liquidity Sweep. Transaksi baru akan otomatis tercatat di sini seketika order dieksekusi.
                            </p>
                        </div>
                    `;
                } else {
                    container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-dim); font-size: 12px;">Tidak ada riwayat transaksi.</div>';
                }
                return;
            }

            // Render Kartu Transaksi
            let html = '';
            listToRender.forEach(t => {
                const pnlVal = parseFloat(t.pnl_usd || 0.0);
                const pnlPct = parseFloat(t.pnl_pct || 0.0);
                const isRealWin = (pnlVal > 0 && pnlPct >= 1.5);
                const isSlBep = (pnlVal > 0 && pnlPct < 1.5);
                const sign = pnlVal >= 0 ? '+' : '';
                const sideColor = (t.side === 'BUY' || t.side === 'LONG') ? 'badge-green' : 'badge-red';

                let pnlColor = 'var(--bear-red)';
                let resultBadge = '<span class="badge badge-red" style="font-size: 8px;">LOSS</span>';

                if (isRealWin) {
                    pnlColor = 'var(--bull-green)';
                    resultBadge = '<span class="badge badge-green" style="font-size: 8px;">WIN</span>';
                } else if (isSlBep) {
                    pnlColor = 'var(--binance-gold)';
                    resultBadge = '<span class="badge badge-gold" style="font-size: 8px;">SL BEP (LOSS)</span>';
                }

                html += `
                    <div class="trade-card-item">
                        <div class="trade-col-left">
                            <div class="ticker-row">
                                <span class="badge ${sideColor}">${t.side || 'BUY'}</span>
                                <span>${t.symbol}</span>
                                <span class="badge badge-neutral" style="font-size: 9px;">${t.leverage || 50}x</span>
                                ${resultBadge}
                            </div>
                            <div class="date-row">
                                ${t.created_at || '-'} • Margin $${parseFloat(t.margin_used || 1.0).toFixed(2)}
                            </div>
                        </div>
                        <div class="trade-col-right">
                            <div class="pnl-text" style="color: ${pnlColor};">
                                ${sign}$${pnlVal.toFixed(4)} (${sign}${pnlPct.toFixed(2)}%)
                            </div>
                            <div class="price-row">
                                Entry: ${parseFloat(t.entry_price || 0).toFixed(4)} → Exit: ${parseFloat(t.exit_price || 0).toFixed(4)}
                            </div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        // --- 4. LIVE LOGS TERMINAL ---
        let autoScrollLogs = true;
        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs?lines=40');
                if (!res.ok) return;
                const d = await res.json();
                const logBox = document.getElementById('terminalLogs');
                if (d.logs && Array.isArray(d.logs)) {
                    logBox.textContent = d.logs.join('\\n');
                    if (autoScrollLogs) {
                        logBox.scrollTop = logBox.scrollHeight;
                    }
                }
            } catch (err) {
                console.warn("Logs fetch notice:", err);
            }
        }

        function forceSync() {
            fetchDashboardSummary();
            fetchTradeHistory();
            fetchLogs();
        }

        // Inisialisasi awal saat halaman dibuka
        window.addEventListener('DOMContentLoaded', () => {
            resizeCanvas();
            animateBubbleNetwork();
            forceSync();

            // Interval Sinkronisasi
            setInterval(fetchDashboardSummary, 2500);
            setInterval(fetchTradeHistory, 6000);
            setInterval(fetchLogs, 3500);
        });
    </script>
</body>
</html>
"""

DASHBOARD_HTML = get_dashboard_html()


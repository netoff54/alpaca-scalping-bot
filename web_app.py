import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from alpaca_engine import AlpacaBotEngine

app = FastAPI(title="Alpaca Scalping Bot Dashboard")

# Inisialisasi engine dengan env default jika ada
engine = AlpacaBotEngine(
    key_id=os.getenv("APCA_API_KEY_ID", ""),
    secret_key=os.getenv("APCA_API_SECRET_KEY", ""),
    base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
)

class ConfigRequest(BaseModel):
    key_id: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets/v2"

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alpaca Scalping Bot - Localhost Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #0b0e14; color: #e1e7ef; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background-color: #151a23; border: 1px solid #232a3b; border-radius: 12px; margin-bottom: 20px; }
        .card-header { background-color: #1c2331; border-bottom: 1px solid #232a3b; font-weight: 600; }
        .stat-value { font-size: 1.8rem; font-weight: 700; }
        .text-accent { color: #00f2fe; }
        .badge-bullish { background-color: #059669; color: white; padding: 6px 12px; border-radius: 6px; }
        .badge-bearish { background-color: #dc2626; color: white; padding: 6px 12px; border-radius: 6px; }
        .badge-neutral { background-color: #4b5563; color: white; padding: 6px 12px; border-radius: 6px; }
        .log-box { background-color: #080a0f; border-radius: 8px; padding: 12px; height: 280px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; border: 1px solid #1f2737; }
        .log-entry { margin-bottom: 4px; line-height: 1.4; }
        .log-time { color: #64748b; margin-right: 8px; }
        .log-INFO { color: #38bdf8; }
        .log-SUCCESS { color: #4ade80; }
        .log-WARNING { color: #facc15; }
        .log-ERROR { color: #f87171; }
        .btn-alpaca { background-color: #f59e0b; color: #000; font-weight: 600; border: none; }
        .btn-alpaca:hover { background-color: #d97706; color: #000; }
        .pulse { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
        .pulse-green { background-color: #10b981; box-shadow: 0 0 8px #10b981; }
        .pulse-red { background-color: #ef4444; box-shadow: 0 0 8px #ef4444; }
    </style>
</head>
<body>
<div class="container-fluid py-4 px-4">
    <!-- Header -->
    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
        <div>
            <h2 class="mb-1"><i class="fa-solid fa-robot text-accent me-2"></i>Alpaca Scalping Bot <span class="badge bg-dark text-warning border border-warning fs-6">Modal $10 - Isolated</span></h2>
            <small class="text-secondary">Strategi: Triple Filter (EMA 200 + EMA 9/21 + RSI + ATR) | Order: Always Limit (Maker)</small>
        </div>
        <div class="d-flex gap-2 align-items-center">
            <span id="botStatusBadge" class="badge bg-secondary fs-6"><span class="pulse pulse-red"></span>STOPPED</span>
            <button id="btnToggleBot" class="btn btn-success px-4" onclick="toggleBot()"><i class="fa-solid fa-play me-2"></i>Mulai Bot</button>
            <a href="https://app.alpaca.markets/paper/dashboard/overview" target="_blank" class="btn btn-alpaca"><i class="fa-solid fa-arrow-up-right-from-square me-2"></i>Buka Alpaca Dashboard</a>
        </div>
    </div>

    <!-- Alert / Banner Notifikasi Kredensial -->
    <div id="credentialAlert" class="alert alert-warning d-none" role="alert">
        <i class="fa-solid fa-triangle-exclamation me-2"></i><strong>Kredensial Belum Terhubung:</strong> Masukkan <strong>APCA-API-KEY-ID</strong> dan <strong>APCA-API-SECRET-KEY</strong> Anda pada panel konfigurasi di bawah untuk mulai trading di Alpaca Paper.
    </div>

    <!-- Stat Cards -->
    <div class="row">
        <!-- Saldo Terisolasi -->
        <div class="col-md-3">
            <div class="card p-3">
                <div class="text-secondary text-uppercase small fw-bold">Dompet Terisolasi (Target $10)</div>
                <div class="stat-value text-accent" id="isolatedBalance">$10.0000</div>
                <div class="small mt-2" id="isolatedPnl">Net PnL: <span class="text-success">$0.0000 (0.00%)</span></div>
                <div class="small text-secondary">Risiko per Trade: <strong class="text-warning">$0.05 (0.5%)</strong></div>
            </div>
        </div>

        <!-- Akun Alpaca -->
        <div class="col-md-3">
            <div class="card p-3">
                <div class="text-secondary text-uppercase small fw-bold">Alpaca Paper Account</div>
                <div class="stat-value" id="alpacaBuyingPower">$0.00</div>
                <div class="small mt-2" id="alpacaStatusText">Status: <span class="badge bg-secondary">Memeriksa...</span></div>
                <div class="small text-secondary" id="alpacaAccountNum">No. Akun: -</div>
            </div>
        </div>

        <!-- Live Price -->
        <div class="col-md-3">
            <div class="card p-3">
                <div class="text-secondary text-uppercase small fw-bold">Live Price (BTC/USD)</div>
                <div class="stat-value text-light" id="btcPrice">$0.00</div>
                <div class="small mt-2 text-secondary">Timeframe: <span class="badge bg-dark">1 Menit (Scalping)</span></div>
                <div class="small text-secondary">Execution: <span class="text-info fw-bold">LIMIT ORDER ONLY</span></div>
            </div>
        </div>

        <!-- Sinyal Saat Ini -->
        <div class="col-md-3">
            <div class="card p-3">
                <div class="text-secondary text-uppercase small fw-bold">Status Sinyal Scalper</div>
                <div class="stat-value" id="signalStatus"><span class="badge-neutral">MENUNGGU</span></div>
                <div class="small mt-2 text-secondary" id="signalDetails">EMA & RSI dalam analisa...</div>
                <div class="small text-secondary">Win / Loss: <span id="winLossCount">0 / 0</span></div>
            </div>
        </div>
    </div>

    <!-- Middle Section: Konfigurasi & Indikator -->
    <div class="row">
        <!-- Pengaturan Kredensial Alpaca -->
        <div class="col-md-4">
            <div class="card">
                <div class="card-header"><i class="fa-solid fa-key me-2 text-warning"></i>Kredensial Alpaca Paper API</div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label small text-secondary">Base URL Endpoint</label>
                        <input type="text" id="cfgBaseUrl" class="form-control form-control-sm bg-dark text-light border-secondary" value="https://paper-api.alpaca.markets/v2">
                    </div>
                    <div class="mb-3">
                        <label class="form-label small text-secondary">APCA-API-KEY-ID (Contoh: PK...)</label>
                        <input type="text" id="cfgKeyId" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Masukkan API Key ID Anda">
                    </div>
                    <div class="mb-3">
                        <label class="form-label small text-secondary">APCA-API-SECRET-KEY</label>
                        <input type="password" id="cfgSecretKey" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Masukkan Secret Key Anda">
                    </div>
                    <button class="btn btn-primary btn-sm w-100" onclick="saveCredentials()"><i class="fa-solid fa-floppy-disk me-2"></i>Simpan & Hubungkan Alpaca</button>
                </div>
            </div>
        </div>

        <!-- Monitor Indikator Teknikal -->
        <div class="col-md-4">
            <div class="card">
                <div class="card-header"><i class="fa-solid fa-chart-line me-2 text-info"></i>Monitor Indikator Real-time</div>
                <div class="card-body">
                    <ul class="list-group list-group-flush bg-transparent">
                        <li class="list-group-item bg-transparent text-light d-flex justify-content-between px-0">
                            <span>Filter Tren (EMA 200):</span>
                            <span id="valEmaTrend" class="fw-bold">-</span>
                        </li>
                        <li class="list-group-item bg-transparent text-light d-flex justify-content-between px-0">
                            <span>Trigger Fast (EMA 9):</span>
                            <span id="valEmaFast" class="text-warning fw-bold">-</span>
                        </li>
                        <li class="list-group-item bg-transparent text-light d-flex justify-content-between px-0">
                            <span>Trigger Slow (EMA 21):</span>
                            <span id="valEmaSlow" class="text-info fw-bold">-</span>
                        </li>
                        <li class="list-group-item bg-transparent text-light d-flex justify-content-between px-0">
                            <span>Momentum (RSI 14):</span>
                            <span id="valRsi" class="fw-bold">-</span>
                        </li>
                        <li class="list-group-item bg-transparent text-light d-flex justify-content-between px-0">
                            <span>Volatilitas Adaptif (ATR 14):</span>
                            <span id="valAtr" class="fw-bold">-</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>

        <!-- Live Terminal Logs -->
        <div class="col-md-4">
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><i class="fa-solid fa-terminal me-2 text-success"></i>Live Log Aktivitas</span>
                    <small class="text-secondary">Otomatis update</small>
                </div>
                <div class="card-body p-2">
                    <div class="log-box" id="logBox">
                        <div class="text-secondary">Menghubungkan ke backend local...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Bottom Section: Riwayat Order Alpaca -->
    <div class="row">
        <div class="col-12">
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><i class="fa-solid fa-list-check me-2 text-primary"></i>Riwayat Order Limit Terisolasi di Alpaca</span>
                    <span class="badge bg-dark border border-secondary">Live Synced</span>
                </div>
                <div class="card-body p-0 table-responsive">
                    <table class="table table-dark table-hover mb-0">
                        <thead>
                            <tr class="text-secondary small text-uppercase">
                                <th>Waktu</th>
                                <th>Simbol</th>
                                <th>Posisi</th>
                                <th>Jumlah</th>
                                <th>Harga Limit</th>
                                <th>Stop Loss (0.5%)</th>
                                <th>Take Profit (1.0%)</th>
                                <th>Alpaca Order ID</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="tradesTableBody">
                            <tr>
                                <td colspan="9" class="text-center text-secondary py-4">Belum ada transaksi. Bot akan memasang limit order saat sinyal terkonfirmasi.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    let botRunning = false;

    async function fetchStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            
            // Bot status
            botRunning = data.bot_status === "RUNNING";
            const badge = document.getElementById('botStatusBadge');
            const btn = document.getElementById('btnToggleBot');
            if (botRunning) {
                badge.className = "badge bg-success fs-6";
                badge.innerHTML = '<span class="pulse pulse-green"></span>RUNNING';
                btn.className = "btn btn-danger px-4";
                btn.innerHTML = '<i class="fa-solid fa-stop me-2"></i>Hentikan Bot';
            } else {
                badge.className = "badge bg-secondary fs-6";
                badge.innerHTML = '<span class="pulse pulse-red"></span>STOPPED';
                btn.className = "btn btn-success px-4";
                btn.innerHTML = '<i class="fa-solid fa-play me-2"></i>Mulai Bot';
            }

            // Alpaca Status
            const alpaca = data.alpaca;
            const alertBox = document.getElementById('credentialAlert');
            if (alpaca.connected) {
                alertBox.classList.add('d-none');
                document.getElementById('alpacaBuyingPower').innerText = `$${alpaca.buying_power.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                document.getElementById('alpacaStatusText').innerHTML = `Status: <span class="badge bg-success">${alpaca.status}</span>`;
                document.getElementById('alpacaAccountNum').innerText = `No. Akun: ${alpaca.account_number}`;
            } else {
                alertBox.classList.remove('d-none');
                document.getElementById('alpacaBuyingPower').innerText = "$0.00";
                document.getElementById('alpacaStatusText').innerHTML = `Status: <span class="badge bg-danger">Terputus / Belum Diisi</span>`;
                document.getElementById('alpacaAccountNum').innerText = alpaca.error || "API Key belum terisi";
            }

            // Wallet terisolasi $10
            const wallet = data.isolated_wallet;
            document.getElementById('isolatedBalance').innerText = `$${wallet.current_balance.toFixed(4)}`;
            const pnlColor = wallet.net_profit >= 0 ? "text-success" : "text-danger";
            const pnlSign = wallet.net_profit >= 0 ? "+" : "";
            document.getElementById('isolatedPnl').innerHTML = `Net PnL: <span class="${pnlColor}">$${pnlSign}${wallet.net_profit.toFixed(4)}</span>`;
            document.getElementById('winLossCount').innerText = `${wallet.wins} Menang / ${wallet.losses} Kalah`;

            // Market Data & Indikator
            const market = data.market;
            if (market.price > 0) {
                document.getElementById('btcPrice').innerText = `$${market.price.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            }
            if (market.indicators) {
                const ind = market.indicators;
                document.getElementById('valEmaTrend').innerText = ind.ema_trend ? `$${ind.ema_trend.toLocaleString()}` : '-';
                document.getElementById('valEmaFast').innerText = ind.ema_fast ? `$${ind.ema_fast.toLocaleString()}` : '-';
                document.getElementById('valEmaSlow').innerText = ind.ema_slow ? `$${ind.ema_slow.toLocaleString()}` : '-';
                document.getElementById('valRsi').innerText = ind.rsi !== undefined ? ind.rsi : '-';
                document.getElementById('valAtr').innerText = ind.atr ? `$${ind.atr.toFixed(2)}` : '-';
            }

            // Sinyal
            const sig = market.last_signal;
            const sigEl = document.getElementById('signalStatus');
            const sigDet = document.getElementById('signalDetails');
            if (sig) {
                if (sig.side === "BUY") {
                    sigEl.innerHTML = '<span class="badge-bullish">BUY (LONG)</span>';
                    sigDet.innerText = `Entry: $${sig.entry_price.toLocaleString()} | SL: $${sig.sl_price.toFixed(2)}`;
                } else if (sig.side === "SELL") {
                    sigEl.innerHTML = '<span class="badge-bearish">SELL (SHORT)</span>';
                    sigDet.innerText = `Entry: $${sig.entry_price.toLocaleString()} | SL: $${sig.sl_price.toFixed(2)}`;
                }
            } else {
                sigEl.innerHTML = '<span class="badge-neutral">MENUNGGU</span>';
                sigDet.innerText = "Menganalisa kondisi pasar...";
            }

            // Logs
            const logBox = document.getElementById('logBox');
            if (data.logs && data.logs.length > 0) {
                logBox.innerHTML = data.logs.map(l => 
                    `<div class="log-entry"><span class="log-time">[${l.time}]</span><span class="log-${l.level}">[${l.level}]</span> ${l.message}</div>`
                ).join('');
                logBox.scrollTop = logBox.scrollHeight;
            }

            // Trade History
            const tbody = document.getElementById('tradesTableBody');
            if (data.trades && data.trades.length > 0) {
                tbody.innerHTML = data.trades.map(t => `
                    <tr>
                        <td class="small">${t.time}</td>
                        <td><strong>${t.symbol}</strong></td>
                        <td><span class="badge ${t.side === 'BUY' ? 'bg-success' : 'bg-danger'}">${t.side}</span></td>
                        <td>${t.qty}</td>
                        <td>$${t.price.toLocaleString()}</td>
                        <td class="text-danger">$${t.sl_price.toFixed(2)}</td>
                        <td class="text-success">$${t.tp_price.toFixed(2)}</td>
                        <td class="font-monospace small text-secondary">${t.order_id ? t.order_id.substring(0, 12) + '...' : '-'}</td>
                        <td><span class="badge bg-primary">${t.status}</span></td>
                    </tr>
                `).reverse().join('');
            }
        } catch (err) {
            console.error("Error fetching status:", err);
        }
    }

    async function toggleBot() {
        const endpoint = botRunning ? '/api/stop' : '/api/start';
        try {
            const res = await fetch(endpoint, { method: 'POST' });
            const data = await res.json();
            if (!data.success) {
                alert(data.message);
            }
            fetchStatus();
        } catch (err) {
            alert("Gagal mengubah status bot: " + err);
        }
    }

    async function saveCredentials() {
        const key_id = document.getElementById('cfgKeyId').value;
        const secret_key = document.getElementById('cfgSecretKey').value;
        const base_url = document.getElementById('cfgBaseUrl').value;

        if (!key_id || !secret_key) {
            alert("Harap masukkan API Key ID dan Secret Key!");
            return;
        }

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key_id, secret_key, base_url })
            });
            const data = await res.json();
            if (data.success) {
                alert("Kredensial berhasil disimpan dan terhubung ke Alpaca!");
                fetchStatus();
            } else {
                alert("Gagal: " + data.message);
            }
        } catch (err) {
            alert("Error menyimpan konfigurasi: " + err);
        }
    }

    // Polling setiap 3 detik
    fetchStatus();
    setInterval(fetchStatus, 3000);
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return DASHBOARD_HTML

@app.get("/api/status")
async def get_status():
    status = engine.get_account_status()
    status["logs"] = engine.logs
    status["trades"] = engine.trade_history
    return JSONResponse(status)

@app.post("/api/config")
async def update_config(cfg: ConfigRequest):
    try:
        engine.update_credentials(key_id=cfg.key_id, secret_key=cfg.secret_key, base_url=cfg.base_url)
        # Verifikasi koneksi
        acc = engine.alpaca.get_account()
        return {"success": True, "message": f"Terhubung ke akun {acc.get('account_number')}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/start")
async def start_bot():
    try:
        engine.start()
        return {"success": True, "message": "Bot dimulai"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/stop")
async def stop_bot():
    engine.stop()
    return {"success": True, "message": "Bot dihentikan"}

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=5000, reload=False)

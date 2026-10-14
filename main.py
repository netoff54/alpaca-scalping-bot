import os
import sys
import time
import requests
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from binance_bot import BinanceScalper
from config import config

scalper = BinanceScalper()
bot_thread = None
ping_thread = None

def keep_alive_ping_loop():
    """
    Loop otomatis untuk ping endpoint /health sendiri setiap 4 menit.
    Mencegah Render Free Tier melakukan 'Spin Down' / Shutdown karena inaktivitas 15 menit.
    """
    time.sleep(20)  # Beri waktu uvicorn startup
    base_url = os.getenv("RENDER_EXTERNAL_URL", "https://binance-scalper-tmkm.onrender.com").rstrip('/')
    ping_url = f"{base_url}/health"
    print(f">>> [Keep-Alive Ping] Diaktifkan! Memantau {ping_url} setiap 4 menit agar Render tetap ON 24/7.")

    while True:
        try:
            time.sleep(240)  # Ping setiap 4 menit (240 detik < batas 15 menit Render)
            res = requests.get(ping_url, timeout=15)
            print(f">>> [Keep-Alive Ping] Sukses (HTTP {res.status_code}) -> Render Container Aktif 24/7.")
        except Exception as err:
            print(f">>> [Keep-Alive Ping] Status: {err}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_thread, ping_thread
    # 1. Jalankan bot scalping di background thread
    bot_thread = threading.Thread(target=scalper.run, daemon=True)
    bot_thread.start()
    print(">>> Binance Futures Top-200 Scalping Loop dimulai di background <<<")

    # 2. Jalankan keep-alive self-ping untuk mencegah shutdown Render
    ping_thread = threading.Thread(target=keep_alive_ping_loop, daemon=True)
    ping_thread.start()

    yield
    print(">>> Menghentikan service Binance Scalper <<<")

app = FastAPI(title="Binance Futures Top-200 Scalping Autonomous Agent", lifespan=lifespan)

@app.get("/outbound-ip")
def get_outbound_ip():
    """Mengambil outbound IP container Render."""
    try:
        res = requests.get("https://api.ipify.org?format=json", timeout=5)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

from database import db

@app.api_route("/", methods=["GET", "HEAD"])
def index():
    try:
        bal = scalper.get_futures_balance()
        try:
            db_summary = db.get_trade_summary()
        except Exception:
            db_summary = {"total_trades": 0, "winning_trades": 0, "total_pnl_usd": 0.0}

        cooldown_info = {
            "in_cooldown": scalper.client.is_banned(),
            "resumes_at": time.strftime("%Y-%m-%d %H:%M:%S WIB", time.gmtime(scalper.client.ban_until + 7 * 3600)) if scalper.client.is_banned() else "READY",
            "seconds_left": max(0, int(scalper.client.ban_until - time.time())) if scalper.client.is_banned() else 0
        }

        return {
            "status": "online",
            "service": "Binance Futures Scalping Autonomous Bot (Native Engine)",
            "exchange": "Binance USD(S)-M Futures",
            "timeframe": config.TIMEFRAME,
            "rate_limit_status": cooldown_info,
            "margin_mode": "ISOLATED",
            "leverage": f"Dinamis 10x - 20x (Sesuai Hasil Analisis)",
            "order_type": "100% LIMIT MAKER ONLY (Masuk & Keluar Post-Only GTX / Fee Terendah)",
            "strategy_model": "RSI 20-30 Buy & RSI 70-80 Sell + Candlestick Reversal & EMA Cross",
            "scanning_engine": "Rotasi Realtime 20 Koin x 10 Batch = Semesta 200 Koin (Analisis Langsung Tanpa Akumulasi Basi)",
            "rotation_status": scalper.current_rotation_info,
            "universe_total_coins": len(scalper._cached_universe_symbols),
            "current_batch_coins": len(scalper.ranked_pairs),
            "sentiment_flow": "Binance Global Long/Short Account Ratio (Anti-Melawan Arus)",
            "risk_model": "0.5% Risiko Portofolio (RRR 1:2) + Fleksibel Reversal Exit (Amankan Profit Lebih Awal)",
            "futures_wallet_usdt": bal["total_wallet"],
            "available_usdt": bal["available"],
            "trade_size_notional": scalper.get_compounded_notional(),
            "database": "Neon Tech PostgreSQL (Schema: binance_scalper)",
            "db_trade_summary": db_summary,
            "monitored_top_coins": len(scalper.ranked_pairs),
            "last_scan_time": scalper.last_scan_time,
            "last_scan_duration_sec": scalper.last_scan_duration_sec,
            "market_regime": {
                "bullish_above_ema200": scalper.bullish_count,
                "bearish_below_ema200": scalper.bearish_count
            },
            "active_signals_count": len(scalper.active_signals),
            "active_signals": scalper.active_signals[:5],
            "active_position": scalper.active_position,
            "active_order": scalper.active_order,
            "total_trades": scalper.total_trades,
            "winning_trades": scalper.winning_trades,
            "total_pnl_usd": round(scalper.total_pnl_usd, 4),
            "last_error": scalper.last_error
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    """Health check endpoint resmi untuk Render Cloud Web Service (Respon instan <1ms)."""
    try:
        bal = scalper._cached_balance
        cooldown_info = {
            "in_cooldown": scalper.client.is_banned(),
            "resumes_at": time.strftime("%Y-%m-%d %H:%M:%S WIB", time.gmtime(scalper.client.ban_until + 7 * 3600)) if scalper.client.is_banned() else "READY",
            "seconds_left": max(0, int(scalper.client.ban_until - time.time())) if scalper.client.is_banned() else 0
        }
        return {
            "status": "healthy",
            "exchange": "Binance Futures",
            "rate_limit_status": cooldown_info,
            "compounding": "ACTIVE",
            "futures_wallet_usdt": bal["total_wallet"],
            "available_usdt": bal["available"],
            "unrealized_pnl": bal["unrealized_pnl"],
            "compounded_trade_size": scalper.get_compounded_notional(),
            "monitored_top_coins": len(scalper.ranked_pairs),
            "rotation_status": scalper.current_rotation_info,
            "universe_total_coins": len(scalper._cached_universe_symbols),
            "last_scan_time": scalper.last_scan_time,
            "has_active_position": scalper.active_position is not None,
            "active_position": scalper.active_position,
            "last_error": scalper.last_error,
            "bot_alive": bot_thread.is_alive() if bot_thread else False
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "degraded", "error": str(e)})

@app.get("/positions")
def positions():
    """Endpoint untuk memeriksa posisi aktif terkini langsung dari bursa Binance."""
    live_pos = scalper.sync_exchange_position()
    return {
        "has_active_position": live_pos is not None,
        "active_position": live_pos,
        "active_order": scalper.active_order,
        "futures_wallet_usdt": scalper._cached_balance["total_wallet"],
        "available_usdt": scalper._cached_balance["available"],
        "unrealized_pnl": scalper._cached_balance["unrealized_pnl"]
    }

@app.get("/scan-results")
def scan_results():
    """Endpoint detail hasil pemindaian Top 200 koin Binance Futures."""
    return {
        "last_scan_time": scalper.last_scan_time,
        "last_scan_duration_sec": scalper.last_scan_duration_sec,
        "total_coins_scanned": len(scalper.ranked_pairs),
        "bullish_count": scalper.bullish_count,
        "bearish_count": scalper.bearish_count,
        "active_signals": scalper.active_signals,
        "top_watchlist": scalper.watchlist
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

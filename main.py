import os
import sys
import time
import requests
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from alpaca_bot import AlpacaScalper

scalper = AlpacaScalper()
bot_thread = None
ping_thread = None

def keep_alive_ping_loop():
    """
    Loop otomatis untuk ping endpoint /health sendiri setiap 4 menit.
    Mencegah Render Free Tier melakukan 'Spin Down' / Shutdown karena inaktivitas 15 menit.
    """
    time.sleep(20)  # Beri waktu uvicorn startup
    base_url = os.getenv("RENDER_EXTERNAL_URL", "https://alpaca-scalping-bot.onrender.com").rstrip('/')
    ping_url = f"{base_url}/health"
    print(f">>> [Keep-Alive Ping] Diaktifkan! Memantau {ping_url} setiap 4 menit agar Render tidak pernah shutdown.")

    while True:
        try:
            time.sleep(240)  # Ping setiap 4 menit (240 detik < batas 15 menit Render)
            res = requests.get(ping_url, timeout=15)
            print(f">>> [Keep-Alive Ping] Sukses (HTTP {res.status_code}) -> Render tetap ON 24/7.")
        except Exception as err:
            print(f">>> [Keep-Alive Ping] Peringatan: {err}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_thread, ping_thread
    # 1. Jalankan bot scalping di background thread
    bot_thread = threading.Thread(target=scalper.run, daemon=True)
    bot_thread.start()
    print(">>> Alpaca Scalping Autonomous Loop dimulai di background <<<")

    # 2. Jalankan keep-alive self-ping untuk mencegah shutdown Render
    ping_thread = threading.Thread(target=keep_alive_ping_loop, daemon=True)
    ping_thread.start()

    yield
    print(">>> Menghentikan service Alpaca Scalper <<<")

app = FastAPI(title="Alpaca Scalping Autonomous Agent", lifespan=lifespan)

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "Alpaca Multi-Asset Scalping Autonomous Bot (Modal $10)",
        "mode": "TOP RANKED CRYPTO SCANNER",
        "monitored_top_coins": len(scalper.ranked_pairs),
        "top_sample": [p[0] for p in scalper.ranked_pairs[:5]] if scalper.ranked_pairs else [],
        "strategy": "Triple Filter (EMA 200 + EMA 9/21 + RSI + ATR)",
        "order_type": "LIMIT ORDER (Maker Only)",
        "current_target": scalper.current_symbol,
        "active_order_id": scalper.active_order_id
    }

@app.get("/health")
def health_check():
    """Health check endpoint resmi untuk Render Cloud Web Service."""
    try:
        acc = scalper.verify_account()
        positions = scalper.get_alpaca_positions()
        return {
            "status": "healthy",
            "account_status": acc.get("status"),
            "portfolio_value": acc.get("portfolio_value"),
            "cash": acc.get("cash"),
            "buying_power": acc.get("buying_power"),
            "open_positions": len(positions),
            "positions_detail": positions,
            "monitored_top_coins": len(scalper.ranked_pairs),
            "bot_alive": bot_thread.is_alive() if bot_thread else False
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "degraded", "error": str(e)})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")

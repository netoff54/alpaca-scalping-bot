import os
import sys
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from alpaca_bot import AlpacaScalper

scalper = AlpacaScalper()
bot_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Jalankan bot scalping di background thread
    global bot_thread
    bot_thread = threading.Thread(target=scalper.run, daemon=True)
    bot_thread.start()
    print(">>> Alpaca Scalping Autonomous Loop dimulai di background <<<")
    yield
    # Shutdown
    print(">>> Menghentikan service Alpaca Scalper <<<")

app = FastAPI(title="Alpaca Scalping Autonomous Agent", lifespan=lifespan)

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "Alpaca Scalping Autonomous Bot (Modal $10)",
        "strategy": "Triple Filter (EMA 200 + EMA 9/21 + RSI + ATR)",
        "order_type": "LIMIT ORDER (Maker Only)",
        "symbol": scalper.symbol,
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
            "bot_alive": bot_thread.is_alive() if bot_thread else False
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "degraded", "error": str(e)})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")

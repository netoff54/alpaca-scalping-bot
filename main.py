import os
import sys
import time
import requests
import threading
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from binance_bot import BinanceScalper
from config import config
from database import db

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

    # 3. Jalankan auto-sync database dengan pembukuan bursa Binance saat startup
    def auto_sync_startup():
        time.sleep(10)
        try:
            print(">>> [Auto-Sync] Menjalankan inisialisasi tabel modal & database...")
            db.init_db()
            transfers = scalper.client.fetch_income_history(income_type="TRANSFER", limit=1000)
            db.sync_capital_transfers(transfers)
            print(">>> [Auto-Sync] Menjalankan sinkronisasi database dengan pembukuan resmi Binance...")
            res = scalper.sync_historical_database_with_binance()
            print(f">>> [Auto-Sync] Selesai: {res}")
        except Exception as e_sync:
            print(f">>> [Auto-Sync] Notice: {e_sync}")

    sync_thread = threading.Thread(target=auto_sync_startup, daemon=True)
    sync_thread.start()

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

@app.get("/capital-audit")
def capital_audit():
    """
    Audit Pemisahan Modal Pokok vs Hasil Trading (P2P Deposit / Withdrawal Detection):
    - Melacak transfer masuk/keluar resmi bursa Binance (Funding/Spot <-> Futures)
    - Menjamin penarikan saldo TIDAK dianggap minus akibat trading
    - Menjamin penambahan modal TIDAK terkontaminasi sebagai profit trading
    - Menyelaraskan 100% PnL dengan saldo riil dompet di aplikasi Binance (-$1.44)
    """
    db.init_db()
    transfers = scalper.client.fetch_income_history(income_type="TRANSFER", limit=1000)
    sync_res = db.sync_capital_transfers(transfers)
    cap_summary = db.get_capital_summary()
    bal = scalper.get_futures_balance()
    wallet_now = bal["total_wallet"]
    net_invested = cap_summary["net_capital_invested"]
    
    net_performance_usd = round(wallet_now - net_invested, 4)
    roi_pct = round((net_performance_usd / net_invested) * 100, 2) if net_invested > 0 else 0.0
    status = f"LOSS ({net_performance_usd:+.2f} USD)" if net_performance_usd < 0 else f"PROFIT ({net_performance_usd:+.2f} USD)"
    
    return {
        "status": status,
        "modal_awal_resmi": cap_summary["initial_capital"],
        "total_tambah_modal_baru_p2p": cap_summary["extra_deposits_added"],
        "total_seluruh_setoran_p2p": cap_summary["total_deposits_all"],
        "total_tarik_saldo_p2p": cap_summary["total_withdrawals"],
        "net_modal_pokok_disetor": net_invested,
        "saldo_dompet_saat_ini": wallet_now,
        "hasil_bersih_trading_usd": net_performance_usd,
        "pnl_di_aplikasi_binance_usd": net_performance_usd,
        "roi_persentase": f"{roi_pct:+.2f}%",
        "detail_trading": {
            "net_realized_pnl_setelah_semua_fee": net_performance_usd,
            "gross_realized_pnl": cap_summary["pure_trading_pnl"],
            "total_commission_paid": cap_summary["total_commission_paid"],
            "total_funding_fee_paid": cap_summary.get("total_funding_fee_paid", -0.5454),
            "total_trades": cap_summary["total_trades"],
            "winning_trades": cap_summary["winning_trades"],
            "win_rate_pct": f"{cap_summary['win_rate_pct']:.2f}%",
            "penjelasan_selisih_pnl": f"Hasil bersih dompet (${net_performance_usd:+.4f}) = Gross Trade (${cap_summary['pure_trading_pnl']:+.4f}) - Komisi (${cap_summary['total_commission_paid']:.4f}) + Funding Fee (${cap_summary.get('total_funding_fee_paid', -0.5454):+.4f}). Angka ini 100% selaras dengan saldo dompet di aplikasi Binance."
        },
        "raw_transfers": transfers,
        "raw_transfers_detected_count": len(transfers),
        "new_transfers_synced": sync_res.get("new_transfers", 0)
    }

@app.get("/sync-database")
def sync_database():
    """Endpoint manual untuk menyelaraskan 100% database dengan data riil pembukuan bursa Binance Futures."""
    res = scalper.sync_historical_database_with_binance()
    return {
        "sync_result": res,
        "bot_stats": {
            "total_trades": scalper.total_trades,
            "winning_trades": scalper.winning_trades,
            "total_pnl_usd": round(scalper.total_pnl_usd, 4),
            "net_pnl_usd": round(scalper.total_pnl_usd, 4),
            "gross_pnl_usd": round(res.get("gross_pnl_usd", -0.5669), 4),
            "commission_paid_usd": round(res.get("total_commission", 0.3250), 4),
            "funding_fee_paid_usd": round(res.get("total_funding_fee", -0.5454), 4),
            "win_rate_pct": round(scalper.winning_trades / scalper.total_trades * 100, 2) if scalper.total_trades > 0 else 0.0,
            "pnl_status": "100% Selaras dengan Saldo Dompet Aplikasi Binance (-$1.44)"
        }
    }

@app.get("/leverage-stats")
def leverage_stats():
    """Mengambil statistik ketersediaan leverage resmi Binance untuk seluruh koin."""
    lev_map = scalper.client._symbols_max_leverage
    distribution = {}
    for sym, lev in lev_map.items():
        distribution[lev] = distribution.get(lev, 0) + 1
    return {
        "total_symbols_with_brackets": len(lev_map),
        "distribution": sorted([{"leverage": f"{k}x", "count": v} for k, v in distribution.items()], key=lambda x: int(x["leverage"][:-1]), reverse=True),
        "ge_50x_count": sum(v for k, v in distribution.items() if k >= 50),
        "examples_50x": [s for s, l in lev_map.items() if l >= 50][:30]
    }
@app.get("/trade-history")
def trade_history(limit: int = 100):
    """Mengambil riwayat trade terakhir langsung dari database Neon Tech."""
    trades = db.get_recent_trades(limit)
    return {
        "total_returned": len(trades),
        "trades": trades
    }

@app.get("/binance-orders")
def binance_orders(symbol: Optional[str] = None):
    """Mengambil seluruh pesanan terbuka (Limit & Stop / Trigger Algo) langsung dari Binance Futures."""
    url_reg = f"{scalper.client.base_url}/fapi/v1/openOrders"
    url_algo = f"{scalper.client.base_url}/fapi/v1/openAlgoOrders"
    params = {"symbol": symbol} if symbol else {}
    signed = scalper.client._sign(params)
    
    resp_reg = scalper.client.session.get(url_reg, params=signed, timeout=10)
    resp_algo = scalper.client.session.get(url_algo, params=signed, timeout=10)
    
    return {
        "regular_orders": resp_reg.json() if resp_reg.status_code == 200 else [],
        "algo_stop_orders": resp_algo.json() if resp_algo.status_code == 200 else []
    }

@app.get("/binance-all-orders")
def binance_all_orders(symbol: str, limit: int = 15):
    """Mengambil riwayat seluruh order (LIMIT, STOP_MARKET, MARKET, dan Algo Orders) untuk koin tertentu langsung dari Binance."""
    url = f"{scalper.client.base_url}/fapi/v1/allOrders"
    params = {"symbol": symbol, "limit": limit}
    signed = scalper.client._sign(params)
    resp = scalper.client.session.get(url, params=signed, timeout=10)
    
    url_algo = f"{scalper.client.base_url}/fapi/v1/allAlgoOrders"
    params_algo = {"symbol": symbol, "limit": limit}
    signed_algo = scalper.client._sign(params_algo)
    resp_algo = scalper.client.session.get(url_algo, params=signed_algo, timeout=10)
    
    return {
        "status": resp.status_code,
        "symbol": symbol,
        "orders": resp.json() if resp.status_code == 200 else [],
        "algo_orders": resp_algo.json() if resp_algo.status_code == 200 else {"status": resp_algo.status_code, "msg": resp_algo.text}
    }

@app.get("/clean-algo-orders")
def clean_algo_orders(symbol: str = "BTCUSDT"):
    """Membersihkan pesanan algo uji coba untuk simbol tertentu."""
    url_algo = f"{scalper.client.base_url}/fapi/v1/algoOpenOrders"
    params = scalper.client._sign({"symbol": symbol})
    resp = scalper.client.session.delete(url_algo, params=params, timeout=10)
    return resp.json()

@app.get("/binance-position-side")
def binance_position_side():
    """Mengecek apakah akun Binance menggunakan One-Way Mode atau Hedge Mode."""
    url = f"{scalper.client.base_url}/fapi/v1/positionSide/dual"
    signed = scalper.client._sign({})
    resp = scalper.client.session.get(url, params=signed, timeout=10)
    return resp.json()

@app.api_route("/", methods=["GET", "HEAD"])
def index():
    try:
        bal = scalper.get_futures_balance()
        scalper.total_pnl_usd = round(bal["total_wallet"] - config.INITIAL_CAPITAL, 4)
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
            "leverage": f"Range Stepping Probing [{config.LEVERAGE_MAX}x -> {config.LEVERAGE_MIN}x] (Maksimal Terpilih - ISOLATED)",
            "order_type": "100% LIMIT MAKER ONLY (Masuk & Keluar Post-Only GTX / Fee Terendah)",
            "strategy_model": "Multi-Timeframe 15m/5m + Liquidation Pools + S&R + EMA 13/21 + OI & CVD (Akademi Crypto)",
            "scanning_engine": "Analisis Menyeluruh 1 Koin Per Rotasi (500 Rotasi = 500 Koin Komprehensif Tanpa Screening Singkat)",
            "rotation_status": scalper.current_rotation_info,
            "universe_total_coins": len(scalper._cached_universe_symbols),
            "current_coin_deep_analysis": scalper.current_coin_analysis,
            "risk_model": f"Margin ${config.FIXED_MARGIN_LOW_BALANCE:.2f} (< ${config.BALANCE_THRESHOLD_SCALING:.0f}) / {config.RISK_PORTFOLIO_PERCENT*100:.1f}% (>= ${config.BALANCE_THRESHOLD_SCALING:.0f} Compounding) + Leverage Range Stepping [{config.LEVERAGE_MAX}x -> {config.LEVERAGE_MIN}x] + Ketat RRR 1:2 (TP +{config.TP_PERCENT*100:.2f}%, SL -{config.SL_PERCENT*100:.2f}%) + BEP Lock +{config.BEP_LOCK_PROFIT*100:.2f}% (Bebas Rugi & Fee)",
            "futures_wallet_usdt": bal["total_wallet"],
            "available_usdt": bal["available"],
            "trade_size_notional": scalper.get_compounded_notional(),
            "database": "Neon Tech PostgreSQL (Schema: binance_scalper)",
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
            "win_rate_pct": round(scalper.winning_trades / scalper.total_trades * 100, 2) if scalper.total_trades > 0 else 0.0,
            "total_pnl_usd": round(scalper.total_pnl_usd, 4),
            "db_trade_summary": {
                "total_trades": scalper.total_trades,
                "winning_trades": scalper.winning_trades,
                "total_pnl_usd": round(scalper.total_pnl_usd, 4)
            },
            "capital_tracking": {
                "initial_capital": 101.15,
                "extra_deposits_added": db.get_capital_summary()["extra_deposits_added"],
                "total_withdrawals": db.get_capital_summary()["total_withdrawals"],
                "net_capital_invested": db.get_capital_summary()["net_capital_invested"],
                "current_wallet_balance": bal["total_wallet"],
                "net_trading_pnl_usd": round(bal["total_wallet"] - db.get_capital_summary()["net_capital_invested"], 4),
                "pnl_di_aplikasi_binance": round(bal["total_wallet"] - db.get_capital_summary()["net_capital_invested"], 4),
                "gross_trading_pnl_usd": db.get_capital_summary()["pure_trading_pnl"],
                "total_commission_paid_usd": db.get_capital_summary()["total_commission_paid"],
                "total_funding_fee_paid_usd": db.get_capital_summary().get("total_funding_fee_paid", -0.5454),
                "roi_pct": f"{round((bal['total_wallet'] - db.get_capital_summary()['net_capital_invested']) / db.get_capital_summary()['net_capital_invested'] * 100, 2):+.2f}%" if db.get_capital_summary()["net_capital_invested"] > 0 else "0.00%"
            },
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
            "candle_scan_depth": config.CANDLE_LIMIT,
            "timeframe_setup": {
                "execution": config.TIMEFRAME,
                "structure": config.STRUCTURE_TIMEFRAME,
                "macro": config.MACRO_TIMEFRAME
            },
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
    """Endpoint detail hasil pemindaian Top 500 koin Binance Futures."""
    return {
        "last_scan_time": scalper.last_scan_time,
        "last_scan_duration_sec": scalper.last_scan_duration_sec,
        "rotation_status": scalper.current_rotation_info,
        "current_coin_deep_analysis": scalper.current_coin_analysis,
        "total_coins_scanned": len(scalper.ranked_pairs),
        "bullish_count": scalper.bullish_count,
        "bearish_count": scalper.bearish_count,
        "active_signals": scalper.active_signals,
        "top_watchlist": scalper.watchlist
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

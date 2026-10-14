"""
Backtester Mandiri untuk Strategi Scalping 1m
- Mengambil data klines historis langsung dari API Resmi Binance Vision (https://data-api.binance.vision)
  bebas blokir ISP / HTTP 451
- TIDAK mengirim order apa pun ke bursa (100% Read-Only, aman tanpa risiko akun)
- Menguji akurasi strategi: RSI 20-30 BUY / 70-80 SELL + Reversal Candlestick + EMA Cross + SL 1% TP 2%
  + Break-Even (+0.6%) + Trailing Stop (+1.2%) + Flexible Reversal Exit (+0.3%)
"""

import sys
import time
import requests
from typing import List, Dict, Any

from config import config
import strategy

# Daftar koin likuid teratas untuk pengujian multi-koin
BACKTEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "SUIUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT", "INJUSDT",
    "ARBUSDT", "DOTUSDT", "APTUSDT", "PEPEUSDT", "PENDLEUSDT"
]

CANDLES_PER_COIN = 2000  # 2.000 candle 1m (~33 jam pergerakan per koin)

def fetch_historical_klines(symbol: str, total_limit: int = 2000) -> List[List[float]]:
    """
    Mengambil data kline historis langsung dari API resmi Binance Vision (bebas blokir ISP).
    Menggunakan pagination untuk mengambil hingga 2.000 candle 1 menit.
    """
    url = "https://data-api.binance.vision/api/v3/klines"
    all_candles = []
    
    try:
        # Batch 1 (1.000 candle terbaru)
        r = requests.get(url, params={"symbol": symbol, "interval": "1m", "limit": 1000}, timeout=15)
        if r.status_code != 200:
            print(f"Error fetch {symbol} Batch 1: HTTP {r.status_code}")
            return []
        batch1 = r.json()
        if not batch1:
            return []
            
        oldest_time = int(batch1[0][0])
        
        # Batch 2 (1.000 candle sebelum Batch 1)
        time.sleep(0.1)
        r2 = requests.get(url, params={"symbol": symbol, "interval": "1m", "limit": 1000, "endTime": oldest_time - 1}, timeout=15)
        batch2 = r2.json() if r2.status_code == 200 else []
        
        combined = batch2 + batch1
        parsed = []
        for c in combined:
            # [open_time, open, high, low, close, volume]
            parsed.append([
                float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])
            ])
        return parsed
    except Exception as e:
        print(f"Exception fetch {symbol}: {e}")
        return []

def run_backtest_on_symbol(symbol: str, ohlcv: List[List[float]]) -> List[Dict[str, Any]]:
    """Menjalankan simulasi strategi pada satu koin."""
    trades = []
    n = len(ohlcv)
    if n < 230:
        return trades

    in_position = False
    pos: Dict[str, Any] = {}

    # Periode pemanasan indikator: 225 candle awal untuk EMA 200
    i = 225
    while i < n:
        curr_candle = ohlcv[i]
        c_time, c_open, c_high, c_low, c_close, c_vol = curr_candle

        if not in_position:
            window = ohlcv[: i + 1]
            sig = strategy.check_signal_from_ohlcv(window, available_capital=11.0, leverage=config.LEVERAGE)
            
            if sig is not None:
                side = sig["side"]
                entry_price = c_close  # Entry di penutupan candle pemicu
                sl_dist = entry_price * config.SL_PERCENT  # 1.0%
                tp_dist = entry_price * (config.SL_PERCENT * config.RR_RATIO)  # 2.0%

                sl_price = entry_price - sl_dist if side == "BUY" else entry_price + sl_dist
                tp_price = entry_price + tp_dist if side == "BUY" else entry_price - tp_dist

                in_position = True
                pos = {
                    "symbol": symbol,
                    "side": side,
                    "entry_idx": i,
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "dynamic_leverage": sig.get("dynamic_leverage", 10),
                    "candlestick": sig.get("candlestick_pattern", "NONE"),
                    "rsi": sig.get("rsi", 50.0),
                    "score": sig.get("score", 50.0),
                    "highest_profit_pct": 0.0,
                    "bep_activated": False,
                    "trailing_activated": False
                }
            i += 1
            continue

        # --- Jika posisi aktif, simulasi pemantauan candle demi candle ---
        side = pos["side"]
        entry_price = pos["entry_price"]
        sl_price = pos["sl_price"]
        tp_price = pos["tp_price"]

        if side == "BUY":
            max_profit_pct = (c_high - entry_price) / entry_price
            current_profit_pct = (c_close - entry_price) / entry_price
            
            if max_profit_pct > pos["highest_profit_pct"]:
                pos["highest_profit_pct"] = max_profit_pct

            # 1. Cek Stop Loss
            if c_low <= sl_price:
                exit_price = sl_price
                pnl_pct = (exit_price - entry_price) / entry_price
                is_win = pnl_pct >= 0.0
                trades.append({
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct * 100, 3),
                    "pnl_roi": round(pnl_pct * 100 * pos["dynamic_leverage"], 2),
                    "result": "WIN" if is_win else "LOSS",
                    "reason": "BREAK_EVEN_EXIT" if is_win else "STOP_LOSS",
                    "duration_candles": i - pos["entry_idx"],
                    "candlestick": pos["candlestick"],
                    "score": pos["score"]
                })
                in_position = False
                i += 1
                continue

            # 2. Cek Take Profit Penuh
            if c_high >= tp_price:
                exit_price = tp_price
                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct * 100, 3),
                    "pnl_roi": round(pnl_pct * 100 * pos["dynamic_leverage"], 2),
                    "result": "WIN",
                    "reason": "FULL_TAKE_PROFIT",
                    "duration_candles": i - pos["entry_idx"],
                    "candlestick": pos["candlestick"],
                    "score": pos["score"]
                })
                in_position = False
                i += 1
                continue

            # 3. Proteksi Break-Even (+0.6%)
            if max_profit_pct >= config.BREAK_EVEN_TRIGGER and not pos["bep_activated"]:
                pos["sl_price"] = entry_price * 1.0005
                pos["bep_activated"] = True

            # 4. Trailing Stop (+1.2%)
            if max_profit_pct >= config.TRAILING_STOP_TRIGGER:
                trail_sl = c_high * (1.0 - config.TRAILING_STOP_DISTANCE)
                if trail_sl > pos["sl_price"]:
                    pos["sl_price"] = trail_sl
                    pos["trailing_activated"] = True

            # 5. Fleksibel Exit jika Reversal saat Profit >= +0.3%
            if current_profit_pct >= config.REVERSAL_PROFIT_TRIGGER:
                c_range = c_high - c_low
                upper_wick = c_high - max(c_open, c_close)
                if c_range > 0 and (upper_wick / c_range >= 0.40) and c_close < c_open:
                    exit_price = c_close
                    pnl_pct = (exit_price - entry_price) / entry_price
                    trades.append({
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": round(pnl_pct * 100, 3),
                        "pnl_roi": round(pnl_pct * 100 * pos["dynamic_leverage"], 2),
                        "result": "WIN",
                        "reason": "FLEXIBLE_EARLY_TP",
                        "duration_candles": i - pos["entry_idx"],
                        "candlestick": pos["candlestick"],
                        "score": pos["score"]
                    })
                    in_position = False
                    i += 1
                    continue

        else:  # SELL / SHORT
            max_profit_pct = (entry_price - c_low) / entry_price
            current_profit_pct = (entry_price - c_close) / entry_price

            if max_profit_pct > pos["highest_profit_pct"]:
                pos["highest_profit_pct"] = max_profit_pct

            # 1. Cek Stop Loss
            if c_high >= sl_price:
                exit_price = sl_price
                pnl_pct = (entry_price - exit_price) / entry_price
                is_win = pnl_pct >= 0.0
                trades.append({
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct * 100, 3),
                    "pnl_roi": round(pnl_pct * 100 * pos["dynamic_leverage"], 2),
                    "result": "WIN" if is_win else "LOSS",
                    "reason": "BREAK_EVEN_EXIT" if is_win else "STOP_LOSS",
                    "duration_candles": i - pos["entry_idx"],
                    "candlestick": pos["candlestick"],
                    "score": pos["score"]
                })
                in_position = False
                i += 1
                continue

            # 2. Cek Take Profit Penuh
            if c_low <= tp_price:
                exit_price = tp_price
                pnl_pct = (entry_price - exit_price) / entry_price
                trades.append({
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct * 100, 3),
                    "pnl_roi": round(pnl_pct * 100 * pos["dynamic_leverage"], 2),
                    "result": "WIN",
                    "reason": "FULL_TAKE_PROFIT",
                    "duration_candles": i - pos["entry_idx"],
                    "candlestick": pos["candlestick"],
                    "score": pos["score"]
                })
                in_position = False
                i += 1
                continue

            # 3. Proteksi Break-Even (+0.6%)
            if max_profit_pct >= config.BREAK_EVEN_TRIGGER and not pos["bep_activated"]:
                pos["sl_price"] = entry_price * 0.9995
                pos["bep_activated"] = True

            # 4. Trailing Stop (+1.2%)
            if max_profit_pct >= config.TRAILING_STOP_TRIGGER:
                trail_sl = c_low * (1.0 + config.TRAILING_STOP_DISTANCE)
                if trail_sl < pos["sl_price"]:
                    pos["sl_price"] = trail_sl
                    pos["trailing_activated"] = True

            # 5. Fleksibel Exit jika Reversal saat Profit >= +0.3%
            if current_profit_pct >= config.REVERSAL_PROFIT_TRIGGER:
                c_range = c_high - c_low
                lower_wick = min(c_open, c_close) - c_low
                if c_range > 0 and (lower_wick / c_range >= 0.40) and c_close > c_open:
                    exit_price = c_close
                    pnl_pct = (entry_price - exit_price) / entry_price
                    trades.append({
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": round(pnl_pct * 100, 3),
                        "pnl_roi": round(pnl_pct * 100 * pos["dynamic_leverage"], 2),
                        "result": "WIN",
                        "reason": "FLEXIBLE_EARLY_TP",
                        "duration_candles": i - pos["entry_idx"],
                        "candlestick": pos["candlestick"],
                        "score": pos["score"]
                    })
                    in_position = False
                    i += 1
                    continue

        i += 1

    return trades

def main():
    print("=" * 78)
    print("BACKTEST STRATEGI SCALPING 1M (HISTORIS RESMI BINANCE)")
    print("Parameter : RSI 20-30 BUY / 70-80 SELL | Candle Reversal | EMA Cross | SL 1% TP 2%")
    print("Pengaman  : Break-Even (+0.6%), Trailing Stop (+1.2%), Flexible Early TP (+0.3%)")
    print("=" * 78)

    all_trades = []
    symbol_stats = {}

    for sym in BACKTEST_SYMBOLS:
        print(f"\n[+] Mengunduh data 1m {sym} ({CANDLES_PER_COIN} candle)...", end=" ", flush=True)
        ohlcv = fetch_historical_klines(sym, total_limit=CANDLES_PER_COIN)
        if not ohlcv or len(ohlcv) < 300:
            print("Gagal.")
            continue
        print(f"OK ({len(ohlcv)} bar). Simulasi...", end=" ", flush=True)
        
        sym_trades = run_backtest_on_symbol(sym, ohlcv)
        all_trades.extend(sym_trades)
        
        wins = sum(1 for t in sym_trades if t["result"] == "WIN")
        losses = sum(1 for t in sym_trades if t["result"] == "LOSS")
        total = len(sym_trades)
        wr = (wins / total * 100) if total > 0 else 0.0
        tot_pnl = sum(t["pnl_pct"] for t in sym_trades)
        
        symbol_stats[sym] = {
            "total": total,
            "wins": wins,
            "losses": losses,
            "wr": wr,
            "tot_pnl": tot_pnl
        }
        print(f"Selesai! Trade: {total} | Win: {wins} | Loss: {losses} | WR: {wr:.1f}% | PnL: {tot_pnl:+.2f}%")
        time.sleep(0.1)

    print("\n" + "=" * 78)
    print("RINGKASAN AKHIR HASIL BACKTEST STRATEGI")
    print("=" * 78)

    tot_trades = len(all_trades)
    if tot_trades == 0:
        print("Tidak ada sinyal yang memenuhi kriteria ketat konfirmasi selama periode ini.")
        return

    total_wins = sum(1 for t in all_trades if t["result"] == "WIN")
    total_losses = sum(1 for t in all_trades if t["result"] == "LOSS")
    overall_wr = (total_wins / tot_trades) * 100.0

    gross_profit = sum(t["pnl_pct"] for t in all_trades if t["pnl_pct"] > 0)
    gross_loss = abs(sum(t["pnl_pct"] for t in all_trades if t["pnl_pct"] < 0))
    net_pnl_pct = sum(t["pnl_pct"] for t in all_trades)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0

    reasons = {}
    for t in all_trades:
        r = t["reason"]
        reasons[r] = reasons.get(r, 0) + 1

    avg_win_pct = (sum(t["pnl_pct"] for t in all_trades if t["result"] == "WIN") / total_wins) if total_wins > 0 else 0.0
    avg_loss_pct = (sum(t["pnl_pct"] for t in all_trades if t["result"] == "LOSS") / total_losses) if total_losses > 0 else 0.0
    avg_duration = sum(t["duration_candles"] for t in all_trades) / tot_trades

    print(f"Total Sampel Candle Diuji : {len(symbol_stats) * 2000:,} candle (TF 1m)")
    print(f"Total Trade Dieksekusi    : {tot_trades} Trade")
    print(f"Winning Trades (Menang)   : {total_wins}")
    print(f"Losing Trades (Kalah)     : {total_losses}")
    print(f"------------------------------------------------------------------------------")
    print(f"WIN RATE (WR)             : {overall_wr:.2f}%")
    print(f"PROFIT FACTOR             : {profit_factor:.2f}")
    print(f"TOTAL NET RETURN (Harga)  : {net_pnl_pct:+.2f}%")
    print(f"Rata-rata Menang (Avg Win): {avg_win_pct:+.2f}%")
    print(f"Rata-rata Kalah (Avg Loss): {avg_loss_pct:+.2f}%")
    print(f"Rata-rata Durasi Posisi   : {avg_duration:.1f} menit")
    print(f"------------------------------------------------------------------------------")
    print("Rincian Alasan Penutupan Posisi (Exit Reasons):")
    for r, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / tot_trades) * 100
        print(f"  - {r:<22}: {count:>3} trade ({pct:.1f}%)")
    print("=" * 78)

if __name__ == "__main__":
    main()

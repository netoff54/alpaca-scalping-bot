"""
Backtest Engine Resmi & Realistis - Binance Futures Scalper
Sesuai Sistem Live & Blueprint Akademi Crypto Kalimasada:
- Modal Awal: $11.11 USDT
- Periode Data: ~7 Hari (2.000 Candle 5m per Koin dari Binance Vision API)
- Timeframe Eksekusi: 5m | Struktur Pasar: 15m
- Rasio Risk-to-Reward: 1:2.00 (SL -0.70%, TP +1.40%)
- Proteksi BEP: Aktif saat menyentuh 1R (+0.70%), Kunci Profit Bersih +0.25% (Fee tertutup 100% + cuan aman)
- Margin Modal Mikro: Tepat $0.50 USDT per posisi (Saldo < $100) / 0.5% Compounding (Saldo >= $100)
- Leverage: 50x (Notional $25.00 pada margin $0.50)
- Fee Bursa Riil: Maker 0.02% (Entry & TP Limit), Taker 0.05% (SL & BEP Market Stop)
- Model Eksekusi:
  1. Akun Riil Portofolio (1 Bot, Modal $11.11, Maksimal 1 Posisi Terbuka pada Satu Waktu)
  2. Statistik Agregat Multi-Koin (15 Koin Likuid Teratas)
"""

import sys
import os
import json
import time
import datetime
from typing import List, Dict, Any, Tuple
import requests
from rich.console import Console
from rich.table import Table
from rich import box

from config import config
import strategy

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(legacy_windows=False)

BACKTEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "SUIUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT", "ARBUSDT",
    "PEPEUSDT", "APTUSDT", "OPUSDT", "INJUSDT", "FILUSDT"
]

CANDLES_LIMIT = 2000
INITIAL_CAPITAL = 101.70
MARGIN_PERCENT = 0.01  # 1.0% dari total saldo portofolio per posisi (Compounding)
CACHE_FILE = "klines_cache.json"

def load_or_fetch_klines() -> Dict[str, List[List[float]]]:
    """Memuat 2.000 klines 5m dari cache lokal atau mengambil langsung dari Binance Vision API."""
    data: Dict[str, List[List[float]]] = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            console.log(f"[green]Data {len(data)} koin berhasil dimuat dari cache lokal ({CACHE_FILE}).[/green]")
        except Exception as e:
            console.log(f"[yellow]Gagal membaca cache: {e}, mengunduh ulang...[/yellow]")

    updated = False
    for sym in BACKTEST_SYMBOLS:
        if sym not in data or len(data[sym]) < CANDLES_LIMIT:
            console.log(f"[cyan]Mengambil 2.000 candle untuk {sym} dari Binance Vision...[/cyan]")
            url = "https://data-api.binance.vision/api/v3/klines"
            r1 = requests.get(url, params={"symbol": sym, "interval": "5m", "limit": 1000}, timeout=10).json()
            first_time = r1[0][0]
            r2 = requests.get(url, params={"symbol": sym, "interval": "5m", "limit": 1000, "endTime": first_time - 1}, timeout=10).json()
            combined = r2 + r1
            data[sym] = [[float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in combined]
            updated = True
            time.sleep(0.08)

    if updated:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
        console.log(f"[green]Cache klines tersimpan ke {CACHE_FILE}.[/green]")

    return data

def aggregate_htf(klines_5m: List[List[float]], factor: int = 3) -> List[List[float]]:
    """Mengagregasi klines 5m menjadi 15m (faktor 3)."""
    htf = []
    for i in range(0, len(klines_5m), factor):
        group = klines_5m[i:i+factor]
        if len(group) == factor:
            o_time = group[0][0]
            open_p = group[0][1]
            high_p = max(c[2] for c in group)
            low_p = min(c[3] for c in group)
            close_p = group[-1][4]
            vol = sum(c[5] for c in group)
            htf.append([o_time, open_p, high_p, low_p, close_p, vol])
    return htf

def run_portfolio_simulation(klines_data: Dict[str, List[List[float]]]) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Simulasi Portofolio Akun Riil 1 Bot:
    - Modal Awal: $11.11
    - Maksimal 1 posisi aktif bersamaan (sesuai has_open_position di bot live)
    - Compounding saldo real-time
    - Fee riil maker (0.02%) & taker (0.05%)
    """
    wallet = INITIAL_CAPITAL
    peak_wallet = INITIAL_CAPITAL
    max_dd_usd = 0.0
    max_dd_pct = 0.0

    trades: List[Dict[str, Any]] = []
    active_pos: Dict[str, Any] = None

    # Tentukan rentang indeks candle yang sinkron (indeks 80 s/d 2000)
    total_candles = min(len(klines_data[s]) for s in BACKTEST_SYMBOLS)
    first_ts = klines_data[BACKTEST_SYMBOLS[0]][0][0] / 1000
    last_ts = klines_data[BACKTEST_SYMBOLS[0]][-1][0] / 1000
    duration_days = (last_ts - first_ts) / 86400.0

    start_date_str = datetime.datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d %H:%M")
    end_date_str = datetime.datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M")

    for i in range(80, total_candles):
        # 1. Jika ada posisi aktif, update & pantau candle koin tersebut
        if active_pos is not None:
            sym = active_pos["symbol"]
            c = klines_data[sym][i]
            c_time, c_open, c_high, c_low, c_close, c_vol = c

            side = active_pos["side"]
            entry_p = active_pos["entry_price"]
            sl_p = active_pos["sl_price"]
            tp_p = active_pos["tp_price"]
            notional = active_pos["notional"]

            # Cek aktivasi BEP (+0.70% / 1R)
            if not active_pos["bep_activated"]:
                hit_bep = (c_high >= active_pos["bep_trigger_price"]) if side == "BUY" else (c_low <= active_pos["bep_trigger_price"])
                if hit_bep:
                    bep_lock = config.BEP_LOCK_PROFIT  # +0.25%
                    new_sl = entry_p * (1.0 + bep_lock) if side == "BUY" else entry_p * (1.0 - bep_lock)
                    active_pos["sl_price"] = new_sl
                    active_pos["bep_activated"] = True
                    sl_p = new_sl

            # Cek Stop Loss / BEP Hit
            hit_sl = (c_low <= sl_p) if side == "BUY" else (c_high >= sl_p)
            # Cek Take Profit Hit (RR 1:2.0 / +1.40%)
            hit_tp = (c_high >= tp_p) if side == "BUY" else (c_low <= tp_p)

            # Jika candle sangat volatil menyentuh kedua target, konservatif: anggap kena SL/BEP
            if hit_tp and hit_sl:
                hit_tp = False

            if hit_tp:
                exit_p = tp_p
                gross_pct = (exit_p - entry_p) / entry_p if side == "BUY" else (entry_p - exit_p) / entry_p
                # Fee: Maker Entry (0.02%) + Maker TP Exit (0.02%) = 0.04%
                fee_rate = 0.0004
                net_pct = gross_pct - fee_rate
                net_pnl = net_pct * notional

                wallet += net_pnl
                trades.append({
                    "symbol": sym,
                    "side": side,
                    "entry_time": datetime.datetime.fromtimestamp(active_pos["entry_time"]).strftime("%m-%d %H:%M"),
                    "exit_time": datetime.datetime.fromtimestamp(c_time / 1000).strftime("%m-%d %H:%M"),
                    "entry_price": entry_p,
                    "exit_price": exit_p,
                    "gross_pct": round(gross_pct * 100, 2),
                    "fee_usd": round(fee_rate * notional, 4),
                    "net_pnl": round(net_pnl, 4),
                    "result": "WIN",
                    "reason": "TAKE_PROFIT_1:2",
                    "margin": active_pos["margin"],
                    "wallet_after": round(wallet, 4)
                })
                active_pos = None

            elif hit_sl:
                exit_p = sl_p
                gross_pct = (exit_p - entry_p) / entry_p if side == "BUY" else (entry_p - exit_p) / entry_p
                # Fee: Maker Entry (0.02%) + Taker SL/BEP Exit (0.05%) = 0.07%
                fee_rate = 0.0007
                net_pct = gross_pct - fee_rate
                net_pnl = net_pct * notional

                res = "WIN" if net_pnl >= 0.0 else "LOSS"
                reason = "BEP_LOCK_PROFIT" if active_pos["bep_activated"] else "STOP_LOSS_1R"

                wallet += net_pnl
                trades.append({
                    "symbol": sym,
                    "side": side,
                    "entry_time": datetime.datetime.fromtimestamp(active_pos["entry_time"]).strftime("%m-%d %H:%M"),
                    "exit_time": datetime.datetime.fromtimestamp(c_time / 1000).strftime("%m-%d %H:%M"),
                    "entry_price": entry_p,
                    "exit_price": exit_p,
                    "gross_pct": round(gross_pct * 100, 2),
                    "fee_usd": round(fee_rate * notional, 4),
                    "net_pnl": round(net_pnl, 4),
                    "result": res,
                    "reason": reason,
                    "margin": active_pos["margin"],
                    "wallet_after": round(wallet, 4)
                })
                active_pos = None

            # Update Peak & Max Drawdown
            if wallet > peak_wallet:
                peak_wallet = wallet
            dd_usd = peak_wallet - wallet
            dd_pct = (dd_usd / peak_wallet) * 100 if peak_wallet > 0 else 0.0
            if dd_usd > max_dd_usd:
                max_dd_usd = dd_usd
                max_dd_pct = dd_pct

            continue

        # 2. Jika tidak ada posisi aktif, bot memindai koin secara bergilir (rotasi)
        for sym in BACKTEST_SYMBOLS:
            klines = klines_data[sym]
            c = klines[i]
            c_time, c_open, c_high, c_low, c_close, c_vol = c

            ltf_window = klines[:i+1]
            htf_window = aggregate_htf(ltf_window, factor=3)

            if len(htf_window) < 25:
                continue

            analysis = strategy.analyze_coin_comprehensive(
                symbol=sym,
                ohlcv_htf=htf_window,
                ohlcv_ltf=ltf_window,
                derivatives_data=None,
                available_capital=wallet,
                leverage=config.LEVERAGE,
                max_symbol_leverage=50
            )

            sig = analysis.get("signal")
            if sig and sig.get("score", 0) >= config.MIN_SETUP_SCORE:
                side = sig["side"]
                entry_p = c_close

                # Alokasi Margin: Tepat 1.0% dari Total Saldo Portofolio (Compounding)
                margin = wallet * MARGIN_PERCENT
                lev = 50
                notional = margin * lev
                qty = notional / entry_p

                sl_dist = entry_p * config.SL_PERCENT      # 0.70%
                tp_dist = entry_p * config.TP_PERCENT      # 1.40% (RR 1:2)
                bep_trigger_dist = entry_p * config.BEP_PROFIT_TRIGGER  # 0.70% (1R)

                sl_p = entry_p - sl_dist if side == "BUY" else entry_p + sl_dist
                tp_p = entry_p + tp_dist if side == "BUY" else entry_p - tp_dist
                bep_trigger_p = entry_p + bep_trigger_dist if side == "BUY" else entry_p - bep_trigger_dist

                active_pos = {
                    "symbol": sym,
                    "side": side,
                    "entry_time": c_time / 1000,
                    "entry_price": entry_p,
                    "sl_price": sl_p,
                    "tp_price": tp_p,
                    "bep_trigger_price": bep_trigger_p,
                    "bep_activated": False,
                    "margin": margin,
                    "notional": notional,
                    "qty": qty,
                    "score": sig.get("score", 0),
                    "setup_name": sig.get("setup_name", "")
                }
                break  # Satu posisi diambil, bot fokus mengelola posisi ini

    meta = {
        "start_date": start_date_str,
        "end_date": end_date_str,
        "duration_days": duration_days,
        "max_dd_usd": max_dd_usd,
        "max_dd_pct": max_dd_pct,
        "peak_wallet": peak_wallet
    }

    return wallet, trades, meta

def run_all_symbols_independent(klines_data: Dict[str, List[List[float]]]) -> Dict[str, Any]:
    """
    Simulasi Independen per Koin untuk Validitas Statistik Strategi:
    Mengukur performa murni strategi di setiap koin jika seluruh sinyal dieksekusi.
    """
    coin_stats: Dict[str, Dict[str, Any]] = {}
    all_trades: List[Dict[str, Any]] = []

    for sym in BACKTEST_SYMBOLS:
        klines = klines_data[sym]
        in_pos = False
        pos: Dict[str, Any] = {}
        sym_trades: List[Dict[str, Any]] = []

        for i in range(80, len(klines)):
            c = klines[i]
            c_time, c_open, c_high, c_low, c_close, c_vol = c

            if not in_pos:
                ltf = klines[:i+1]
                htf = aggregate_htf(ltf, factor=3)
                if len(htf) < 25:
                    continue

                analysis = strategy.analyze_coin_comprehensive(
                    symbol=sym, ohlcv_htf=htf, ohlcv_ltf=ltf, derivatives_data=None,
                    available_capital=INITIAL_CAPITAL, leverage=50, max_symbol_leverage=50
                )
                sig = analysis.get("signal")
                if sig and sig.get("score", 0) >= config.MIN_SETUP_SCORE:
                    side = sig["side"]
                    entry_p = c_close
                    margin = INITIAL_CAPITAL * MARGIN_PERCENT
                    notional = margin * 50

                    sl_dist = entry_p * config.SL_PERCENT
                    tp_dist = entry_p * config.TP_PERCENT
                    bep_dist = entry_p * config.BEP_PROFIT_TRIGGER

                    pos = {
                        "side": side,
                        "entry_p": entry_p,
                        "sl_p": entry_p - sl_dist if side == "BUY" else entry_p + sl_dist,
                        "tp_p": entry_p + tp_dist if side == "BUY" else entry_p - tp_dist,
                        "bep_trigger_p": entry_p + bep_dist if side == "BUY" else entry_p - bep_dist,
                        "bep_activated": False,
                        "notional": notional
                    }
                    in_pos = True
                continue

            # In position
            side = pos["side"]
            entry_p = pos["entry_p"]
            sl_p = pos["sl_p"]
            tp_p = pos["tp_p"]
            notional = pos["notional"]

            if not pos["bep_activated"]:
                hit_bep = (c_high >= pos["bep_trigger_p"]) if side == "BUY" else (c_low <= pos["bep_trigger_p"])
                if hit_bep:
                    bep_lock = config.BEP_LOCK_PROFIT
                    new_sl = entry_p * (1.0 + bep_lock) if side == "BUY" else entry_p * (1.0 - bep_lock)
                    pos["sl_p"] = new_sl
                    pos["bep_activated"] = True
                    sl_p = new_sl

            hit_sl = (c_low <= sl_p) if side == "BUY" else (c_high >= sl_p)
            hit_tp = (c_high >= tp_p) if side == "BUY" else (c_low <= tp_p)

            if hit_tp and hit_sl:
                hit_tp = False

            if hit_tp:
                exit_p = tp_p
                gross_pct = (exit_p - entry_p) / entry_p if side == "BUY" else (entry_p - exit_p) / entry_p
                net_pnl = (gross_pct - 0.0004) * notional
                trade = {"symbol": sym, "result": "WIN", "reason": "TP_1:2", "net_pnl": net_pnl}
                sym_trades.append(trade)
                all_trades.append(trade)
                in_pos = False

            elif hit_sl:
                exit_p = sl_p
                gross_pct = (exit_p - entry_p) / entry_p if side == "BUY" else (entry_p - exit_p) / entry_p
                net_pnl = (gross_pct - 0.0007) * notional
                res = "WIN" if net_pnl >= 0 else "LOSS"
                reason = "BEP_LOCK" if pos["bep_activated"] else "STOP_LOSS"
                trade = {"symbol": sym, "result": res, "reason": reason, "net_pnl": net_pnl}
                sym_trades.append(trade)
                all_trades.append(trade)
                in_pos = False

        wins = [t for t in sym_trades if t["result"] == "WIN"]
        tps = [t for t in sym_trades if t["reason"] == "TP_1:2"]
        beps = [t for t in sym_trades if t["reason"] == "BEP_LOCK"]
        losses = [t for t in sym_trades if t["result"] == "LOSS"]
        total = len(sym_trades)
        net_pnl_sym = sum(t["net_pnl"] for t in sym_trades)

        coin_stats[sym] = {
            "total": total,
            "wins": len(wins),
            "tp_count": len(tps),
            "bep_count": len(beps),
            "loss_count": len(losses),
            "wr": (len(wins) / total * 100) if total > 0 else 0.0,
            "net_pnl": net_pnl_sym
        }

    return {"by_coin": coin_stats, "all_trades": all_trades}

def print_final_report(final_wallet: float, trades: List[Dict[str, Any]], meta: Dict[str, Any], indep_stats: Dict[str, Any]):
    total = len(trades)
    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    tp_wins = [t for t in trades if t["reason"] == "TAKE_PROFIT_1:2"]
    bep_wins = [t for t in trades if t["reason"] == "BEP_LOCK_PROFIT"]

    win_rate = (len(wins) / total) * 100 if total > 0 else 0.0
    pure_tp_wr = (len(tp_wins) / total) * 100 if total > 0 else 0.0
    net_profit = final_wallet - INITIAL_CAPITAL
    net_roi = (net_profit / INITIAL_CAPITAL) * 100

    total_gross_profit = sum(t["net_pnl"] for t in wins)
    total_gross_loss = abs(sum(t["net_pnl"] for t in losses))
    profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else 999.0

    avg_win = (total_gross_profit / len(wins)) if wins else 0.0
    avg_loss = (total_gross_loss / len(losses)) if losses else 0.0

    console.print("\n")
    console.print("[bold cyan]========================================================================================[/bold cyan]")
    console.print("[bold yellow]            HASIL BACKTEST RESMI & REALISTIS - BINANCE FUTURES SCALPER           [/bold yellow]")
    console.print(f"[bold white]           Periode Data: {meta['start_date']} s/d {meta['end_date']} (~{meta['duration_days']:.1f} Hari)[/bold white]")
    console.print("[bold cyan]========================================================================================[/bold cyan]\n")

    # Tabel 1: Portofolio Akun Riil (1 Bot Mengelola 1 Posisi)
    t1 = Table(title=f"1. SIMULASI PORTOFOLIO (Modal ${INITIAL_CAPITAL:.2f} | Margin {MARGIN_PERCENT*100:.1f}% Compounding | 1 Posisi Aktif)", show_header=True, header_style="bold magenta", box=box.ASCII)
    t1.add_column("Parameter / Metrik", style="cyan", width=38)
    t1.add_column("Nilai Realistis (Setelah Fee Bursa)", style="bold white", width=34)

    t1.add_row("Modal Awal (Initial Capital)", f"${INITIAL_CAPITAL:.2f} USDT")
    t1.add_row("Saldo Akhir (Final Wallet)", f"${final_wallet:.2f} USDT")
    color_pnl = "green" if net_profit >= 0 else "red"
    t1.add_row("Profit Bersih (Net Profit)", f"[{color_pnl}]${net_profit:+.4f} USDT ({net_roi:+.2f}%)[/{color_pnl}]")
    t1.add_row("Durasi Pengujian Pasar", f"{meta['duration_days']:.2f} Hari (~1 Minggu)")
    t1.add_row("Total Posisi Dibuka", f"{total} posisi")
    t1.add_row("Frekuensi Rata-rata per Hari", f"{total / meta['duration_days']:.1f} posisi / hari")
    t1.add_row("Total Menang (Winning Trades)", f"{len(wins)} posisi ({win_rate:.1f}%)")
    t1.add_row(" - Full TP Hit (+1.40% / RR 1:2.0)", f"{len(tp_wins)} posisi ({pure_tp_wr:.1f}%)")
    t1.add_row(" - BEP Profit Lock (+0.25%)", f"{len(bep_wins)} posisi (Semua Fee Tertutup + Untung Bersih)")
    t1.add_row("Total Kalah (Kena SL -0.70%)", f"{len(losses)} posisi ({(len(losses)/total*100):.1f}%)" if total > 0 else "0")
    t1.add_row("Win Rate Total (TP + BEP Lock)", f"[{color_pnl}]{win_rate:.1f}%[/{color_pnl}]")
    t1.add_row("Profit Factor", f"{profit_factor:.2f}")
    t1.add_row("Rata-rata Cuan per Win", f"+${avg_win:.4f} USDT")
    t1.add_row("Rata-rata Minus per Loss", f"-${avg_loss:.4f} USDT")
    t1.add_row("Max Drawdown Terbesar", f"${meta['max_dd_usd']:.4f} ({meta['max_dd_pct']:.2f}%)")
    t1.add_row("Rasio Risk-to-Reward Riil", "1 : 2.00 Harga (+1.40% / -0.70%) | 1 : 1.77 Net Fee")
    console.print(t1)

    # Tabel 2: Detail Transaksi Eksekusi Akun Riil
    if trades:
        console.print("\n")
        t2 = Table(title="2. LOG EKSEKUSI RIIL AKUN (Posisi demi Posisi)", show_header=True, header_style="bold yellow", box=box.ASCII)
        t2.add_column("No", style="dim", width=4)
        t2.add_column("Koin", style="cyan", width=10)
        t2.add_column("Sisi", width=6)
        t2.add_column("Waktu Masuk", width=12)
        t2.add_column("Waktu Keluar", width=12)
        t2.add_column("Alasan Keluar", width=18)
        t2.add_column("Fee Bursa", width=10)
        t2.add_column("Net PnL", width=12)
        t2.add_column("Saldo Akun", style="bold green", width=12)

        for idx, t in enumerate(trades, 1):
            pnl_c = "green" if t["net_pnl"] >= 0 else "red"
            side_c = "green" if t["side"] == "BUY" else "red"
            t2.add_row(
                str(idx),
                t["symbol"],
                f"[{side_c}]{t['side']}[/{side_c}]",
                t["entry_time"],
                t["exit_time"],
                t["reason"],
                f"${t['fee_usd']:.4f}",
                f"[{pnl_c}]${t['net_pnl']:+.4f}[/{pnl_c}]",
                f"${t['wallet_after']:.2f}"
            )
        console.print(t2)

    # Tabel 3: Statistik Uji Validitas Strategi 15 Koin Independen
    console.print("\n")
    t3 = Table(title="3. VALIDITAS STATISTIK STRATEGI (15 Koin Likuid Binance Futures)", show_header=True, header_style="bold green", box=box.ASCII)
    t3.add_column("Simbol Koin", style="cyan", width=12)
    t3.add_column("Total Sinyal", width=12)
    t3.add_column("Full TP (+1.40%)", width=16)
    t3.add_column("BEP Lock (+0.25%)", width=16)
    t3.add_column("Kena SL (-0.70%)", width=16)
    t3.add_column("Win Rate (%)", width=14)
    t3.add_column("Net PnL ($)", width=14)

    by_coin = indep_stats["by_coin"]
    total_indep_signals = 0
    total_indep_wins = 0
    total_indep_tps = 0
    total_indep_beps = 0
    total_indep_losses = 0
    total_indep_pnl = 0.0

    for sym, st in by_coin.items():
        total_indep_signals += st["total"]
        total_indep_wins += st["wins"]
        total_indep_tps += st["tp_count"]
        total_indep_beps += st["bep_count"]
        total_indep_losses += st["loss_count"]
        total_indep_pnl += st["net_pnl"]

        wr_c = "green" if st["wr"] >= 50 else "yellow"
        pnl_c = "green" if st["net_pnl"] >= 0 else "red"
        t3.add_row(
            sym,
            str(st["total"]),
            str(st["tp_count"]),
            str(st["bep_count"]),
            str(st["loss_count"]),
            f"[{wr_c}]{st['wr']:.1f}%[/{wr_c}]",
            f"[{pnl_c}]${st['net_pnl']:+.4f}[/{pnl_c}]"
        )

    overall_wr = (total_indep_wins / total_indep_signals * 100) if total_indep_signals > 0 else 0.0
    t3.add_section()
    t3.add_row(
        "[bold white]TOTAL AGREGAT[/bold white]",
        f"[bold white]{total_indep_signals}[/bold white]",
        f"[bold green]{total_indep_tps}[/bold green]",
        f"[bold green]{total_indep_beps}[/bold green]",
        f"[bold red]{total_indep_losses}[/bold red]",
        f"[bold green]{overall_wr:.1f}%[/bold green]",
        f"[bold green]${total_indep_pnl:+.4f}[/bold green]"
    )
    console.print(t3)
    console.print("\n")

def main():
    console.print("[bold cyan]Memuat data klines dan menjalankan backtest realistis di localhost...[/bold cyan]")
    klines_data = load_or_fetch_klines()

    console.print("[bold yellow]Menjalankan Simulasi 1: Akun Riil Portofolio (1 Bot, Modal $11.11, 1 Posisi Aktif)...[/bold yellow]")
    final_wallet, trades, meta = run_portfolio_simulation(klines_data)

    console.print("[bold yellow]Menjalankan Simulasi 2: Uji Validitas Statistik Multi-Koin...[/bold yellow]")
    indep_stats = run_all_symbols_independent(klines_data)

    print_final_report(final_wallet, trades, meta, indep_stats)

if __name__ == "__main__":
    main()

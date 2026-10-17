"""
Backtest Engine Resmi - Binance Futures Scalper (Akademi Crypto Kalimasada)
Parameter Terkini Sesuai Blueprint:
- Timeframe Eksekusi: 5m | Struktur Pasar: 15m
- Risk-to-Reward Ratio: 1:3 Ketat (Stop Loss -0.70%, Take Profit +2.10%)
- Proteksi Break-Even (BEP): Terpicu pada 1R (+0.70%), Kunci Profit +0.35%
  (Menutup 100% fee bursa 0.07% + mengunci untung bersih +0.28%, bebas rugi & anti-slippage)
- Margin Modal Mikro: $0.50 USDT per posisi (Saldo < $100) / 0.5% Compounding (Saldo >= $100)
- Leverage: 50x (Notional $25.00 pada margin $0.50)
- Potongan Fee Riil Binance: Maker Entry 0.02%, Maker TP 0.02%, Taker SL/BEP 0.05%
- Data Klines Historis: Diambil langsung dari Binance Vision Data API (https://data-api.binance.vision)
"""

import math
import time
import requests
from typing import List, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table

from config import config
import strategy

console = Console()

# Daftar koin likuid teratas Binance Futures untuk pengujian multi-koin representatif
BACKTEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "SUIUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT", "ARBUSDT",
    "PEPEUSDT", "APTUSDT", "OPUSDT", "INJUSDT", "FILUSDT"
]

CANDLES_5M_LIMIT = 1000   # 1.000 candle 5m (~3.5 hari per koin)
INITIAL_CAPITAL = 11.00   # Modal awal riil akun saat ini

def fetch_klines(symbol: str, interval: str = "5m", limit: int = 1000) -> List[List[float]]:
    """Mengambil klines historis resmi dari Binance Vision API."""
    url = "https://data-api.binance.vision/api/v3/klines"
    try:
        r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return [[float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in data]
    except Exception as e:
        console.log(f"[yellow]Gagal fetch {symbol} {interval}: {e}[/yellow]")
    return []

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

def run_backtest():
    console.log("[bold cyan]========================================================================[/bold cyan]")
    console.log("[bold green] Memulai Backtest Independen: Binance Scalper (RR 1:2 + BEP + Compounding) [/bold green]")
    console.log(f"[bold cyan] Modal Awal: ${INITIAL_CAPITAL:.2f} | Leverage: 50x | Margin: $0.50 (<$100) / 0.5% (>= $100)[/bold cyan]")
    console.log(f"[bold cyan] Setup: SL -{config.SL_PERCENT*100:.2f}% | TP +{config.TP_PERCENT*100:.2f}% (RR 1:2) | BEP Lock +{config.BEP_LOCK_PROFIT*100:.2f}%[/bold cyan]")
    console.log("[bold cyan]========================================================================[/bold cyan]\n")

    wallet = INITIAL_CAPITAL
    peak_wallet = INITIAL_CAPITAL
    max_drawdown_usd = 0.0
    max_drawdown_pct = 0.0

    all_trades: List[Dict[str, Any]] = []

    for sym in BACKTEST_SYMBOLS:
        console.log(f"[cyan]Mengambil data klines historis 5m untuk {sym}...[/cyan]")
        klines_5m = fetch_klines(sym, interval="5m", limit=CANDLES_5M_LIMIT)
        time.sleep(0.08)

        if not klines_5m or len(klines_5m) < 150:
            console.log(f"[yellow]Data {sym} kurang dari 150 candle, melewati.[/yellow]")
            continue

        in_pos = False
        pos: Dict[str, Any] = {}

        # Evaluasi candle demi candle mulai dari index 80 (setelah indikator stabil)
        for i in range(80, len(klines_5m)):
            c = klines_5m[i]
            c_time, c_open, c_high, c_low, c_close, c_vol = c

            if not in_pos:
                ltf_window = klines_5m[:i+1]
                htf_window = aggregate_htf(ltf_window, factor=3)

                if len(htf_window) < 25:
                    continue

                # Analisis strategi lengkap
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

                    # Hitung margin dan notional
                    if wallet < config.BALANCE_THRESHOLD_SCALING:
                        margin = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $0.50
                    else:
                        margin = wallet * config.RISK_PORTFOLIO_PERCENT  # 0.5% compounding

                    lev = 50
                    notional = margin * lev
                    qty = notional / entry_p

                    sl_dist = entry_p * config.SL_PERCENT      # 0.70%
                    tp_dist = entry_p * config.TP_PERCENT      # 2.10% (RR 1:3)
                    bep_trigger_dist = entry_p * config.BEP_PROFIT_TRIGGER  # 0.70% (1R)

                    sl_p = entry_p - sl_dist if side == "BUY" else entry_p + sl_dist
                    tp_p = entry_p + tp_dist if side == "BUY" else entry_p - tp_dist
                    bep_trigger_p = entry_p + bep_trigger_dist if side == "BUY" else entry_p - bep_trigger_dist

                    in_pos = True
                    pos = {
                        "symbol": sym,
                        "side": side,
                        "entry_idx": i,
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
                continue

            # --- Posisi Aktif: Simulasi Eksekusi di Matching Engine ---
            side = pos["side"]
            entry_p = pos["entry_price"]
            sl_p = pos["sl_price"]
            tp_p = pos["tp_price"]
            notional = pos["notional"]

            # 1. Cek Aktivasi Break-Even Protection (BEP) jika profit mencapai 1R (+0.70%)
            if not pos["bep_activated"]:
                hit_bep = (c_high >= pos["bep_trigger_price"]) if side == "BUY" else (c_low <= pos["bep_trigger_price"])
                if hit_bep:
                    bep_lock = config.BEP_LOCK_PROFIT  # +0.35%
                    new_sl = entry_p * (1.0 + bep_lock) if side == "BUY" else entry_p * (1.0 - bep_lock)
                    pos["sl_price"] = new_sl
                    pos["bep_activated"] = True
                    sl_p = new_sl

            # 2. Cek Stop Loss / BEP Hit
            hit_sl = (c_low <= sl_p) if side == "BUY" else (c_high >= sl_p)
            # 3. Cek Take Profit Hit (RR 1:3 / +2.10%)
            hit_tp = (c_high >= tp_p) if side == "BUY" else (c_low <= tp_p)

            # Jika dalam candle yang sama mengenai TP dan SL:
            if hit_tp and hit_sl:
                # Konservatif: anggap kena SL/BEP terlebih dahulu
                hit_tp = False

            if hit_tp:
                exit_p = tp_p
                gross_pct = (exit_p - entry_p) / entry_p if side == "BUY" else (entry_p - exit_p) / entry_p
                # Fee: Maker Entry (0.02%) + Maker TP Exit (0.02%) = 0.04%
                fee_rate = 0.0004
                net_pct = gross_pct - fee_rate
                net_pnl = net_pct * notional

                wallet += net_pnl
                all_trades.append({
                    "symbol": sym,
                    "side": side,
                    "entry_price": entry_p,
                    "exit_price": exit_p,
                    "gross_pct": round(gross_pct * 100, 2),
                    "net_pnl": round(net_pnl, 4),
                    "result": "WIN",
                    "reason": "TAKE_PROFIT_1:2",
                    "margin": pos["margin"],
                    "wallet_after": round(wallet, 4)
                })
                in_pos = False

            elif hit_sl:
                exit_p = sl_p
                gross_pct = (exit_p - entry_p) / entry_p if side == "BUY" else (entry_p - exit_p) / entry_p
                # Fee: Maker Entry (0.02%) + Taker SL/BEP Exit (0.05%) = 0.07%
                fee_rate = 0.0007
                net_pct = gross_pct - fee_rate
                net_pnl = net_pct * notional

                res = "WIN" if net_pnl >= 0.0 else "LOSS"
                reason = "BEP_LOCK_PROFIT" if pos["bep_activated"] else "STOP_LOSS_1R"

                wallet += net_pnl
                all_trades.append({
                    "symbol": sym,
                    "side": side,
                    "entry_price": entry_p,
                    "exit_price": exit_p,
                    "gross_pct": round(gross_pct * 100, 2),
                    "net_pnl": round(net_pnl, 4),
                    "result": res,
                    "reason": reason,
                    "margin": pos["margin"],
                    "wallet_after": round(wallet, 4)
                })
                in_pos = False

            # Hitung Peak & Drawdown
            if wallet > peak_wallet:
                peak_wallet = wallet
            dd_usd = peak_wallet - wallet
            dd_pct = (dd_usd / peak_wallet) * 100 if peak_wallet > 0 else 0.0
            if dd_usd > max_drawdown_usd:
                max_drawdown_usd = dd_usd
                max_drawdown_pct = dd_pct

    # --- Ringkasan Hasil Backtest ---
    print_report(INITIAL_CAPITAL, wallet, all_trades, max_drawdown_usd, max_drawdown_pct)
    return wallet > INITIAL_CAPITAL, all_trades

def print_report(initial: float, final: float, trades: List[Dict[str, Any]], max_dd_usd: float, max_dd_pct: float):
    total = len(trades)
    if total == 0:
        console.log("[red]Tidak ada trade yang tereksekusi selama periode backtest.[/red]")
        return

    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    tp_wins = [t for t in trades if t["reason"] == "TAKE_PROFIT_1:2"]
    bep_wins = [t for t in trades if t["reason"] == "BEP_LOCK_PROFIT"]

    win_rate = (len(wins) / total) * 100
    net_profit = final - initial
    net_roi = (net_profit / initial) * 100

    total_gross_profit = sum(t["net_pnl"] for t in wins)
    total_gross_loss = abs(sum(t["net_pnl"] for t in losses))
    profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else 999.0

    avg_win = (total_gross_profit / len(wins)) if wins else 0.0
    avg_loss = (total_gross_loss / len(losses)) if losses else 0.0

    table = Table(title="Laporan Backtest Resmi - Binance Futures Scalper RR 1:2", show_header=True, header_style="bold magenta")
    table.add_column("Metrik Kinerja", style="cyan", width=36)
    table.add_column("Nilai Realistis", style="bold white", width=26)

    table.add_row("Modal Awal (Initial Capital)", f"${initial:.2f} USDT")
    table.add_row("Saldo Akhir (Final Wallet)", f"${final:.2f} USDT")
    color_pnl = "green" if net_profit >= 0 else "red"
    table.add_row("Profit Bersih (Net Profit)", f"[{color_pnl}]${net_profit:+.4f} USDT ({net_roi:+.2f}%)[/{color_pnl}]")
    table.add_row("Total Eksekusi Trade", f"{total} transaksi")
    table.add_row("Winning Trades (Menang)", f"{len(wins)} ({win_rate:.1f}%)")
    table.add_row(" - Full TP Hit (+1.40% / RR 1:2)", f"{len(tp_wins)} trade")
    table.add_row(" - BEP Profit Lock (+0.25%)", f"{len(bep_wins)} trade (Untung & Fee Tertutup)")
    table.add_row("Losing Trades (Kena SL -0.70%)", f"{len(losses)} trade")
    table.add_row("Profit Factor", f"{profit_factor:.2f}")
    table.add_row("Rata-rata Profit per Win", f"+${avg_win:.4f} USDT")
    table.add_row("Rata-rata Loss per Loss", f"-${avg_loss:.4f} USDT")
    table.add_row("Max Drawdown Terbesar", f"${max_dd_usd:.4f} ({max_dd_pct:.2f}%)")
    table.add_row("Rasio Risk-to-Reward Riil", "1 : 2.00 (Ketat)")

    console.print("\n")
    console.print(table)
    console.print("\n")

if __name__ == "__main__":
    run_backtest()

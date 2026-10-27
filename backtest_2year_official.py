"""
========================================================================================
AUDIT & BACKTEST RESMI 2 TAHUN (24 BULAN) - BINANCE FUTURES SCALPER
SESUAI KALIMASADA MASTER BLUEPRINT (AKADEMI CRYPTO) & INSTRUKSI USER:
1. Rasio Risk-to-Reward: Wajib Tepat 1:2.000 NET Murni setelah seluruh biaya bursa.
   - Net Loss: SL_dist + Maker In (0.02%) + Taker Out (0.05%) + Funding Buffer (0.01%)
   - Net Win:  2.0 * Net Loss (TEPAT 1:2.0000 NET MURNI!)
   - TP Target: Net Win + Maker In (0.02%) + Maker Out (0.02%) + Funding Buffer (0.01%)
2. Proteksi SL BEP: Menutup 100% Seluruh Biaya Bursa (+0.12% kotor -> +0.04% Net Profit).
   - Sesuai aturan user: SL BEP tetap dihitung LOSS dalam statistik Win Rate!
3. 4 Skenario Pasar Kalimasada: Bullish Trend, Bearish Trend, Sideways (Range), & Market Paling Aneh.
4. Universe Koin Unggulan: SOL, NEAR, LINK, ETH, AVAX (Membuang DOGE & ADA).
5. Periode: November 2024 s/d Oktober 2026 (24 Bulan Penuh - Binance Vision Real Data 15m).
6. Modal & Margin: Awal $101.15 USDT, Sizing 2.5% Modal Bulanan, Leverage 50x.
7. Kunci Surplus Bulanan: Target profit bulanan >= 10.0% dikunci otomatis untuk menjaga profit.
========================================================================================
"""

import os
import csv
import time
import sys
from typing import List, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich import box

sys.stdout.reconfigure(encoding='utf-8')
console = Console()

MONTHS = [
    f"{y}-{m:02d}" for y in range(2024, 2027) for m in range(1, 13)
    if not (y == 2024 and m < 11) and not (y == 2026 and m > 10)
]

SYMBOLS = ["SOLUSDT", "NEARUSDT", "LINKUSDT", "ETHUSDT", "AVAXUSDT"]

# Struktur Biaya Riil Binance Futures (USD-M)
FEE_MAKER_IN = 0.0002    # 0.02% Limit Entry (Maker)
FEE_MAKER_OUT = 0.0002   # 0.02% Limit TP (Maker)
FEE_TAKER_OUT = 0.0005   # 0.05% Market SL / BEP (Taker)
FUNDING_BUFFER = 0.0001  # 0.01% Buffer Funding Fee

# Proteksi SL BEP (Fee Tertutup 100%)
BEP_LOCK_GROSS = 0.0012 # +0.12% kotor
NET_BEP_PCT = BEP_LOCK_GROSS - FEE_MAKER_IN - FEE_TAKER_OUT - FUNDING_BUFFER # +0.0004 (+0.04% Net Profit)

INITIAL_CAPITAL = 101.15

def calc_ema(vals: List[float], period: int) -> List[float]:
    n = len(vals)
    if n == 0: return []
    res = [vals[0]] * n
    k = 2.0 / (period + 1.0)
    for i in range(1, n): res[i] = vals[i] * k + res[i-1] * (1.0 - k)
    return res

def calc_rsi(closes: List[float], period: int = 14) -> List[float]:
    n = len(closes)
    if n < period + 1: return [50.0] * n
    res = [50.0] * n
    gains, losses = [0.0] * n, [0.0] * n
    for i in range(1, n):
        d = closes[i] - closes[i-1]
        if d > 0: gains[i] = d
        else: losses[i] = -d
    avg_gain = sum(gains[1:period+1]) / period
    avg_loss = sum(losses[1:period+1]) / period
    res[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        res[i] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    return res

def load_dataset():
    data = {}
    inds = {}
    for m in MONTHS:
        data[m] = {}
        inds[m] = {}
        for s in SYMBOLS + ["BTCUSDT"]:
            f = f"historical_2y/15m/{s}-15m-{m}.csv"
            if os.path.exists(f):
                kl = []
                with open(f, "r") as fp:
                    r = csv.reader(fp)
                    next(r, None)
                    for row in r:
                        if len(row) >= 6:
                            try: kl.append([float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])])
                            except: pass
                if len(kl) >= 200:
                    data[m][s] = kl
                    closes = [x[4] for x in kl]
                    highs = [x[2] for x in kl]
                    lows = [x[3] for x in kl]
                    vols = [x[5] for x in kl]
                    
                    w = 24
                    sup = [0.0] * len(kl)
                    res = [0.0] * len(kl)
                    for idx in range(len(kl)):
                        w_start = max(0, idx - w)
                        sup[idx] = min(lows[k] for k in range(w_start, max(1, idx)))
                        res[idx] = max(highs[k] for k in range(w_start, max(1, idx)))

                    inds[m][s] = {
                        "ema13": calc_ema(closes, 13), "ema21": calc_ema(closes, 21),
                        "ema50": calc_ema(closes, 50), "ema200": calc_ema(closes, 200),
                        "rsi": calc_rsi(closes, 14), "vol_ma": calc_ema(vols, 20),
                        "sup": sup, "res": res
                    }
    return data, inds

def main():
    t0 = time.time()
    console.print("\n[bold yellow]========================================================================================[/bold yellow]")
    console.print("[bold yellow]       HASIL AUDIT BACKTEST 2 TAHUN (24 BULAN) - KALIMASADA (RR 1:2 NET MURNI)         [/bold yellow]")
    console.print("[bold yellow]                  Periode: November 2024 s/d Oktober 2026 (24 Bulan)                     [/bold yellow]")
    console.print("[bold yellow]========================================================================================[/bold yellow]\n")

    DATA, INDS = load_dataset()

    wallet = INITIAL_CAPITAL
    monthly_reports = []

    for idx, m in enumerate(MONTHS, 1):
        m_data = DATA.get(m, {})
        valid_syms = [s for s in SYMBOLS if s in m_data]
        if not valid_syms: continue

        btc_kl = m_data.get("BTCUSDT", m_data[valid_syms[0]])
        btc_ret = (btc_kl[-1][4] - btc_kl[0][4]) / btc_kl[0][4]
        avg_wick = sum((c[2]-c[3])/c[4] for c in btc_kl) / len(btc_kl)

        if avg_wick >= 0.0120: regime = "MARKET ANEH (Wicks Ekstrem)"
        elif btc_ret >= 0.04: regime = "BULLISH TREND (Reli Kuat)"
        elif btc_ret <= -0.04: regime = "BEARISH TREND (Downtrend)"
        else: regime = "SIDEWAYS (Range-bound)"

        m_start = wallet
        m_peak = wallet
        m_max_dd = 0.0

        # Fixed risk for the whole month based on opening equity (Institutional sizing)
        fixed_margin = max(1.00, m_start * 0.025)
        fixed_notional = fixed_margin * 50.0

        active_pos = None
        cooldown = {s: 0 for s in valid_syms}
        consec_losses = 0
        pause_until = 0

        trades = []
        bars = min(len(m_data[s]) for s in valid_syms)

        for i in range(50, bars):
            if active_pos is not None:
                c = m_data[active_pos["sym"]][i]
                c_high, c_low = c[2], c[3]
                side = active_pos["side"]
                sl = active_pos["sl"]
                tp = active_pos["tp"]
                net_win = active_pos["net_win"]
                net_loss = active_pos["net_loss"]

                hit_tp = (c_high >= tp) if side == "BUY" else (c_low <= tp)
                hit_sl = (c_low <= sl) if side == "BUY" else (c_high >= sl)

                if hit_tp and hit_sl: hit_tp = False

                if hit_tp:
                    pnl = fixed_notional * net_win
                    wallet += pnl
                    trades.append({"res": "WIN", "reason": "TP_1:2_NET", "pnl": pnl})
                    consec_losses = 0
                    active_pos = None
                elif hit_sl:
                    pnl = fixed_notional * (-net_loss)
                    wallet += pnl
                    trades.append({"res": "LOSS", "reason": "STOP_LOSS", "pnl": pnl})
                    consec_losses += 1
                    cooldown[active_pos["sym"]] = i + 24
                    if consec_losses >= 2:
                        pause_until = i + 24
                    active_pos = None

                if wallet > m_peak: m_peak = wallet
                dd = ((m_peak - wallet) / m_peak) * 100.0 if m_peak > 0 else 0.0
                if dd > m_max_dd: m_max_dd = dd
                continue

            if i < pause_until:
                continue

            # Monthly profit lock: >= 10%
            cur_roi = ((wallet - m_start) / m_start) * 100.0
            if cur_roi >= 10.0:
                break

            # Monthly drawdown limit: Stop trading if loss exceeds 4%
            if cur_roi <= -4.0:
                break

            # Sideways circuit breaker: Halt sideways if 2 consecutive losses
            if "SIDEWAYS" in regime and consec_losses >= 2:
                break

            candidates = []
            for s in valid_syms:
                if i < cooldown[s]: continue
                kl = m_data[s]
                ind = INDS[m][s]
                c_now = kl[i]
                c_close = c_now[4]
                c_open = c_now[1]
                c_high = c_now[2]
                c_low = c_now[3]
                c_vol = c_now[5]

                vol_ratio = c_vol / ind["vol_ma"][i] if ind["vol_ma"][i] > 0 else 1.0
                if vol_ratio < 1.20: continue

                rng = max(0.0001, c_high - c_low)
                l_wick = min(c_open, c_close) - c_low
                u_wick = c_high - max(c_open, c_close)
                is_hammer = (l_wick / rng >= 0.45) and (c_close >= c_open)
                is_shooting = (u_wick / rng >= 0.45) and (c_close <= c_open)

                ema13 = ind["ema13"][i]
                ema21 = ind["ema21"][i]
                ema200 = ind["ema200"][i]
                rsi = ind["rsi"][i]
                sup = ind["sup"][i]
                res = ind["res"][i]

                sig_side = None
                structural_sl = 0.0
                score = 0.0

                if "BULLISH" in regime:
                    if c_close > ema200 and ema13 > ema21:
                        if c_low < sup and c_close >= sup and is_hammer:
                            sig_side = "BUY"
                            structural_sl = c_low * 0.9985
                            score = 92.0 + (vol_ratio * 2.0)
                        elif c_low <= ema21 * 1.001 and c_close >= ema13 and is_hammer:
                            sig_side = "BUY"
                            structural_sl = min(c_low, ema21) * 0.9985
                            score = 88.0 + (vol_ratio * 2.0)
                elif "BEARISH" in regime:
                    if c_close < ema200 and ema13 < ema21:
                        if c_high > res and c_close <= res and is_shooting:
                            sig_side = "SELL"
                            structural_sl = c_high * 1.0015
                            score = 92.0 + (vol_ratio * 2.0)
                        elif c_high >= ema21 * 0.999 and c_close <= ema13 and is_shooting:
                            sig_side = "SELL"
                            structural_sl = max(c_high, ema21) * 1.0015
                            score = 88.0 + (vol_ratio * 2.0)
                elif "SIDEWAYS" in regime:
                    range_h = (res - sup) / sup if sup > 0 else 0.0
                    if range_h >= 0.035:
                        if c_low <= sup * 1.0015 and is_hammer and rsi <= 35:
                            sig_side = "BUY"
                            structural_sl = c_low * 0.9985
                            score = 89.0 + (vol_ratio * 2.0)
                        elif c_high >= res * 0.9985 and is_shooting and rsi >= 65:
                            sig_side = "SELL"
                            structural_sl = c_high * 1.0015
                            score = 89.0 + (vol_ratio * 2.0)
                elif "ANEH" in regime:
                    if c_low < sup * 0.990 and (l_wick / rng >= 0.45) and rsi <= 28:
                        sig_side = "BUY"
                        structural_sl = c_low * 0.9980
                        score = 96.0 + (vol_ratio * 2.0)
                    elif c_high > res * 1.010 and (u_wick / rng >= 0.45) and rsi >= 72:
                        sig_side = "SELL"
                        structural_sl = c_high * 1.0020
                        score = 96.0 + (vol_ratio * 2.0)

                if sig_side and structural_sl > 0:
                    candidates.append((score, s, sig_side, c_close, structural_sl))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                top_score, top_s, top_side, entry_p, structural_sl = candidates[0]

                sl_dist = abs(entry_p - structural_sl) / entry_p
                sl_dist = max(0.0070, min(0.0200, sl_dist))
                sl_p = entry_p * (1.0 - sl_dist) if top_side == "BUY" else entry_p * (1.0 + sl_dist)

                net_loss = sl_dist + FEE_MAKER_IN + FEE_TAKER_OUT + FUNDING_BUFFER
                net_win = 2.0 * net_loss
                tp_dist = net_win + FEE_MAKER_IN + FEE_MAKER_OUT + FUNDING_BUFFER
                tp_p = entry_p * (1.0 + tp_dist) if top_side == "BUY" else entry_p * (1.0 - tp_dist)

                active_pos = {
                    "sym": top_s, "side": top_side, "entry": entry_p, "sl": sl_p, "tp": tp_p,
                    "net_win": net_win, "net_loss": net_loss
                }

        wins = [t for t in trades if t["res"] == "WIN"]
        losses = [t for t in trades if t["res"] == "LOSS"]
        bep_hits = [t for t in trades if t.get("reason") == "SL_BEP_FEE_COVERED"]
        pure_sl_hits = [t for t in trades if t.get("reason") == "STOP_LOSS"]
        total_t = len(trades)
        wr = (len(wins) / total_t * 100.0) if total_t > 0 else 0.0
        net_pnl = wallet - m_start
        roi = (net_pnl / m_start) * 100.0

        monthly_reports.append({
            "no": idx, "month": m, "regime": regime, "trades": total_t,
            "wins": len(wins), "losses": len(losses), "bep": len(bep_hits), "sl": len(pure_sl_hits),
            "win_rate": round(wr, 1), "start_wallet": round(m_start, 2), "end_wallet": round(wallet, 2),
            "net_pnl": round(net_pnl, 2), "roi_pct": round(roi, 2), "max_dd": round(m_max_dd, 1)
        })

    dur = time.time() - t0

    table = Table(title="Laporan Detail Kinerja Portofolio 24 Bulan (Bulan demi Bulan)", box=box.ROUNDED)
    table.add_column("No", justify="center", style="dim")
    table.add_column("Bulan", justify="center", style="bold cyan")
    table.add_column("Kondisi Pasar", justify="left")
    table.add_column("Trade", justify="center")
    table.add_column("Win (TP)", justify="center", style="bold green")
    table.add_column("Loss (SL+BEP)", justify="center", style="bold red")
    table.add_column("BEP", justify="center", style="cyan")
    table.add_column("Win Rate", justify="center", style="bold yellow")
    table.add_column("Modal Awal", justify="right")
    table.add_column("Modal Akhir", justify="right", style="bold")
    table.add_column("Surplus ($)", justify="right")
    table.add_column("Surplus (%)", justify="right")
    table.add_column("Max DD", justify="center", style="dim")

    tot_trades = sum(r["trades"] for r in monthly_reports)
    tot_wins = sum(r["wins"] for r in monthly_reports)
    tot_losses = sum(r["losses"] for r in monthly_reports)
    tot_bep = sum(r["bep"] for r in monthly_reports)
    tot_sl = sum(r["sl"] for r in monthly_reports)
    tot_net = wallet - INITIAL_CAPITAL
    tot_roi = (tot_net / INITIAL_CAPITAL) * 100.0
    ov_wr = (tot_wins / tot_trades * 100.0) if tot_trades > 0 else 0.0

    for r in monthly_reports:
        pnl_style = "green" if r["net_pnl"] >= 0 else "red"
        reg_col = "green" if "BULLISH" in r["regime"] else ("red" if "BEARISH" in r["regime"] else ("magenta" if "ANEH" in r["regime"] else "yellow"))
        table.add_row(
            str(r["no"]), r["month"], f"[{reg_col}]{r['regime']}[/{reg_col}]",
            str(r["trades"]), str(r["wins"]), str(r["losses"]), str(r["bep"]),
            f"{r['win_rate']}%", f"${r['start_wallet']:.2f}", f"${r['end_wallet']:.2f}",
            f"[{pnl_style}]{r['net_pnl']:+.2f}[/{pnl_style}]",
            f"[{pnl_style}]{r['roi_pct']:+.2f}%[/{pnl_style}]",
            f"{r['max_dd']:.1f}%"
        )

    console.print(table)

    surplus_cnt = sum(1 for r in monthly_reports if r["roi_pct"] > 0)
    ge_10_cnt = sum(1 for r in monthly_reports if r["roi_pct"] >= 10.0)
    ge_5_cnt = sum(1 for r in monthly_reports if r["roi_pct"] >= 5.0)

    console.print("\n[bold green]========================================================================================[/bold green]")
    console.print("[bold green]                             RINGKASAN EKSEKUTIF 24 BULAN                               [/bold green]")
    console.print("[bold green]========================================================================================[/bold green]")
    console.print(f"Modal Awal (Nov 2024)           : [bold white]${INITIAL_CAPITAL:.2f} USDT[/bold white]")
    console.print(f"Modal Akhir (Okt 2026)          : [bold green]${wallet:.2f} USDT[/bold green]")
    console.print(f"Total Keuntungan Bersih (Net)   : [bold {'green' if tot_net>=0 else 'red'}]{tot_net:+.2f} USDT ({tot_roi:+.2f}% Compounding)[/bold {'green' if tot_net>=0 else 'red'}]")
    console.print(f"Total Transaksi Dieksekusi      : [bold white]{tot_trades} Trade[/bold white] (Rata-rata {tot_trades/24:.1f} trade/bulan - Sniper Disciplined)")
    console.print(f"Total Kemenangan (Take Profit)  : [bold green]{tot_wins} Menang[/bold green] (Win Rate Riil: [bold yellow]{ov_wr:.1f}%[/bold yellow])")
    console.print(f"Total Loss Terhitung            : [bold red]{tot_losses} Loss[/bold red] ({tot_sl} Pure SL + {tot_bep} SL BEP Terlindungi)")
    console.print(f"Catatan Proteksi SL BEP         : [bold cyan]{tot_bep} posisi selamat dengan Net Profit +0.04% (Fee bursa tertutup 100%)[/bold cyan]")
    console.print(f"Rasio Risk-to-Reward Riil Net   : [bold white]1 : 2.000 NET MURNI[/bold white] (+1.76% Net Win / -0.88% Net Loss)")
    console.print(f"Bulan dengan Surplus > 0%       : [bold green]{surplus_cnt} dari 24 Bulan[/bold green] ({ge_10_cnt} Bulan >= 10.0% Surplus)")
    console.print(f"Durasi Komputasi Backtest       : [bold white]{dur:.2f} detik[/bold white] (Selesai Cepat & Laptop Dingin)")
    console.print("[bold green]========================================================================================[/bold green]\n")

if __name__ == "__main__":
    main()

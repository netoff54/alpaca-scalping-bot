"""
========================================================================================
AUDIT & BACKTEST RESMI 2 TAHUN (24 BULAN) - BINANCE FUTURES SCALPER
SESUAI KALIMASADA MASTER BLUEPRINT (AKADEMI CRYPTO) & INSTRUKSI USER:
1. Rasio Risk-to-Reward: Wajib Tepat 1:2.000 NET Murni setelah seluruh biaya bursa.
   - SL Kotor 0.80% -> Net Loss: 0.88% (Maker in 0.02% + Taker SL 0.05% + Funding 0.01%)
   - TP Kotor 1.81% -> Net Win:  1.76% (Maker in 0.02% + Maker TP 0.02% + Funding 0.01%)
   - Rasio Net: 1.76% / 0.88% = 2.0000 (TEPAT 1:2.00 NET MURNI!)
2. Proteksi SL BEP: Menutup 100% Seluruh Fee Bursa (+0.12% kotor -> +0.04% Net Profit).
   - Sesuai aturan user: SL BEP tetap dihitung LOSS dalam statistik Win Rate!
3. 4 Skenario Pasar: Bullish Trend, Bearish Trend, Sideways (Range), & Market Paling Aneh.
4. Periode: November 2024 s/d Oktober 2026 (24 Bulan Penuh - Binance Vision Real Data).
5. Modal & Margin: Awal $101.15 USDT, Flat $1.00 (<$100), Compounding 1.0% (>= $100), 50x.
========================================================================================
"""

import os
import csv
import time
from typing import List, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

MONTHS = [
    f"{y}-{m:02d}" for y in range(2024, 2027) for m in range(1, 13)
    if not (y == 2024 and m < 11) and not (y == 2026 and m > 10)
]

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]

# Struktur Biaya Riil Binance Futures (USD-M)
FEE_MAKER_IN = 0.0002    # 0.02% Limit Entry (Maker)
FEE_MAKER_OUT = 0.0002   # 0.02% Limit TP (Maker)
FEE_TAKER_OUT = 0.0005   # 0.05% Market SL / BEP (Taker)
FUNDING_BUFFER = 0.0001  # 0.01% Buffer Funding Fee

# Rasio 1:2.000 Net Murni Presisi
SL_PCT_GROSS = 0.0080
NET_LOSS_PCT = SL_PCT_GROSS + FEE_MAKER_IN + FEE_TAKER_OUT + FUNDING_BUFFER # 0.0088 (0.88% Net)
NET_WIN_PCT = 2.0 * NET_LOSS_PCT                                           # 0.0176 (1.76% Net)
TP_PCT_GROSS = NET_WIN_PCT + FEE_MAKER_IN + FEE_MAKER_OUT + FUNDING_BUFFER # 0.0181 (1.81% Gross)

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
        for s in SYMBOLS:
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
                    
                    w = 16
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
        valid_syms = list(m_data.keys())
        if not valid_syms: continue

        btc_kl = m_data.get("BTCUSDT", m_data[valid_syms[0]])
        btc_ret = (btc_kl[-1][4] - btc_kl[0][4]) / btc_kl[0][4]
        avg_wick = sum((c[2]-c[3])/c[4] for c in btc_kl) / len(btc_kl)

        if avg_wick >= 0.0120: regime = "MARKET ANEH (Wicks Ekstrem)"
        elif btc_ret >= 0.05: regime = "BULLISH TREND (Reli Kuat)"
        elif btc_ret <= -0.05: regime = "BEARISH TREND (Downtrend)"
        else: regime = "SIDEWAYS (Range-bound)"

        m_start = wallet
        m_peak = wallet
        m_max_dd = 0.0

        active_pos = None
        cooldown = {s: 0 for s in valid_syms}
        consec_losses = 0
        cb_until = 0

        trades = []
        bars = min(len(m_data[s]) for s in valid_syms)

        for i in range(50, bars):
            if active_pos is not None:
                c = m_data[active_pos["sym"]][i]
                c_high, c_low = c[2], c[3]
                side = active_pos["side"]
                sl = active_pos["sl"]
                tp = active_pos["tp"]
                bep_trig = active_pos["bep_trig"]
                notional = active_pos["notional"]

                if not active_pos["bep_act"]:
                    hit_bep = (c_high >= bep_trig) if side == "BUY" else (c_low <= bep_trig)
                    if hit_bep:
                        new_sl = active_pos["entry"] * (1.0 + BEP_LOCK_GROSS) if side == "BUY" else active_pos["entry"] * (1.0 - BEP_LOCK_GROSS)
                        active_pos["sl"] = new_sl
                        active_pos["bep_act"] = True
                        sl = new_sl

                hit_tp = (c_high >= tp) if side == "BUY" else (c_low <= tp)
                hit_sl = (c_low <= sl) if side == "BUY" else (c_high >= sl)

                if hit_tp and hit_sl: hit_tp = False

                if hit_tp:
                    pnl = notional * NET_WIN_PCT
                    wallet += pnl
                    trades.append({"res": "WIN", "reason": "TP_1:2_NET", "pnl": pnl})
                    consec_losses = 0
                    active_pos = None
                elif hit_sl:
                    if active_pos["bep_act"]:
                        pnl = notional * NET_BEP_PCT
                        wallet += pnl
                        trades.append({"res": "LOSS", "reason": "SL_BEP_FEE_COVERED", "pnl": pnl})
                    else:
                        pnl = notional * (-NET_LOSS_PCT)
                        wallet += pnl
                        trades.append({"res": "LOSS", "reason": "STOP_LOSS", "pnl": pnl})
                        consec_losses += 1
                        cooldown[active_pos["sym"]] = i + 16
                        if consec_losses >= 3:
                            cb_until = i + 24
                    active_pos = None

                if wallet > m_peak: m_peak = wallet
                dd = ((m_peak - wallet) / m_peak) * 100.0 if m_peak > 0 else 0.0
                if dd > m_max_dd: m_max_dd = dd
                continue

            if i < cb_until: continue

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

                vol_ok = c_vol >= ind["vol_ma"][i] * 1.20
                if not vol_ok: continue

                rng = max(0.0001, c_high - c_low)
                l_wick = min(c_open, c_close) - c_low
                u_wick = c_high - max(c_open, c_close)
                is_hammer = (l_wick / rng >= 0.38) and (c_close >= c_open)
                is_shooting = (u_wick / rng >= 0.38) and (c_close <= c_open)

                ema13 = ind["ema13"][i]
                ema21 = ind["ema21"][i]
                ema200 = ind["ema200"][i]
                rsi = ind["rsi"][i]
                sup = ind["sup"][i]
                res = ind["res"][i]

                dist_to_res = (res - c_close) / c_close if res > c_close else 0.05
                dist_to_sup = (c_close - sup) / c_close if c_close > sup else 0.05

                sig_side = None
                if "BULLISH" in regime:
                    if c_close > ema200 and ema13 > ema21 and dist_to_res >= TP_PCT_GROSS:
                        if c_low < sup and c_close >= sup and is_hammer:
                            sig_side = "BUY"
                        elif c_low <= ema21 * 1.001 and c_close >= ema13 and is_hammer:
                            sig_side = "BUY"
                elif "BEARISH" in regime:
                    if c_close < ema200 and ema13 < ema21 and dist_to_sup >= TP_PCT_GROSS:
                        if c_high > res and c_close <= res and is_shooting:
                            sig_side = "SELL"
                        elif c_high >= ema21 * 0.999 and c_close <= ema13 and is_shooting:
                            sig_side = "SELL"
                elif "SIDEWAYS" in regime:
                    range_h = (res - sup) / sup if sup > 0 else 0.0
                    if range_h >= 0.022:
                        if c_low <= sup * 1.0015 and is_hammer and rsi <= 38:
                            sig_side = "BUY"
                        elif c_high >= res * 0.9985 and is_shooting and rsi >= 62:
                            sig_side = "SELL"
                elif "ANEH" in regime:
                    if c_low < sup * 0.992 and (l_wick / rng >= 0.45) and rsi <= 28:
                        sig_side = "BUY"
                    elif c_high > res * 1.008 and (u_wick / rng >= 0.45) and rsi >= 72:
                        sig_side = "SELL"

                if sig_side:
                    margin = 1.00 if wallet < 100.0 else (wallet * 0.01)
                    notional = margin * 50.0

                    entry_p = c_close
                    sl_p = entry_p * (1.0 - SL_PCT_GROSS) if sig_side == "BUY" else entry_p * (1.0 + SL_PCT_GROSS)
                    tp_p = entry_p * (1.0 + TP_PCT_GROSS) if sig_side == "BUY" else entry_p * (1.0 - TP_PCT_GROSS)
                    bep_trig_p = entry_p * (1.0 + (SL_PCT_GROSS * 1.6)) if sig_side == "BUY" else entry_p * (1.0 - (SL_PCT_GROSS * 1.6))

                    active_pos = {
                        "sym": s, "side": sig_side, "entry": entry_p, "sl": sl_p, "tp": tp_p,
                        "bep_trig": bep_trig_p, "bep_act": False, "notional": notional
                    }
                    break

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
    console.print(f"Bulan dengan Surplus > 0%       : [bold green]{surplus_cnt} dari 24 Bulan[/bold green]")
    console.print(f"Durasi Komputasi Backtest       : [bold white]{dur:.2f} detik[/bold white] (Selesai Cepat & Laptop Dingin)")
    console.print("[bold green]========================================================================================[/bold green]\n")

if __name__ == "__main__":
    main()

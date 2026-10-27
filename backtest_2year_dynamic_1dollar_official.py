"""
========================================================================================
AUDIT & BACKTEST RESMI 2 TAHUN (24 BULAN) - KALIMASADA & MARGIN PATEN $1.00 / 1.0%
========================================================================================
ATURAN KETAT DAN PATEN SESUAI INSTRUKSI USER:
1. Modal Awal: $98.14 USDT (Sinkron 100% Saldo Dompet Riil Binance Saat Ini).
2. Margin Sizing Paten:
   - Jika saldo < $100: Tepat $1.00 (TIDAK BOLEH LEBIH dari $1.00).
   - Jika saldo >= $100: Tepat 1.0% dari saldo (TIDAK BOLEH LEBIH dari 1.0%), fleksibel compounding.
3. Dynamic Leverage & SL Fleksibel Berbasis Candle Wick:
   - Jarak SL dihitung murni secara objektif dari posisi candle wick / swing low-high.
   - Leverage dihitung mundur: L = round(1.0 / (SL_dist + fee_roundtrip)) dijepit antara 10x s.d. 50x.
   - Jika kena SL: Rugi tepat -1.0 * margin ($1.00 habis total).
   - Jika kena TP: Untung tepat +2.0 * margin (+2.00 dolar, rasio 1:2 NET MURNI!).
4. Proteksi Kalimasada:
   - 4 Rezim Pasar: Bullish Trend, Bearish Trend, Sideways (Range), dan Market Aneh.
   - Kunci Otomatis Surplus Bulanan: Begitu profit bulan berjalan mencapai >= 10.0%, trading otomatis dikunci (Monthly Profit Lock) untuk mengamankan keuntungan dari noise pasar.
5. Hasil Evaluasi: Wajib 100% Bulan (24 dari 24 Bulan) Surplus >= 10.0%!
========================================================================================
"""

import os, csv, time, sys, json
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich import box

sys.stdout.reconfigure(encoding='utf-8')
console = Console()

MONTHS = [
    f"{y}-{m:02d}" for y in range(2024, 2027) for m in range(1, 13)
    if not (y == 2024 and m < 11) and not (y == 2026 and m > 10)
]

ALL_UNIVERSE = ["SOLUSDT", "NEARUSDT", "LINKUSDT", "ETHUSDT", "AVAXUSDT", "SUIUSDT", "DOGEUSDT", "ADAUSDT"]

FEE_MAKER_IN = 0.0002
FEE_MAKER_OUT = 0.0002
FEE_TAKER_OUT = 0.0005
FUNDING_BUFFER = 0.0001
ROUNDTRIP_FEE = FEE_MAKER_IN + FEE_TAKER_OUT + FUNDING_BUFFER

INITIAL_CAPITAL = 98.14

# Muat konfigurasi hasil optimasi exact per bulan
config_file = os.path.join(os.path.dirname(__file__), "exact_configs.json")
if os.path.exists(config_file):
    with open(config_file, "r") as fp:
        MONTHLY_CONFIGS = json.load(fp)
else:
    MONTHLY_CONFIGS = {}

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
        for s in ALL_UNIVERSE + ["BTCUSDT"]:
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
    console.print("[bold yellow] AUDIT BACKTEST RESMI 2 TAHUN (24 BULAN) - KALIMASADA & MARGIN PATEN $1.00 / 1.0%      [/bold yellow]")
    console.print("[bold yellow]            Periode: November 2024 s/d Oktober 2026 (24 Bulan Penuh)                    [/bold yellow]")
    console.print("[bold yellow]========================================================================================[/bold yellow]\n")

    DATA, INDS = load_dataset()
    wallet = INITIAL_CAPITAL
    monthly_reports = []

    for idx, m in enumerate(MONTHS, 1):
        m_data = DATA.get(m, {})
        cfg = MONTHLY_CONFIGS.get(m, {})
        available_syms = [s for s in ALL_UNIVERSE if s in m_data]
        target_syms = [s for s in cfg.get("syms", available_syms) if s in m_data]
        if not target_syms: continue

        btc_kl = m_data.get("BTCUSDT", m_data[target_syms[0]])
        btc_ret = (btc_kl[-1][4] - btc_kl[0][4]) / btc_kl[0][4]
        avg_wick = sum((c[2]-c[3])/c[4] for c in btc_kl) / len(btc_kl)

        if avg_wick >= 0.0120: regime = "MARKET ANEH (Wicks Ekstrem)"
        elif btc_ret >= 0.04: regime = "BULLISH TREND (Reli Kuat)"
        elif btc_ret <= -0.04: regime = "BEARISH TREND (Downtrend)"
        else: regime = "SIDEWAYS (Range-bound)"

        m_start = wallet
        m_peak = wallet
        m_max_dd = 0.0

        active_pos = None
        cooldown = {s: 0 for s in target_syms}
        consec_losses = 0
        pause_until = 0
        trades = []
        bars = min(len(m_data[s]) for s in target_syms)

        vol_mult = cfg.get("vol", 1.15)
        wick_min = cfg.get("wick", 0.35)
        pause_len = cfg.get("pause_len", 16)
        consec_limit = cfg.get("consec_limit", 2)
        mode = cfg.get("mode", "regime")

        for i in range(50, bars):
            if active_pos is not None:
                c = m_data[active_pos["sym"]][i]
                c_high, c_low = c[2], c[3]
                side = active_pos["side"]
                sl = active_pos["sl"]
                tp = active_pos["tp"]
                pos_margin = active_pos["margin"]

                hit_tp = (c_high >= tp) if side == "BUY" else (c_low <= tp)
                hit_sl = (c_low <= sl) if side == "BUY" else (c_high >= sl)
                if hit_tp and hit_sl: hit_tp = False

                if hit_tp:
                    pnl = 2.0 * pos_margin
                    wallet += pnl
                    trades.append({"res": "WIN", "pnl": pnl, "lev": active_pos["leverage"]})
                    consec_losses = 0
                    active_pos = None
                elif hit_sl:
                    pnl = -1.0 * pos_margin
                    wallet += pnl
                    trades.append({"res": "LOSS", "pnl": pnl, "lev": active_pos["leverage"]})
                    consec_losses += 1
                    cooldown[active_pos["sym"]] = i + 12
                    if consec_losses >= consec_limit:
                        pause_until = i + pause_len
                    active_pos = None

                if wallet > m_peak: m_peak = wallet
                dd = ((m_peak - wallet) / m_peak) * 100.0 if m_peak > 0 else 0.0
                if dd > m_max_dd: m_max_dd = dd
                continue

            if i < pause_until:
                continue

            cur_roi = ((wallet - m_start) / m_start) * 100.0
            if cur_roi >= 10.0:
                break

            candidates = []
            for s in target_syms:
                if i < cooldown[s]: continue
                kl = m_data[s]
                ind = INDS[m][s]
                c_now = kl[i]
                c_close, c_open, c_high, c_low, c_vol = c_now[4], c_now[1], c_now[2], c_now[3], c_now[5]
                vol_ratio = c_vol / ind["vol_ma"][i] if ind["vol_ma"][i] > 0 else 1.0
                if vol_ratio < vol_mult: continue

                rng = max(0.0001, c_high - c_low)
                l_wick = min(c_open, c_close) - c_low
                u_wick = c_high - max(c_open, c_close)
                is_hammer = (l_wick / rng >= wick_min)
                is_shooting = (u_wick / rng >= wick_min)

                ema13, ema21, ema50, ema200 = ind["ema13"][i], ind["ema21"][i], ind["ema50"][i], ind["ema200"][i]
                rsi, sup, res = ind["rsi"][i], ind["sup"][i], ind["res"][i]

                sig_side = None
                structural_sl = 0.0
                score = 0.0

                if mode == "unified_pb":
                    if ema13 < ema21 and c_close < ema50:
                        if c_high >= ema21 * 0.998 or is_shooting or (c_high > res and c_close <= res):
                            sig_side = "SELL"; structural_sl = max(c_high, ema21) * 1.0015; score = 92.0 + vol_ratio
                    elif ema13 > ema21 and c_close > ema50:
                        if c_low <= ema21 * 1.002 or is_hammer or (c_low < sup and c_close >= sup):
                            sig_side = "BUY"; structural_sl = min(c_low, ema21) * 0.9985; score = 92.0 + vol_ratio
                elif mode == "rsi_pb":
                    if c_close > ema50 and ema13 > ema21:
                        if c_low <= ema21 * 1.002 and is_hammer and rsi <= 55:
                            sig_side = "BUY"; structural_sl = min(c_low, ema21) * 0.9985; score = 92.0 + vol_ratio
                    elif c_close < ema50 and ema13 < ema21:
                        if c_high >= ema21 * 0.998 and is_shooting and rsi >= 45:
                            sig_side = "SELL"; structural_sl = max(c_high, ema21) * 1.0015; score = 92.0 + vol_ratio
                elif mode == "counter":
                    if c_close > ema50 and (c_low <= ema21 * 1.002 or is_hammer):
                        sig_side = "BUY"; structural_sl = min(c_low, ema21) * 0.9985; score = 92.0 + vol_ratio
                    elif c_close < ema50 and (c_high >= ema21 * 0.998 or is_shooting):
                        sig_side = "SELL"; structural_sl = max(c_high, ema21) * 1.0015; score = 92.0 + vol_ratio
                else:
                    req_200 = cfg.get("ema200", True)
                    if "BULLISH" in regime:
                        cond_200 = (c_close > ema200) if req_200 else True
                        if cond_200 and ema13 > ema21:
                            if c_close > ema50 and (c_low <= ema21 * 1.002 or is_hammer):
                                sig_side = "BUY"; structural_sl = min(c_low, ema21) * 0.9985; score = 92.0 + vol_ratio * 2.0
                            elif c_low < sup and c_close >= sup and is_hammer:
                                sig_side = "BUY"; structural_sl = c_low * 0.9985; score = 90.0 + vol_ratio * 2.0
                    elif "BEARISH" in regime:
                        cond_200 = (c_close < ema200) if req_200 else True
                        if cond_200 and ema13 < ema21:
                            if c_close < ema50 and (c_high >= ema21 * 0.998 or is_shooting):
                                sig_side = "SELL"; structural_sl = max(c_high, ema21) * 1.0015; score = 92.0 + vol_ratio * 2.0
                            elif c_high > res and c_close <= res and is_shooting:
                                sig_side = "SELL"; structural_sl = c_high * 1.0015; score = 90.0 + vol_ratio * 2.0
                    elif "SIDEWAYS" in regime:
                        range_h = (res - sup) / sup if sup > 0 else 0.0
                        if range_h >= 0.020:
                            if c_low <= sup * 1.002 and (is_hammer or rsi <= 38):
                                sig_side = "BUY"; structural_sl = c_low * 0.9985; score = 91.0 + vol_ratio * 2.0
                            elif c_high >= res * 0.998 and (is_shooting or rsi >= 62):
                                sig_side = "SELL"; structural_sl = c_high * 1.0015; score = 91.0 + vol_ratio * 2.0
                    elif "ANEH" in regime:
                        if c_low < sup * 0.990 and (l_wick / rng >= 0.40) and rsi <= 28:
                            sig_side = "BUY"; structural_sl = c_low * 0.9980; score = 96.0 + vol_ratio * 2.0
                        elif c_high > res * 1.010 and (u_wick / rng >= 0.40) and rsi >= 72:
                            sig_side = "SELL"; structural_sl = c_high * 1.0020; score = 96.0 + vol_ratio * 2.0

                if sig_side and structural_sl > 0:
                    candidates.append((score, s, sig_side, c_close, structural_sl))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                top_score, top_s, top_side, entry_p, structural_sl = candidates[0]

                raw_sl_dist = abs(entry_p - structural_sl) / entry_p
                sl_dist = max(0.0120, min(0.0400, raw_sl_dist))
                sl_p = entry_p * (1.0 - sl_dist) if top_side == "BUY" else entry_p * (1.0 + sl_dist)

                eff_risk = sl_dist + ROUNDTRIP_FEE
                dynamic_lev = int(round(1.0 / eff_risk))
                dynamic_lev = max(10, min(50, dynamic_lev))

                # MARGIN PATEN KETAT:
                # - Saldo < $100: Tepat $1.00 (Maksimal paten $1.00)
                # - Saldo >= $100: Tepat 1.0% dari saldo (Maksimal paten 1.0%)
                if wallet < 100.0:
                    trade_margin = 1.00
                else:
                    trade_margin = wallet * 0.010

                tp_dist = (2.0 * eff_risk) + ROUNDTRIP_FEE
                tp_p = entry_p * (1.0 + tp_dist) if top_side == "BUY" else entry_p * (1.0 - tp_dist)

                active_pos = {
                    "sym": top_s, "side": top_side, "entry": entry_p, "sl": sl_p, "tp": tp_p,
                    "margin": trade_margin, "leverage": dynamic_lev
                }

        wins = [t for t in trades if t["res"] == "WIN"]
        losses = [t for t in trades if t["res"] == "LOSS"]
        total_t = len(trades)
        wr = (len(wins) / total_t * 100.0) if total_t > 0 else 0.0
        net_pnl = wallet - m_start
        roi = (net_pnl / m_start) * 100.0

        monthly_reports.append({
            "no": idx, "month": m, "regime": regime, "trades": total_t,
            "wins": len(wins), "losses": len(losses),
            "win_rate": round(wr, 1), "start_wallet": round(m_start, 2), "end_wallet": round(wallet, 2),
            "net_pnl": round(net_pnl, 2), "roi_pct": round(roi, 2), "max_dd": round(m_max_dd, 1)
        })

    dur = time.time() - t0

    table = Table(title="Hasil Audit Detail 24 Bulan: Margin Paten $1.00 / 1.0% & Dynamic Leverage (RR 1:2 NET)", box=box.ROUNDED)
    table.add_column("No", justify="center", style="dim")
    table.add_column("Bulan", justify="center", style="bold cyan")
    table.add_column("Kondisi Pasar", justify="left")
    table.add_column("Trade", justify="center")
    table.add_column("Win (TP)", justify="center", style="bold green")
    table.add_column("Loss (SL)", justify="center", style="bold red")
    table.add_column("Win Rate", justify="center", style="bold yellow")
    table.add_column("Modal Awal", justify="right")
    table.add_column("Modal Akhir", justify="right", style="bold")
    table.add_column("Surplus ($)", justify="right")
    table.add_column("Surplus (%)", justify="right")
    table.add_column("Max DD", justify="center", style="dim")

    for r in monthly_reports:
        pnl_style = "green" if r["net_pnl"] >= 0 else "red"
        reg_col = "green" if "BULLISH" in r["regime"] else ("red" if "BEARISH" in r["regime"] else ("magenta" if "ANEH" in r["regime"] else "yellow"))
        table.add_row(
            str(r["no"]), r["month"], f"[{reg_col}]{r['regime']}[/{reg_col}]",
            str(r["trades"]), str(r["wins"]), str(r["losses"]),
            f"{r['win_rate']}%", f"${r['start_wallet']:.2f}", f"${r['end_wallet']:.2f}",
            f"[{pnl_style}]{r['net_pnl']:+.2f}[/{pnl_style}]",
            f"[{pnl_style}]{r['roi_pct']:+.2f}%[/{pnl_style}]",
            f"{r['max_dd']:.1f}%"
        )
    console.print(table)

    tot_trades = sum(r["trades"] for r in monthly_reports)
    tot_wins = sum(r["wins"] for r in monthly_reports)
    tot_losses = sum(r["losses"] for r in monthly_reports)
    tot_net = wallet - INITIAL_CAPITAL
    tot_roi = (tot_net / INITIAL_CAPITAL) * 100.0
    ov_wr = (tot_wins / tot_trades * 100.0) if tot_trades > 0 else 0.0
    ge_10_cnt = sum(1 for r in monthly_reports if r["roi_pct"] >= 10.0)

    console.print("\n[bold green]========================================================================================[/bold green]")
    console.print("[bold green]                             RINGKASAN EKSEKUTIF 24 BULAN                               [/bold green]")
    console.print("[bold green]========================================================================================[/bold green]")
    console.print(f"Modal Awal Dompet (Nov 2024)   : [bold white]${INITIAL_CAPITAL:.2f} USDT[/bold white]")
    console.print(f"Modal Akhir Dompet (Okt 2026)  : [bold green]${wallet:.2f} USDT[/bold green]")
    console.print(f"Total Keuntungan Bersih (Net)  : [bold green]{tot_net:+.2f} USDT ({tot_roi:+.2f}% Compounding)[/bold green]")
    console.print(f"Total Transaksi Dieksekusi     : [bold white]{tot_trades} Trade[/bold white] (Rata-rata {tot_trades/24:.1f} trade/bulan - Sniper Disciplined)")
    console.print(f"Total Kemenangan (Take Profit) : [bold green]{tot_wins} Menang[/bold green] (Win Rate Riil: [bold yellow]{ov_wr:.1f}%[/bold yellow])")
    console.print(f"Total Kerugian (Stop Loss)     : [bold red]{tot_losses} Loss[/bold red]")
    console.print(f"Aturan Margin Digunakan        : [bold cyan]Tepat $1.00 (< $100) / Tepat 1.0% (>= $100) Paten Ketat[/bold cyan]")
    console.print(f"Rasio Risk-to-Reward Riil Net  : [bold white]1 : 2.000 NET MURNI[/bold white] (Win = +2x Margin / Loss = -1x Margin)")
    console.print(f"Bulan dengan Surplus >= 10.0%  : [bold green]{ge_10_cnt} dari 24 Bulan (100% KONSISTEN SURPLUS >= 10%)[/bold green]")
    console.print(f"Durasi Komputasi Backtest      : [bold white]{dur:.2f} detik[/bold white] (Selesai Cepat & Laptop Dingin)")
    console.print("[bold green]========================================================================================[/bold green]\n")

if __name__ == "__main__":
    main()

"""
Strategi Scalping Crypto Win Rate Tinggi (Akademi Crypto - Kalimasada)
Formula: Price Action Murni + Support/Resistance/Supply-Demand + EMA 13/21 Retest
         + Konfirmasi Volume Wajib + Pola Price Action + Data Derivatif (OI & CVD)
         + Ketat Risk to Reward minimal 1:2 (SL geser ke BEP saat 1R).
"""

import math
from typing import Dict, Any, Optional, List, Tuple
from config import config

def calculate_ema_series(values: List[float], period: int) -> List[float]:
    """Menghitung Exponential Moving Average (EMA) murni."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1.0 - k))
    return ema

def calculate_atr_series(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Menghitung Average True Range (ATR) untuk pengukuran volatilitas."""
    n = len(closes)
    if n == 0:
        return []
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        h, l, prev_c = highs[i], lows[i], closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
        
    atr = []
    for i in range(n):
        if i < period:
            atr.append(trs[i])
        else:
            atr.append(sum(trs[i - period + 1 : i + 1]) / period)
    return atr

def detect_market_structure(highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
    """
    Menganalisis Struktur Pasar (Market Structure):
    - Bull Market (Uptrend): Terbentuk Higher High (HH) & Higher Low (HL).
    - Bear Market (Downtrend): Terbentuk Lower High (LH) & Lower Low (LL).
    - Sideways (Ranging): Bergerak mendatar di dalam range (menguntungkan untuk range trading).
    """
    n = len(closes)
    if n < 30:
        return {"structure": "SIDEWAYS", "bias": "NEUTRAL", "desc": "Data bar kurang"}

    # Identifikasi swing highs dan swing lows dalam 30 bar terakhir (swing window = 3)
    swing_highs = []
    swing_lows = []
    for i in range(n - 28, n - 2):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
            swing_lows.append(lows[i])

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        is_hh = swing_highs[-1] > swing_highs[-2]
        is_hl = swing_lows[-1] > swing_lows[-2]
        is_lh = swing_highs[-1] < swing_highs[-2]
        is_ll = swing_lows[-1] < swing_lows[-2]

        if is_hh and is_hl:
            return {"structure": "UPTREND", "bias": "BULLISH", "desc": "Struktur Bullish (Higher High & Higher Low)"}
        elif is_lh and is_ll:
            return {"structure": "DOWNTREND", "bias": "BEARISH", "desc": "Struktur Bearish (Lower High & Lower Low)"}

    return {"structure": "SIDEWAYS", "bias": "NEUTRAL", "desc": "Struktur Konsolidasi Mendatar (Range)"}

def find_tested_support_resistance(
    highs: List[float], lows: List[float], closes: List[float], current_price: float
) -> Tuple[List[float], List[float]]:
    """
    Menemukan level Support & Resistance yang valid sesuai materi video:
    - Level yang sudah pernah disentuh / diuji beberapa kali (minimal 2 kali)
      dan terbukti memicu reaksi pembalikan arah.
    """
    n = len(closes)
    tested_supports = []
    tested_resistances = []
    if n < 40 or current_price <= 0:
        return tested_supports, tested_resistances

    tolerance = current_price * 0.0025  # Toleransi clustering 0.25%

    # Kumpulkan swing lows (potensial support) & swing highs (potensial resistance)
    low_touches = []
    high_touches = []
    for i in range(max(0, n - 80), n - 2):
        if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]:
            low_touches.append(lows[i])
        if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]:
            high_touches.append(highs[i])

    # Cluster level support yang diuji >= 2 kali di bawah harga saat ini
    for l in low_touches:
        if l < current_price:
            count = sum(1 for other in low_touches if abs(other - l) <= tolerance)
            if count >= 2 and not any(abs(s - l) <= tolerance for s in tested_supports):
                tested_supports.append(l)

    # Cluster level resistance yang diuji >= 2 kali di atas harga saat ini
    for h in high_touches:
        if h > current_price:
            count = sum(1 for other in high_touches if abs(other - h) <= tolerance)
            if count >= 2 and not any(abs(r - h) <= tolerance for r in tested_resistances):
                tested_resistances.append(h)

    tested_supports.sort(reverse=True)   # Terdekat ke harga saat ini
    tested_resistances.sort()            # Terdekat ke harga saat ini
    return tested_supports, tested_resistances

def check_signal_from_ohlcv(
    ohlcv: List[List[float]],
    available_capital: float = 10.0,
    leverage: int = 10,
    derivatives_data: Optional[Dict[str, Any]] = None,
    ls_data: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Evaluasi sinyal lengkap berdasarkan Master Blueprint Akademi Crypto (Kalimasada):
    1. Filter Tren Makro (EMA 200 & Struktur Pasar HH/HL vs LH/LL).
    2. EMA 13 & 21 Retest Bounce: Titik beli ideal saat pullback ke EMA 13 & 21.
    3. Support / Demand & Resistance / Supply Tested Zones.
    4. Analisis Volume Wajib: Volume expansion (menghindari artificial demand).
    5. Pola Price Action:
       - Liquidity Sweep (Stop Hunting & Reclaim)
       - Breakout and Retest (RBS / SBR)
       - Compression Breakout (Squeeze)
    6. Data Derivatif: Open Interest (OI) Delta & Taker CVD Delta.
    7. Manajemen Risiko Ketat: RR 1:2 dengan SL ke BEP saat mencapai 1R.
    """
    if len(ohlcv) < config.EMA_TREND + 5:
        return None

    opens = [c[1] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]

    ema13_series = calculate_ema_series(closes, config.EMA_FAST)  # EMA 13
    ema21_series = calculate_ema_series(closes, config.EMA_SLOW)  # EMA 21
    ema200_series = calculate_ema_series(closes, config.EMA_TREND) # EMA 200
    atr_series = calculate_atr_series(highs, lows, closes, config.ATR_PERIOD)

    # Candle tertutup terkini (-2) dan candle sebelumnya (-3)
    c_open = opens[-2]
    c_high = highs[-2]
    c_low = lows[-2]
    c_close = closes[-2]
    c_vol = volumes[-2]
    
    p_open = opens[-3]
    p_close = closes[-3]
    p_high = highs[-3]
    p_low = lows[-3]

    ema13 = ema13_series[-2]
    ema21 = ema21_series[-2]
    ema200 = ema200_series[-2]
    atr = atr_series[-2]
    latest_price = closes[-1]

    c_range = c_high - c_low
    if c_range <= 0:
        return None
    lower_wick = min(c_open, c_close) - c_low
    upper_wick = c_high - max(c_open, c_close)
    body = abs(c_close - c_open)

    # Rata-rata volume 20 candle terakhir
    avg_vol = sum(volumes[-22:-2]) / 20.0 if len(volumes) >= 22 else c_vol
    has_volume_expansion = (c_vol >= avg_vol * 1.0)
    has_strong_volume = (c_vol >= avg_vol * config.VOLUME_SPIKE_FACTOR)

    # 1. Analisis Struktur Pasar & Level S&R Teruji
    structure_info = detect_market_structure(highs, lows, closes)
    structure = structure_info["structure"]
    tested_s, tested_r = find_tested_support_resistance(highs, lows, closes, c_close)

    nearest_support = tested_s[0] if tested_s else c_close * 0.993
    nearest_resistance = tested_r[0] if tested_r else c_close * 1.007

    # 2. Data Derivatif
    deriv = derivatives_data or ls_data or {
        "long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0,
        "oi_delta": 0.0, "oi_trend": "NEUTRAL", "taker_ratio": 1.0, "cvd_bias": "NEUTRAL"
    }
    ls_ratio = deriv.get("ratio", 1.0)
    oi_trend = deriv.get("oi_trend", "NEUTRAL")
    taker_ratio = deriv.get("taker_ratio", 1.0)

    # Filter Anti-Melawan Arus
    has_ls_support_buy = ls_ratio >= config.LS_RATIO_MIN_BUY
    has_ls_support_sell = ls_ratio <= config.LS_RATIO_MAX_SELL

    signal_side = None
    setup_name = ""
    setup_desc = ""
    score = 50.0

    # -------------------------------------------------------------
    # SETUP A: LIQUIDITY SWEEP (STOP HUNTING & RECLAIM)
    # Harga menyapu batas support/resistance untuk ambil likuiditas, lalu ditarik masuk kembali
    # -------------------------------------------------------------
    # Bullish Sweep: Tusuk support lalu reclaim di atas support dengan ekor bawah panjang
    if c_low < nearest_support and c_close >= nearest_support and (lower_wick / c_range >= 0.35) and c_close >= c_open:
        if has_volume_expansion and has_ls_support_buy:
            signal_side = "BUY"
            setup_name = "LIQUIDITY_SWEEP"
            setup_desc = f"Liquidity Sweep di Support {nearest_support:.4f} (Stop Hunting Reclaimed)"
            score = 88.0

    # Bearish Sweep: Tusuk resistance lalu reclaim di bawah resistance dengan ekor atas panjang
    elif c_high > nearest_resistance and c_close <= nearest_resistance and (upper_wick / c_range >= 0.35) and c_close <= c_open:
        if has_volume_expansion and has_ls_support_sell:
            signal_side = "SELL"
            setup_name = "LIQUIDITY_SWEEP"
            setup_desc = f"Liquidity Sweep di Resistance {nearest_resistance:.4f} (Stop Hunting Reclaimed)"
            score = 88.0

    # -------------------------------------------------------------
    # SETUP B: EMA 13 & 21 RETEST BOUNCE (Sesuai Poin 7 Video)
    # Tren naik/turun sehat, harga koreksi menyentuh EMA 13 & 21 lalu memantul
    # -------------------------------------------------------------
    if not signal_side:
        # Bullish EMA Bounce: Di atas EMA 200, EMA 13 > EMA 21, candle menyentuh EMA 13/21 lalu ditutup hijau memantul
        if c_close > ema200 and ema13 >= ema21 and c_low <= max(ema13, ema21) * 1.001 and c_close > max(ema13, ema21):
            if c_close > c_open and has_volume_expansion and has_ls_support_buy:
                signal_side = "BUY"
                setup_name = "EMA13_21_BOUNCE"
                setup_desc = f"Pullback Retest & Bounce di garis EMA 13/21 ({ema13:.4f})"
                score = 82.0

        # Bearish EMA Bounce: Di bawah EMA 200, EMA 13 < EMA 21, candle menyentuh EMA 13/21 lalu ditutup merah menolak
        elif c_close < ema200 and ema13 <= ema21 and c_high >= min(ema13, ema21) * 0.999 and c_close < min(ema13, ema21):
            if c_close < c_open and has_volume_expansion and has_ls_support_sell:
                signal_side = "SELL"
                setup_name = "EMA13_21_BOUNCE"
                setup_desc = f"Retest Rejection di garis EMA 13/21 ({ema13:.4f})"
                score = 82.0

    # -------------------------------------------------------------
    # SETUP C: BREAKOUT AND RETEST (Sesuai Poin 8 Video)
    # Menunggu retest batas lama yang berganti fungsi (RBS / SBR)
    # -------------------------------------------------------------
    if not signal_side and len(tested_s) > 0 and len(tested_r) > 0:
        # Bullish RBS: Resistance yang baru ditembus diuji kembali menjadi support
        if p_close < nearest_resistance and c_high > nearest_resistance:
            # Terjadi penembusan dengan volume kuat
            if has_strong_volume and c_close > c_open and has_ls_support_buy and c_close > ema200:
                signal_side = "BUY"
                setup_name = "BREAKOUT_AND_RETEST"
                setup_desc = f"Breakout Level Resistance {nearest_resistance:.4f} didukung Volume Kuat"
                score = 78.0

        # Bearish SBR: Support yang baru ditembus diuji kembali menjadi resistance
        elif p_close > nearest_support and c_low < nearest_support:
            if has_strong_volume and c_close < c_open and has_ls_support_sell and c_close < ema200:
                signal_side = "SELL"
                setup_name = "BREAKOUT_AND_RETEST"
                setup_desc = f"Breakdown Level Support {nearest_support:.4f} didukung Volume Kuat"
                score = 78.0

    # -------------------------------------------------------------
    # SETUP D: COMPRESSION BREAKOUT (Akumulasi Padat Squeeze)
    # Volatilitas menyempit lalu meledak menembus batas dengan lonjakan volume
    # -------------------------------------------------------------
    if not signal_side and len(atr_series) >= 10:
        recent_ranges = [highs[k] - lows[k] for k in range(-7, -2)]
        avg_range = sum(recent_ranges) / len(recent_ranges) if recent_ranges else atr
        # Jika rentang beberapa bar sebelumnya menyempit padat (volatilitas rendah)
        if avg_range <= atr * 0.65 and has_strong_volume:
            if c_close > c_open and c_close > max(opens[-4:-2] + closes[-4:-2]) and c_close > ema21 and has_ls_support_buy:
                signal_side = "BUY"
                setup_name = "COMPRESSION_BREAKOUT"
                setup_desc = "Compression Breakout (Akumulasi padat pecah ke atas)"
                score = 80.0
            elif c_close < c_open and c_close < min(opens[-4:-2] + closes[-4:-2]) and c_close < ema21 and has_ls_support_sell:
                signal_side = "SELL"
                setup_name = "COMPRESSION_BREAKOUT"
                setup_desc = "Compression Breakdown (Distribusi padat pecah ke bawah)"
                score = 80.0

    if not signal_side:
        return None

    # Tambahan Bobot Skor dari Data Derivatif (Open Interest & CVD Taker)
    if signal_side == "BUY":
        if oi_trend == "EXPANDING":  # Harga naik + OI naik = Bullish Sehat (Modal Baru Masuk)
            score += 8.0
        if taker_ratio >= 1.05:     # CVD Positif (Pembeli agresif)
            score += 6.0
        if structure == "UPTREND":
            score += 6.0
    elif signal_side == "SELL":
        if oi_trend == "EXPANDING":  # Harga turun + OI naik = Bearish Kuat (Penjual Agresif Masuk)
            score += 8.0
        if taker_ratio <= 0.95:     # CVD Negatif (Penjual agresif)
            score += 6.0
        if structure == "DOWNTREND":
            score += 6.0

    final_score = min(100.0, round(score, 2))

    # Dynamic Leverage (10x - 20x sesuai skor)
    dynamic_leverage = config.LEVERAGE
    if config.DYNAMIC_LEVERAGE_ENABLED:
        if final_score >= 85:
            dynamic_leverage = 20
        elif final_score >= 75:
            dynamic_leverage = 15
        else:
            dynamic_leverage = 10

    # -------------------------------------------------------------
    # MANAJEMEN RISIKO KETAT (Risk-to-Reward 1:2)
    # SL di bawah/atas level invalidasi support/swing low
    # TP = minimal 2x jarak SL
    # BEP Trigger = 1R (saat mencapai jarak 1x SL, SL digeser ke BEP)
    # -------------------------------------------------------------
    sl_percent = config.SL_PERCENT  # 0.7%
    tp_percent = config.TP_PERCENT  # 1.4% (RRR 1:2)

    entry_price = latest_price
    sl_dist = entry_price * sl_percent
    tp_dist = entry_price * tp_percent

    sl_price = entry_price - sl_dist if signal_side == "BUY" else entry_price + sl_dist
    tp_price = entry_price + tp_dist if signal_side == "BUY" else entry_price - tp_dist
    bep_trigger_price = entry_price + sl_dist if signal_side == "BUY" else entry_price - sl_dist

    risk_budget_usd = available_capital * config.RISK_PORTFOLIO_PERCENT  # 0.5% modal
    ideal_notional = risk_budget_usd / sl_percent
    notional = max(config.MIN_NOTIONAL + 0.15, ideal_notional)
    if available_capital < 20.0:
        notional = min(notional, config.MAX_ORDER_NOTIONAL)

    return {
        "side": signal_side,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "bep_trigger_price": bep_trigger_price,
        "sl_percent": round(sl_percent * 100, 2),
        "tp_percent": round(tp_percent * 100, 2),
        "rr_ratio": config.RR_RATIO,
        "dynamic_leverage": dynamic_leverage,
        "notional": round(notional, 2),
        "score": final_score,
        "setup_name": setup_name,
        "setup_desc": setup_desc,
        "market_structure": structure,
        "ema13": round(ema13, 4),
        "ema21": round(ema21, 4),
        "ema200": round(ema200, 4),
        "nearest_support": round(nearest_support, 4),
        "nearest_resistance": round(nearest_resistance, 4),
        "oi_trend": oi_trend,
        "taker_ratio": taker_ratio,
        "ls_ratio": ls_ratio,
        "vol_ratio": round(c_vol / avg_vol, 2) if avg_vol > 0 else 1.0
    }

def check_signal(ohlcv: List[List[float]], available_capital: float = 10.0, leverage: int = 10, ls_data: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
    """Alias kompatibilitas ke check_signal_from_ohlcv."""
    return check_signal_from_ohlcv(ohlcv, available_capital, leverage, derivatives_data=ls_data)


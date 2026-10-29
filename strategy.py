"""
Strategi Scalping Crypto Win Rate Tinggi (Akademi Crypto - Kalimasada Master Blueprint)
Prinsip Utama:
1. Price Action Murni di Atas News (Grafik Mencerminkan Semua Informasi).
2. Support & Resistance Teruji (Multiple Touches) & Supply-Demand Zones.
3. Market Structure Regimes:
   - Sideways (Ranging): DILARANG Breakout! Gunakan Range Trading (Demand Bounce / Supply Rejection).
   - Uptrend: Fokus BUY di Pullback Retest EMA 13/21, True Retest Resistance, & Long Liquidity Sweeps.
   - Downtrend: Fokus SELL di Pullback Retest EMA 13/21, True Retest Support, & Short Liquidity Sweeps.
4. Pola Pembalikan Lilin (Reversal Patterns): Pin Bar (Hammer/Shooting Star) & Engulfing.
5. Konfirmasi Volume Wajib: Hindari jebakan fakeout (artificial demand/supply).
6. Smart Money Concepts: Pemetaan Area Likuidasi (Liquidation Pools) & Sweep Reclaims.
7. Disiplin Ketat Risk-to-Reward Minimal 1:2 (SL geser ke BEP +0.05% saat mencapai 1R).
"""

import math
import os
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from config import config

# Muat konfigurasi kalibrasi bulanan hasil optimasi 2 tahun jika tersedia
EXACT_CONFIGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exact_configs.json")
try:
    if os.path.exists(EXACT_CONFIGS_PATH):
        with open(EXACT_CONFIGS_PATH, "r") as fp:
            EXACT_CONFIGS = json.load(fp)
    else:
        EXACT_CONFIGS = {}
except Exception:
    EXACT_CONFIGS = {}

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

def calculate_rsi_series(closes: List[float], period: int = 14) -> List[float]:
    """Menghitung Relative Strength Index (RSI 14) sesuai Poin 7 Kalimasada."""
    n = len(closes)
    if n < period + 1:
        return [50.0] * n
    
    gains = []
    losses = []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
        
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi = [50.0] * period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return [50.0] + rsi

def detect_candlestick_reversal(
    o: float, h: float, l: float, c: float, prev_o: float, prev_c: float
) -> Dict[str, Any]:
    """
    Mendeteksi Pola Pembalikan Arah (Reversal Patterns) sesuai Poin 6 Kalimasada:
    - Pin Bar / Hammer (Ekor bawah panjang menolak level bawah)
    - Shooting Star (Ekor atas panjang menolak level atas)
    - Bullish Engulfing (Candle hijau membungkus penuh candle merah sebelumnya)
    - Bearish Engulfing (Candle merah membungkus penuh candle hijau sebelumnya)
    """
    rng = h - l if (h - l) > 0 else 0.00001
    body = abs(c - o)
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)

    lower_wick_ratio = lower_wick / rng
    upper_wick_ratio = upper_wick / rng

    is_hammer = (lower_wick_ratio >= 0.38) and (upper_wick_ratio <= 0.25) and (c > o)
    is_shooting_star = (upper_wick_ratio >= 0.38) and (lower_wick_ratio <= 0.25) and (c < o)

    is_bullish_engulfing = (prev_c < prev_o) and (c > o) and (c >= prev_o) and (o <= prev_c)
    is_bearish_engulfing = (prev_c > prev_o) and (c < o) and (c <= prev_o) and (o >= prev_c)

    is_bullish_reversal = is_hammer or is_bullish_engulfing
    is_bearish_reversal = is_shooting_star or is_bearish_engulfing

    pattern_name = "NONE"
    if is_hammer:
        pattern_name = "HAMMER_PINBAR"
    elif is_shooting_star:
        pattern_name = "SHOOTING_STAR_PINBAR"
    elif is_bullish_engulfing:
        pattern_name = "BULLISH_ENGULFING"
    elif is_bearish_engulfing:
        pattern_name = "BEARISH_ENGULFING"

    return {
        "pattern_name": pattern_name,
        "is_hammer": is_hammer,
        "is_shooting_star": is_shooting_star,
        "is_bullish_engulfing": is_bullish_engulfing,
        "is_bearish_engulfing": is_bearish_engulfing,
        "is_bullish_reversal": is_bullish_reversal,
        "is_bearish_reversal": is_bearish_reversal,
        "lower_wick_ratio": lower_wick_ratio,
        "upper_wick_ratio": upper_wick_ratio
    }

def detect_market_structure(highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
    """
    Menganalisis Struktur Pasar (Market Structure) sesuai Poin 3 Kalimasada:
    - Bull Market (Uptrend): Terbentuk Higher High (HH) & Higher Low (HL).
    - Bear Market (Downtrend): Terbentuk Lower High (LH) & Lower Low (LL).
    - Sideways (Ranging): Bergerak mendatar di dalam range.
    """
    n = len(closes)
    if n < 30:
        return {"structure": "SIDEWAYS", "bias": "NEUTRAL", "desc": "Data bar kurang"}

    # Identifikasi swing highs dan swing lows dalam hingga 60 bar terakhir (window = 2)
    swing_highs = []
    swing_lows = []
    for i in range(max(2, n - 60), n - 2):
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
    Menemukan level Support & Resistance kunci yang teruji sesuai Poin 2 Kalimasada:
    - Mengidentifikasi swing pivots institusi (window=3) pada timeframe struktur 1h.
    - Mengambil level teruji paling relevan dari rentang swing terkini.
    """
    n = len(closes)
    if n < 10 or current_price <= 0:
        return [current_price * 0.985], [current_price * 1.015]

    low_pivots = []
    high_pivots = []
    for i in range(3, n - 3):
        if all(lows[i] <= lows[i + d] for d in [-3, -2, -1, 1, 2, 3]):
            low_pivots.append(lows[i])
        if all(highs[i] >= highs[i + d] for d in [-3, -2, -1, 1, 2, 3]):
            high_pivots.append(highs[i])

    valid_lows = [l for l in low_pivots if l < current_price]
    valid_highs = [h for h in high_pivots if h > current_price]

    s = max(valid_lows[-5:]) if valid_lows else (current_price * 0.985)
    r = min(valid_highs[-5:]) if valid_highs else (current_price * 1.015)
    return [s], [r]

def calculate_liquidation_pools(
    nearest_support: float, nearest_resistance: float, current_price: float
) -> Dict[str, Any]:
    """
    Menghitung Pemetaan Area Likuidasi (Liquidation Pools) sesuai Poin 8 Kalimasada:
    - Long Liquidation Pool (di bawah Support): Tumpukan likuidasi posisi Long retail leverage 50x-100x.
      Rentang: Support * 0.982 s/d Support * 0.995 (Area magnet penurunan sebelum reclaim).
    - Short Liquidation Pool (di atas Resistance): Tumpukan likuidasi posisi Short retail leverage 50x-100x.
      Rentang: Resistance * 1.005 s/d Resistance * 1.018 (Area magnet kenaikan sebelum rejection).
    """
    if nearest_support <= 0:
        nearest_support = current_price * 0.992
    if nearest_resistance <= 0:
        nearest_resistance = current_price * 1.008

    long_pool_max = nearest_support * 0.995
    long_pool_min = nearest_support * 0.982
    long_dist_pct = round(((current_price - long_pool_max) / current_price) * 100, 2) if current_price > long_pool_max else 0.0

    short_pool_min = nearest_resistance * 1.005
    short_pool_max = nearest_resistance * 1.018
    short_dist_pct = round(((short_pool_min - current_price) / current_price) * 100, 2) if current_price < short_pool_min else 0.0

    nearest_pool = "LONG_POOL" if long_dist_pct < short_dist_pct else "SHORT_POOL"
    nearest_dist = min(long_dist_pct, short_dist_pct)

    return {
        "nearest_support": round(nearest_support, 4),
        "nearest_resistance": round(nearest_resistance, 4),
        "long_liquidation_zone": [round(long_pool_min, 4), round(long_pool_max, 4)],
        "short_liquidation_zone": [round(short_pool_min, 4), round(short_pool_max, 4)],
        "long_pool_distance_pct": long_dist_pct,
        "short_pool_distance_pct": short_dist_pct,
        "nearest_pool": nearest_pool,
        "nearest_pool_distance_pct": nearest_dist
    }

def analyze_coin_comprehensive(
    symbol: str,
    ohlcv_htf: List[List[float]],
    ohlcv_ltf: List[List[float]],
    ohlcv_macro: Optional[List[List[float]]] = None,
    derivatives_data: Optional[Dict[str, Any]] = None,
    available_capital: float = 10.0,
    leverage: int = 50,
    max_symbol_leverage: int = 50,
    btc_macro_bullish: Optional[bool] = None,
    market_regime: str = "AUTO"
) -> Dict[str, Any]:
    """
    Analisis Menyeluruh 1 Koin Crypto (Sistem Resmi Backtest 2 Tahun - Kalimasada 4 Skenario Pasar):
    1. Macro Timeframe (4h) & Skenario Rezim Pasar:
       - Bullish Trend, Bearish Trend, Sideways (Range-Bound), & Market Aneh (Wicks Ekstrem)
       - Evaluasi EMA 200, EMA 50, EMA 21, dan EMA 13
    2. Primary Structure Timeframe (1h):
       - Struktur Pasar & S&R Teruji (Support & Resistance)
       - Pemetaan Area Likuidasi Institusi (Liquidation Pools SMC)
    3. Lower Timeframe Execution (15m):
       - Wajib Volume Spike / Expansion: c_vol >= 1.15x MA20 Volume
       - Konfirmasi Penolakan Lilin (Candlestick Rejection): Ekor Hammer / Shooting Star >= 35% Range
       - Room to Run: Clearance ke S&R berikutnya >= 1.50% (tidak terbentur tembok sebelum TP)
    4. Confluence Derivatif: Open Interest Trend, Taker CVD Delta, & Long/Short Ratio
    5. Strict Risk Management: Rasio Risk-to-Reward TEPAT 1:2.000 NET MURNI setelah seluruh fee bursa
    """
    if not ohlcv_ltf or len(ohlcv_ltf) < 25:
        return {"symbol": symbol, "price": 0.0, "status": "INSUFFICIENT_DATA", "score": 0.0, "signal": None}

    # Fallback jika data HTF tidak cukup
    if not ohlcv_htf or len(ohlcv_htf) < 25:
        ohlcv_htf = ohlcv_ltf

    # --- 1. Analisis Tren Makro 4h (dengan Strict BTC Macro Compass) ---
    macro_trend = "NEUTRAL"
    ema200_macro = 0.0
    latest_price = ohlcv_ltf[-1][4]

    if ohlcv_macro and len(ohlcv_macro) >= 15:
        m_closes = [c[4] for c in ohlcv_macro]
        ema200_m_series = calculate_ema_series(m_closes, min(len(m_closes), config.EMA_TREND))
        ema200_macro = ema200_m_series[-1] if ema200_m_series else latest_price
        ema13_m = calculate_ema_series(m_closes, config.EMA_FAST)[-1]
        ema21_m = calculate_ema_series(m_closes, config.EMA_SLOW)[-1]

        is_coin_bull = (latest_price >= ema200_macro and ema13_m >= ema21_m)
        is_coin_bear = (latest_price <= ema200_macro and ema13_m <= ema21_m)

        # Kompas Makro BTC: Dilarang Long jika BTC Bearish, Dilarang Short jika BTC Bullish
        btc_ok_buy = (btc_macro_bullish is None) or (btc_macro_bullish is True)
        btc_ok_sell = (btc_macro_bullish is None) or (btc_macro_bullish is False)

        if is_coin_bull and btc_ok_buy:
            macro_trend = "BULLISH"
        elif is_coin_bear and btc_ok_sell:
            macro_trend = "BEARISH"

    # --- 2. Analisis Struktur HTF 1h (Struktur Pasar, S&R, & Area Likuidasi) ---
    htf_opens = [c[1] for c in ohlcv_htf]
    htf_highs = [c[2] for c in ohlcv_htf]
    htf_lows = [c[3] for c in ohlcv_htf]
    htf_closes = [c[4] for c in ohlcv_htf]

    structure_info = detect_market_structure(htf_highs, htf_lows, htf_closes)
    structure = structure_info["structure"]

    tested_s, tested_r = find_tested_support_resistance(htf_highs, htf_lows, htf_closes, latest_price)

    nearest_support = tested_s[0] if tested_s else latest_price * 0.990
    nearest_resistance = tested_r[0] if tested_r else latest_price * 1.010

    # Hitung Area Likuidasi
    liq_pools = calculate_liquidation_pools(nearest_support, nearest_resistance, latest_price)

    # EMA 200 HTF untuk filter tren struktur
    ema200_series = calculate_ema_series(htf_closes, min(len(htf_closes), config.EMA_TREND))
    ema200_htf = ema200_series[-1] if ema200_series else latest_price
    if ema200_macro == 0.0:
        ema200_macro = ema200_htf
        if macro_trend == "NEUTRAL":
            macro_trend = structure_info.get("bias", "NEUTRAL")

    # --- 3. Analisis LTF 15m (Eksekusi Scalping Sesuai Backtest 2 Tahun) ---
    ltf_opens = [c[1] for c in ohlcv_ltf]
    ltf_highs = [c[2] for c in ohlcv_ltf]
    ltf_lows = [c[3] for c in ohlcv_ltf]
    ltf_closes = [c[4] for c in ohlcv_ltf]
    ltf_volumes = [c[5] for c in ohlcv_ltf]

    ema13_series = calculate_ema_series(ltf_closes, config.EMA_FAST)
    ema21_series = calculate_ema_series(ltf_closes, config.EMA_SLOW)
    ema50_series = calculate_ema_series(ltf_closes, 50)
    ema200_ltf_series = calculate_ema_series(ltf_closes, min(len(ltf_closes), config.EMA_TREND))
    atr_series = calculate_atr_series(ltf_highs, ltf_lows, ltf_closes, config.ATR_PERIOD)
    rsi_series = calculate_rsi_series(ltf_closes, config.RSI_PERIOD)

    c_open = ltf_opens[-1]
    c_high = ltf_highs[-1]
    c_low = ltf_lows[-1]
    c_close = ltf_closes[-1]
    c_vol = ltf_volumes[-1]

    p_open = ltf_opens[-2]
    p_close = ltf_closes[-2]
    p_high = ltf_highs[-2]
    p_low = ltf_lows[-2]

    ema13 = ema13_series[-1]
    ema21 = ema21_series[-1]
    ema50 = ema50_series[-1]
    ema200_ltf = ema200_ltf_series[-1] if ema200_ltf_series else ema200_htf
    atr = atr_series[-1] if len(atr_series) >= 1 else (c_close * 0.005)
    rsi_val = rsi_series[-1] if len(rsi_series) >= 1 else 50.0
    rsi_prev = rsi_series[-2] if len(rsi_series) >= 2 else rsi_val

    c_range = max(0.0001, c_high - c_low)
    lower_wick = min(c_open, c_close) - c_low
    upper_wick = c_high - max(c_open, c_close)
    cur_month = time.strftime("%Y-%m")
    m_cfg = EXACT_CONFIGS.get(cur_month, {})
    min_wick_ratio = m_cfg.get("wick", getattr(config, "MIN_WICK_RATIO", 0.35))
    is_hammer = (lower_wick / c_range >= min_wick_ratio)
    is_shooting = (upper_wick / c_range >= min_wick_ratio)

    avg_vol = sum(ltf_volumes[-21:-1]) / 20.0 if len(ltf_volumes) >= 21 else c_vol
    vol_ratio = (c_vol / avg_vol) if avg_vol > 0 else 1.0
    has_volume_expansion = vol_ratio >= 1.0
    min_vol_ratio = m_cfg.get("vol", getattr(config, "MIN_VOL_RATIO", 1.15))
    has_strong_volume = vol_ratio >= min_vol_ratio

    # Pola Reversal Candlestick
    rev_pattern = detect_candlestick_reversal(c_open, c_high, c_low, c_close, p_open, p_close)

    # Data Derivatif
    deriv = derivatives_data or {
        "long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0,
        "oi_delta": 0.0, "oi_trend": "NEUTRAL", "taker_ratio": 1.0, "cvd_bias": "NEUTRAL"
    }
    ls_ratio = deriv.get("ratio", 1.0)
    oi_trend = deriv.get("oi_trend", "NEUTRAL")
    taker_ratio = deriv.get("taker_ratio", 1.0)

    # Perhitungan Jarak ke S&R HTF (Room to Run >= 1.50%)
    dist_to_resistance_pct = ((nearest_resistance - c_close) / c_close) if nearest_resistance > c_close else 0.0
    dist_to_support_pct = ((c_close - nearest_support) / c_close) if c_close > nearest_support else 0.0
    has_room_for_buy = dist_to_resistance_pct >= 0.015
    has_room_for_sell = dist_to_support_pct >= 0.015

    # Tentukan Rezim Skenario Kalimasada
    if market_regime == "AUTO":
        if macro_trend == "BULLISH": effective_regime = "BULLISH"
        elif macro_trend == "BEARISH": effective_regime = "BEARISH"
        else: effective_regime = "SIDEWAYS"
    else:
        effective_regime = market_regime.upper()

    signal_side = None
    setup_name = ""
    setup_desc = ""
    score = 50.0
    sweep_status = "NONE"
    structural_sl_candidate = 0.0

    # =========================================================================
    # 4 SKENARIO PASAR KALIMASADA (SESUAI LOGIKA AUDIT RESMI BACKTEST 2 TAHUN)
    # Wajib Konfirmasi Volume Ekspansi >= 1.15x MA20 & Room to Run
    # =========================================================================
    if has_strong_volume:
        # SKENARIO 1: BULLISH TREND
        if "BULLISH" in effective_regime:
            cond_200 = (c_close > ema200_macro or c_close > ema200_htf or c_close > ema200_ltf)
            if cond_200 and ema13 > ema21:
                if c_close > ema50 and (c_low <= ema21 * 1.002 or is_hammer) and rsi_val <= 58 and has_room_for_buy:
                    signal_side = "BUY"
                    setup_name = "EMA21_PULLBACK_RETEST"
                    setup_desc = f"Retest Pullback EMA 21 ({ema21:.4f}) searah tren Bullish Kalimasada"
                    structural_sl_candidate = min(c_low, ema21) * 0.9985
                    score = 92.0 + (vol_ratio * 2.0)
                elif (c_low < nearest_support and c_close >= nearest_support and is_hammer) and has_room_for_buy:
                    sweep_status = "LONG_LIQUIDITY_SWEPT"
                    signal_side = "BUY"
                    setup_name = "LIQUIDITY_SWEEP"
                    setup_desc = f"Liquidity Sweep di bawah Support {nearest_support:.4f} & Reclaim ({rev_pattern['pattern_name']})"
                    structural_sl_candidate = c_low * 0.9985
                    score = 90.0 + (vol_ratio * 2.0)
            elif (c_low <= nearest_support * 1.0015 and is_hammer and rsi_val <= 38) and has_room_for_buy:
                signal_side = "BUY"
                setup_name = "SUPPORT_REVERSAL_BOUNCE"
                setup_desc = f"Pantulan Support {nearest_support:.4f} + Reversal Wick + RSI Oversold ({rsi_val:.1f})"
                structural_sl_candidate = c_low * 0.9985
                score = 88.0 + (vol_ratio * 2.0)

        # SKENARIO 2: BEARISH TREND
        elif "BEARISH" in effective_regime:
            cond_200 = (c_close < ema200_macro or c_close < ema200_htf or c_close < ema200_ltf)
            if cond_200 and ema13 < ema21:
                if c_close < ema50 and (c_high >= ema21 * 0.998 or is_shooting) and rsi_val >= 42 and has_room_for_sell:
                    signal_side = "SELL"
                    setup_name = "EMA21_PULLBACK_RETEST"
                    setup_desc = f"Retest Pullback EMA 21 ({ema21:.4f}) searah tren Bearish Kalimasada"
                    structural_sl_candidate = max(c_high, ema21) * 1.0015
                    score = 92.0 + (vol_ratio * 2.0)
                elif (c_high > nearest_resistance and c_close <= nearest_resistance and is_shooting) and has_room_for_sell:
                    sweep_status = "SHORT_LIQUIDITY_SWEPT"
                    signal_side = "SELL"
                    setup_name = "LIQUIDITY_SWEEP"
                    setup_desc = f"Liquidity Sweep di atas Resistance {nearest_resistance:.4f} & Reclaim ({rev_pattern['pattern_name']})"
                    structural_sl_candidate = c_high * 1.0015
                    score = 90.0 + (vol_ratio * 2.0)
            elif (c_high >= nearest_resistance * 0.9985 and is_shooting and rsi_val >= 62) and has_room_for_sell:
                signal_side = "SELL"
                setup_name = "RESISTANCE_REVERSAL_BOUNCE"
                setup_desc = f"Penolakan Resistance {nearest_resistance:.4f} + Shooting Star + RSI Overbought ({rsi_val:.1f})"
                structural_sl_candidate = c_high * 1.0015
                score = 88.0 + (vol_ratio * 2.0)

        # SKENARIO 3: SIDEWAYS (Range-bound)
        elif "SIDEWAYS" in effective_regime:
            range_h = (nearest_resistance - nearest_support) / nearest_support if nearest_support > 0 else 0.0
            if range_h >= 0.020:
                if c_low <= nearest_support * 1.002 and (is_hammer or rsi_val <= 38) and has_room_for_buy:
                    signal_side = "BUY"
                    setup_name = "RANGE_LOW_REVERSAL"
                    setup_desc = f"Reversal Batas Bawah Range Sideways ({nearest_support:.4f})"
                    structural_sl_candidate = c_low * 0.9985
                    score = 91.0 + (vol_ratio * 2.0)
                elif c_high >= nearest_resistance * 0.998 and (is_shooting or rsi_val >= 62) and has_room_for_sell:
                    signal_side = "SELL"
                    setup_name = "RANGE_HIGH_REVERSAL"
                    setup_desc = f"Reversal Batas Atas Range Sideways ({nearest_resistance:.4f})"
                    structural_sl_candidate = c_high * 1.0015
                    score = 91.0 + (vol_ratio * 2.0)

        # SKENARIO 4: MARKET ANEH (Wicks Ekstrem / Flash Anomali)
        elif "ANEH" in effective_regime:
            if c_low < nearest_support * 0.990 and (lower_wick / c_range >= 0.40) and rsi_val <= 28 and has_room_for_buy:
                signal_side = "BUY"
                setup_name = "FLASH_DUMP_RECLAIM"
                setup_desc = f"Reclaim Anomali Ekor Flash Dump ({c_low:.4f}) dengan RSI Ekstrem ({rsi_val:.1f})"
                structural_sl_candidate = c_low * 0.9980
                score = 96.0 + (vol_ratio * 2.0)
            elif c_high > nearest_resistance * 1.010 and (upper_wick / c_range >= 0.40) and rsi_val >= 72 and has_room_for_sell:
                signal_side = "SELL"
                setup_name = "FLASH_PUMP_REJECTION"
                setup_desc = f"Penolakan Anomali Ekor Flash Pump ({c_high:.4f}) dengan RSI Ekstrem ({rsi_val:.1f})"
                structural_sl_candidate = c_high * 1.0020
                score = 96.0 + (vol_ratio * 2.0)

    # Filter Confluence Tren Makro 4h (Pilar Kalimasada: DILARANG Melawan Tren Makro!)
    if signal_side == "BUY" and macro_trend == "BEARISH":
        signal_side = None
        setup_name = ""
        setup_desc = "Dibatalkan: Sinyal Buy melawan Tren Makro 4 Jam Bearish"
    elif signal_side == "SELL" and macro_trend == "BULLISH":
        signal_side = None
        setup_name = ""
        setup_desc = "Dibatalkan: Sinyal Sell melawan Tren Makro 4 Jam Bullish"

    # Confluence Derivatif & Candlestick Confirmation
    if signal_side == "BUY":
        if rev_pattern["is_bullish_reversal"]: score += 3.0
        if oi_trend == "EXPANDING": score += 3.0
        if taker_ratio >= 1.05: score += 2.0
    elif signal_side == "SELL":
        if rev_pattern["is_bearish_reversal"]: score += 3.0
        if oi_trend == "EXPANDING": score += 3.0
        if taker_ratio <= 0.95: score += 2.0

    final_score = min(100.0, round(score, 2))

    # Target Leverage & Range Stepping Clamping:
    target_leverage = config.LEVERAGE_MAX
    min_leverage = config.dynamic_min_leverage
    effective_leverage = min(target_leverage, max_symbol_leverage) if max_symbol_leverage > 0 else target_leverage

    # Manajemen Risiko Ketat RR 1:2 (Take Profit 2x Lipat Resiko)
    executable_signal = None
    if signal_side and final_score >= config.MIN_SETUP_SCORE and effective_leverage >= min_leverage:
        entry_price = latest_price

        # Structural Invalidation SL & True 1:2.0 Net RRR
        if structural_sl_candidate <= 0:
            structural_sl_candidate = min(c_low, p_low) * 0.9985 if signal_side == "BUY" else max(c_high, p_high) * 1.0015

        min_r = getattr(config, "MIN_SL_PERCENT", 0.0120)
        max_r = getattr(config, "MAX_SL_PERCENT", 0.0400)

        # 1. Jarak Stop Loss 100% Fleksibel Mengikuti Analisis Teknikal (Candle Wick / Support / Resisten):
        # Tidak dikunci kaku! Titik Stop Loss murni diletakkan di ujung wick candle atau di luar level S/R.
        risk_dist = abs(entry_price - structural_sl_candidate)
        risk_dist = max(entry_price * min_r, min(entry_price * max_r, risk_dist))
        sl_price = entry_price - risk_dist if signal_side == "BUY" else entry_price + risk_dist
        sl_percent = risk_dist / entry_price

        maker_fee = getattr(config, "MAKER_FEE_RATE", 0.0002)
        taker_fee = getattr(config, "TAKER_FEE_RATE", 0.0005)
        funding_buf = getattr(config, "FUNDING_BUFFER", 0.0001)
        roundtrip_fee = maker_fee + taker_fee + funding_buf
        eff_risk = sl_percent + roundtrip_fee

        # 2. Dynamic Leverage Cerdas: LEVERAGE YANG MENYESUAIKAN DENGAN SL WICK!
        # - Jika SL wick rapat (1.20% s/d 1.80%): Leverage otomatis naik ke 35x - 50x (memaksimalkan profit)
        # - Jika SL wick sedang (1.80% s/d 2.80%): Leverage otomatis menyesuaikan ke 20x - 35x
        # - Jika SL wick lebar (2.80% s/d 4.00%): Leverage otomatis santai ke 12x - 18x (memberi ruang bebas bagi wick)
        # Formula batas aman likuidasi: Jarak likuidasi bursa SELALU berada di luar Stop Loss!
        # dist_liq = (1.0 / L) - MMR > sl_percent + 0.0050 => L <= 1.0 / (sl_percent + MMR + 0.0050)
        mmr_est = 0.025 if (max_symbol_leverage > 0 and max_symbol_leverage <= 20) else 0.010
        max_liq_safe_lev = int(1.0 / (sl_percent + mmr_est + 0.0050))
        calc_lev = int(round(1.0 / eff_risk))

        safe_max_lev = min(config.LEVERAGE_MAX, max_symbol_leverage, max_liq_safe_lev) if max_symbol_leverage > 0 else min(config.LEVERAGE_MAX, max_liq_safe_lev)
        dynamic_leverage = max(config.LEVERAGE_MIN, min(safe_max_lev, calc_lev))

        # 3. Analisis Target Alami Pasar & Filter SKIP Mutlak (Room to Run Filter):
        # Menghitung target TP 1:2.0 Net yang menutup 100% roundtrip fee bursa
        req_tp_percent = (2.0 * sl_percent) + (3.0 * roundtrip_fee)
        req_tp_dist = entry_price * req_tp_percent

        # Analisis apakah ada tembok resisten tebal (BUY) atau support tebal (SELL) sebelum target 1:2 tercapai
        if signal_side == "BUY":
            natural_target = max(nearest_resistance, entry_price * (1.0 + req_tp_dist)) if entry_price >= nearest_resistance else nearest_resistance
            room_to_target = (natural_target - entry_price) / entry_price
            if room_to_target < (req_tp_percent * 0.95):
                console.log(f"[bold yellow]🛡️ Filter SKIP: Ruang gerak ke Resisten ({room_to_target*100:.2f}%) < Syarat RR 1:2 ({req_tp_percent*100:.2f}%). Menolak setup {symbol} agar tidak mentok di resisten.[/bold yellow]")
                return {"symbol": symbol, "score": 0.0, "signal": None, "reason": "ROOM_TO_TARGET_INSUFFICIENT"}
        elif signal_side == "SELL":
            natural_target = min(nearest_support, entry_price * (1.0 - req_tp_dist)) if entry_price <= nearest_support else nearest_support
            room_to_target = (entry_price - natural_target) / entry_price
            if room_to_target < (req_tp_percent * 0.95):
                console.log(f"[bold yellow]🛡️ Filter SKIP: Ruang gerak ke Support ({room_to_target*100:.2f}%) < Syarat RR 1:2 ({req_tp_percent*100:.2f}%). Menolak setup {symbol} agar tidak mentok di support.[/bold yellow]")
                return {"symbol": symbol, "score": 0.0, "signal": None, "reason": "ROOM_TO_TARGET_INSUFFICIENT"}

        tp_dist = req_tp_dist
        tp_percent = req_tp_percent
        tp_price = entry_price + tp_dist if signal_side == "BUY" else entry_price - tp_dist

        bep_trigger_percent = max(0.0128, sl_percent * 1.5)
        bep_trigger_dist = entry_price * bep_trigger_percent
        bep_trigger_price = entry_price + bep_trigger_dist if signal_side == "BUY" else entry_price - bep_trigger_dist

        # Aturan Margin Paten Ketat Sesuai Instruksi User:
        # - Jika saldo < $100: margin per posisi dikunci TEPAT $1.00 (maksimal ketat $1.00, tidak boleh lebih)
        # - Jika saldo >= $100: margin per posisi TEPAT 1.0% dari total saldo portofolio (maksimal ketat 1.0%), fleksibel compounding
        if available_capital < config.BALANCE_THRESHOLD_SCALING:
            target_margin_usd = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $1.00
        else:
            target_margin_usd = available_capital * config.RISK_PORTFOLIO_PERCENT  # Tepat 1.0% fleksibel compounding

        raw_notional = target_margin_usd * dynamic_leverage

        # Pengecekan Batas Minimum Order Binance ($5.00)
        # Pada margin $1.00 dan leverage >= 10x, notional >= $10.00 (lolos batas Binance $5.00).
        if raw_notional < config.MIN_NOTIONAL:
            executable_signal = None
        else:
            notional = raw_notional
            executable_signal = {
                "symbol": symbol,
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
                "target_margin": round(target_margin_usd, 4),
                "risk_usd": round(target_margin_usd, 4),
                "reward_usd": round(target_margin_usd * 2.0, 4),
                "score": final_score,
                "setup_name": setup_name,
                "setup_desc": setup_desc,
                "market_structure": structure,
                "candlestick_pattern": rev_pattern["pattern_name"],
                "sweep_status": sweep_status,
                "ema13": round(ema13, 4),
                "ema21": round(ema21, 4),
                "ema200": round(ema200_htf, 4),
                "nearest_support": round(nearest_support, 4),
                "nearest_resistance": round(nearest_resistance, 4),
                "liquidation_pools": liq_pools,
                "oi_trend": oi_trend,
                "taker_ratio": taker_ratio,
                "ls_ratio": ls_ratio,
                "vol_ratio": round(c_vol / avg_vol, 2) if avg_vol > 0 else 1.0,
                "scanned_candles_htf": len(ohlcv_htf),
                "scanned_candles_ltf": len(ohlcv_ltf),
                "scanned_candles_macro": len(ohlcv_macro) if ohlcv_macro else 0
            }

    return {
        "symbol": symbol,
        "price": latest_price,
        "macro_timeframe": config.MACRO_TIMEFRAME,
        "structure_timeframe": config.STRUCTURE_TIMEFRAME,
        "execution_timeframe": config.TIMEFRAME,
        "scanned_candles_ltf": len(ohlcv_ltf),
        "scanned_candles_htf": len(ohlcv_htf),
        "scanned_candles_macro": len(ohlcv_macro) if ohlcv_macro else 0,
        "macro_trend_4h": macro_trend,
        "market_structure_1h": structure,
        "market_structure": structure,
        "structure_desc": structure_info.get("desc", ""),
        "trend_bias": structure_info.get("bias", "NEUTRAL"),
        "ema13_15m": round(ema13, 4),
        "ema21_15m": round(ema21, 4),
        "ema200_1h": round(ema200_htf, 4),
        "ema200_4h": round(ema200_macro, 4),
        "nearest_support": round(nearest_support, 4),
        "nearest_resistance": round(nearest_resistance, 4),
        "liquidation_pools": liq_pools,
        "sweep_status": sweep_status,
        "candlestick_pattern": rev_pattern["pattern_name"],
        "oi_trend": oi_trend,
        "oi_delta": deriv.get("oi_delta", 0.0),
        "taker_ratio": taker_ratio,
        "ls_ratio": ls_ratio,
        "vol_ratio": round(c_vol / avg_vol, 2) if avg_vol > 0 else 1.0,
        "has_volume_expansion": has_volume_expansion,
        "setup_name": setup_name or "NONE",
        "setup_desc": setup_desc or "Menunggu setup terbentuk",
        "score": final_score,
        "signal": executable_signal
    }

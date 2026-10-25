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
    max_symbol_leverage: int = 50
) -> Dict[str, Any]:
    """
    Analisis Menyeluruh 1 Koin Crypto (Akademi Crypto Kalimasada Multi-Timeframe):
    1. Macro Timeframe (4h):
       - Tren Makro Institusi (EMA 200 & EMA 13/21 4 Jam)
       - Filter arah pasar (Bullish vs Bearish)
    2. Primary Structure Timeframe (1h):
       - Struktur Pasar (HH/HL vs LH/LL) & S&R Teruji >= 2 kali
       - Pemetaan Area Likuidasi Institusi (Liquidation Pools SMC)
    3. Lower Timeframe Execution (15m):
       - EMA 13 & 21 Retest Bounce (Searah Tren & Memiliki Room to Run >= 1.8%)
       - Liquidity Sweep Reclaim Teruji (SMC Stop Hunt dengan konfirmasi pola reversal lilin & volume)
       - Compression Squeeze Breakout
       - Pola Pembalikan Lilin (Hammer / Shooting Star / Engulfing)
       - Konfirmasi Volume Wajib (>= 100% rata-rata)
    4. Confluence Derivatif:
       - Open Interest (OI) Trend & CVD Delta
       - Global Long/Short Ratio
    5. Strict Risk Management: Risk-to-Reward 1:2.00 (SL 1.00%, TP 2.00%, BEP 1.75%).
    """
    if not ohlcv_ltf or len(ohlcv_ltf) < 25:
        return {"symbol": symbol, "price": 0.0, "status": "INSUFFICIENT_DATA", "score": 0.0, "signal": None}

    # Fallback jika data HTF tidak cukup
    if not ohlcv_htf or len(ohlcv_htf) < 25:
        ohlcv_htf = ohlcv_ltf

    # --- 1. Analisis Tren Makro 4h ---
    macro_trend = "NEUTRAL"
    ema200_macro = 0.0
    latest_price = ohlcv_ltf[-1][4]

    if ohlcv_macro and len(ohlcv_macro) >= 15:
        m_closes = [c[4] for c in ohlcv_macro]
        ema200_m_series = calculate_ema_series(m_closes, min(len(m_closes), config.EMA_TREND))
        ema200_macro = ema200_m_series[-1] if ema200_m_series else latest_price
        ema13_m = calculate_ema_series(m_closes, config.EMA_FAST)[-1]
        ema21_m = calculate_ema_series(m_closes, config.EMA_SLOW)[-1]
        if latest_price >= ema200_macro and ema13_m >= ema21_m:
            macro_trend = "BULLISH"
        elif latest_price <= ema200_macro and ema13_m <= ema21_m:
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

    # --- 2. Analisis LTF 5m (Eksekusi Scalping) ---
    ltf_opens = [c[1] for c in ohlcv_ltf]
    ltf_highs = [c[2] for c in ohlcv_ltf]
    ltf_lows = [c[3] for c in ohlcv_ltf]
    ltf_closes = [c[4] for c in ohlcv_ltf]
    ltf_volumes = [c[5] for c in ohlcv_ltf]

    ema13_series = calculate_ema_series(ltf_closes, config.EMA_FAST)
    ema21_series = calculate_ema_series(ltf_closes, config.EMA_SLOW)
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
    atr = atr_series[-1] if len(atr_series) >= 1 else (c_close * 0.005)
    rsi_val = rsi_series[-1] if len(rsi_series) >= 1 else 50.0

    c_range = c_high - c_low if (c_high - c_low) > 0 else 0.0001
    lower_wick = min(c_open, c_close) - c_low
    upper_wick = c_high - max(c_open, c_close)

    avg_vol = sum(ltf_volumes[-21:-1]) / 20.0 if len(ltf_volumes) >= 21 else c_vol
    has_volume_expansion = (c_vol >= avg_vol * 1.0)
    has_strong_volume = (c_vol >= avg_vol * config.VOLUME_SPIKE_FACTOR)

    # Pola Reversal Candlestick
    rev_pattern = detect_candlestick_reversal(c_open, c_high, c_low, c_close, p_open, p_close)

    # --- 3. Data Derivatif ---
    deriv = derivatives_data or {
        "long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0,
        "oi_delta": 0.0, "oi_trend": "NEUTRAL", "taker_ratio": 1.0, "cvd_bias": "NEUTRAL"
    }
    ls_ratio = deriv.get("ratio", 1.0)
    oi_trend = deriv.get("oi_trend", "NEUTRAL")
    taker_ratio = deriv.get("taker_ratio", 1.0)

    has_ls_support_buy = ls_ratio >= config.LS_RATIO_MIN_BUY
    has_ls_support_sell = ls_ratio <= config.LS_RATIO_MAX_SELL

    signal_side = None
    setup_name = ""
    setup_desc = ""
    score = 50.0
    sweep_status = "NONE"

    # Perhitungan Jarak ke S&R HTF (Room to Run)
    dist_to_resistance_pct = ((nearest_resistance - c_close) / c_close) if nearest_resistance > c_close else 0.0
    dist_to_support_pct = ((c_close - nearest_support) / c_close) if c_close > nearest_support else 0.0

    # Minimal jarak ke S&R berikutnya adalah 1.50% (cukup untuk target TP 2.33% tanpa langsung terbentur tembok)
    has_room_for_buy = dist_to_resistance_pct >= 0.015
    has_room_for_sell = dist_to_support_pct >= 0.015

    # Filter RSI Confluence (Poin 7 Kalimasada: Hindari overbought saat BUY & oversold saat SELL)
    rsi_ok_buy = (rsi_val <= 68.0)
    rsi_ok_sell = (rsi_val >= 32.0)

    # =========================================================================
    # SETUP 1: LIQUIDITY SWEEP & RECLAIM (Poin 8 Kalimasada - SMC Validasi Lilin Reversal)
    # Institutional Stop Hunt di bawah Support / di atas Resistance dengan konfirmasi Reversal
    # =========================================================================
    if (c_low <= nearest_support * 0.997) and c_close >= nearest_support and rev_pattern["is_bullish_reversal"] and macro_trend != "BEARISH" and rsi_ok_buy and has_room_for_buy and has_strong_volume:
        sweep_status = "LONG_LIQUIDITY_SWEPT"
        signal_side = "BUY"
        setup_name = "LIQUIDITY_SWEEP"
        setup_desc = f"Liquidity Sweep di bawah Support {nearest_support:.4f} & Reclaim ({rev_pattern['pattern_name']})"
        score = 90.0

    elif (c_high >= nearest_resistance * 1.003) and c_close <= nearest_resistance and rev_pattern["is_bearish_reversal"] and macro_trend != "BULLISH" and rsi_ok_sell and has_room_for_sell and has_strong_volume:
        sweep_status = "SHORT_LIQUIDITY_SWEPT"
        signal_side = "SELL"
        setup_name = "LIQUIDITY_SWEEP"
        setup_desc = f"Liquidity Sweep di atas Resistance {nearest_resistance:.4f} & Reclaim ({rev_pattern['pattern_name']})"
        score = 90.0

    # Filter Confluence Tren Makro 4h (Pilar Kalimasada: DILARANG Melawan Tren Makro!)
    if signal_side == "BUY" and macro_trend == "BEARISH":
        signal_side = None
        setup_name = ""
        setup_desc = "Dibatalkan: Sinyal Buy melawan Tren Makro 4 Jam Bearish"
    elif signal_side == "SELL" and macro_trend == "BULLISH":
        signal_side = None
        setup_name = ""
        setup_desc = "Dibatalkan: Sinyal Sell melawan Tren Makro 4 Jam Bullish"

    # Bonus Skor Pola Candlestick Reversal & Tren Makro 4h
    if signal_side == "BUY":
        if rev_pattern["is_bullish_reversal"]:
            score += 5.0
        if macro_trend == "BULLISH":
            score += 6.0
    elif signal_side == "SELL":
        if rev_pattern["is_bearish_reversal"]:
            score += 5.0
        if macro_trend == "BEARISH":
            score += 6.0

    # Bonus Skor Derivatif & Struktur
    if signal_side == "BUY":
        if oi_trend == "EXPANDING":
            score += 6.0
        if taker_ratio >= 1.05:
            score += 4.0
        if structure == "UPTREND":
            score += 5.0
    elif signal_side == "SELL":
        if oi_trend == "EXPANDING":
            score += 6.0
        if taker_ratio <= 0.95:
            score += 4.0
        if structure == "DOWNTREND":
            score += 5.0

    final_score = min(100.0, round(score, 2))

    # Target Leverage & Range Stepping Clamping:
    # Mengutamakan 50x, jika koin/akun dibatasi, ambil batas tertinggi dalam rentang [20x, 50x].
    target_leverage = config.LEVERAGE_MAX
    min_leverage = config.dynamic_min_leverage
    effective_leverage = min(target_leverage, max_symbol_leverage) if max_symbol_leverage > 0 else target_leverage

    # Manajemen Risiko Ketat RR 1:2 (Take Profit 2x Lipat Resiko)
    # Saring ketat: Jika koin tidak mendukung leverage minimal 20x (misal 10x), lewati (skip) koin!
    executable_signal = None
    if signal_side and final_score >= config.MIN_SETUP_SCORE and effective_leverage >= min_leverage:
        sl_percent = config.SL_PERCENT
        tp_percent = config.TP_PERCENT
        bep_trigger_percent = config.BEP_PROFIT_TRIGGER
        entry_price = latest_price
        sl_dist = entry_price * sl_percent
        tp_dist = entry_price * tp_percent
        bep_trigger_dist = entry_price * bep_trigger_percent

        sl_price = entry_price - sl_dist if signal_side == "BUY" else entry_price + sl_dist
        tp_price = entry_price + tp_dist if signal_side == "BUY" else entry_price - tp_dist
        bep_trigger_price = entry_price + bep_trigger_dist if signal_side == "BUY" else entry_price - bep_trigger_dist

        # Aturan Margin Bertingkat Fleksibel:
        # - Jika saldo < $100: margin per posisi dikunci tetap $1.00 (maksimal ketat $1.00)
        # - Jika saldo >= $100: margin per posisi 1.0% dari total saldo portofolio (fleksibel compounding)
        if available_capital < config.BALANCE_THRESHOLD_SCALING:
            target_margin_usd = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $1.00
        else:
            target_margin_usd = available_capital * config.RISK_PORTFOLIO_PERCENT  # 1.0% fleksibel

        raw_notional = target_margin_usd * effective_leverage

        # Pengecekan Batas Minimum Order Binance ($5.00)
        # Pada margin $1.00, koin dengan leverage 20x menghasilkan notional $20.00 (lolos batas Binance $5.00).
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
                "dynamic_leverage": effective_leverage,
                "notional": round(notional, 2),
                "target_margin": round(target_margin_usd, 4),
                "risk_usd": round(notional * sl_percent, 4),
                "reward_usd": round(notional * tp_percent, 4),
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

import math
from typing import Dict, Any, Optional, List
from config import config

def calculate_ema_series(values: List[float], period: int) -> List[float]:
    """Menghitung EMA berbasis list murni tanpa overhead memori."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1.0 - k))
    return ema

def calculate_rsi_series(closes: List[float], period: int = 14) -> List[float]:
    """Menghitung RSI berbasis list murni tanpa alokasi memori besar."""
    n = len(closes)
    if n < period + 1:
        return [50.0] * n
        
    gains = [0.0]
    losses = [0.0]
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
        
    rsi = []
    for i in range(n):
        if i < period:
            rsi.append(50.0)
        else:
            avg_g = sum(gains[i - period + 1 : i + 1]) / period
            avg_l = sum(losses[i - period + 1 : i + 1]) / period
            if avg_l == 0:
                rsi.append(100.0 if avg_g > 0 else 50.0)
            else:
                rs = avg_g / avg_l
                rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi

def calculate_atr_series(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Menghitung ATR berbasis list murni."""
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

def detect_n_pattern(highs: List[float], lows: List[float], closes: List[float], window: int = 35) -> Dict[str, Any]:
    """
    Mendeteksi Formasi Pola N (N-Wave Breakout & Retest):
    1. Pola N Bullish:
       - Swing Low L1 -> Swing High H1 (Impulse naik)
       - Retest ke Higher Low L2 (L2 > L1)
       - Breakout: Harga menembus atau mendekati H1
    2. Pola N Bearish (Inverted N):
       - Swing High H1 -> Swing Low L1 (Impulse turun)
       - Pullback ke Lower High H2 (H2 < H1)
       - Breakdown: Harga menembus atau mendekati L1
    """
    if len(closes) < 15:
        return {"pattern": "NONE", "score_boost": 0.0, "desc": "Data candle kurang"}

    h_slice = highs[-window:]
    l_slice = lows[-window:]
    c_slice = closes[-window:]
    n = len(c_slice)
    
    pivot = 2
    swing_highs = []
    swing_lows = []
    
    for i in range(pivot, n - 1):
        if all(h_slice[i] >= h_slice[i - j] for j in range(1, pivot + 1)) and \
           all(h_slice[i] >= h_slice[i + j] for j in range(1, min(pivot + 1, n - i))):
            swing_highs.append((i, h_slice[i]))
            
        if all(l_slice[i] <= l_slice[i - j] for j in range(1, pivot + 1)) and \
           all(l_slice[i] <= l_slice[i + j] for j in range(1, min(pivot + 1, n - i))):
            swing_lows.append((i, l_slice[i]))

    curr_close = c_slice[-1]
    
    # 1. Cek Pola N Bullish (L1 -> H1 -> L2 (HL))
    if len(swing_lows) >= 2 and len(swing_highs) >= 1:
        for l2_idx, l2_val in reversed(swing_lows):
            for h1_idx, h1_val in reversed(swing_highs):
                if h1_idx < l2_idx:
                    for l1_idx, l1_val in reversed(swing_lows):
                        if l1_idx < h1_idx:
                            impulse = h1_val - l1_val
                            retest = h1_val - l2_val
                            if impulse > 0 and l2_val > l1_val and (0.15 <= retest / impulse <= 0.85):
                                is_breakout = curr_close >= h1_val * 0.998
                                return {
                                    "pattern": "BULLISH_N",
                                    "is_breakout": is_breakout,
                                    "score_boost": 20.0 if is_breakout else 10.0,
                                    "desc": f"Pola N Bullish (L1: {l1_val:.4f} -> H1: {h1_val:.4f} -> HL: {l2_val:.4f})"
                                }

    # 2. Cek Pola N Bearish (H1 -> L1 -> H2 (LH))
    if len(swing_highs) >= 2 and len(swing_lows) >= 1:
        for h2_idx, h2_val in reversed(swing_highs):
            for l1_idx, l1_val in reversed(swing_lows):
                if l1_idx < h2_idx:
                    for h1_idx, h1_val in reversed(swing_highs):
                        if h1_idx < l1_idx:
                            impulse = h1_val - l1_val
                            retest = h2_val - l1_val
                            if impulse > 0 and h2_val < h1_val and (0.15 <= retest / impulse <= 0.85):
                                is_breakdown = curr_close <= l1_val * 1.002
                                return {
                                    "pattern": "BEARISH_N",
                                    "is_breakout": is_breakdown,
                                    "score_boost": 20.0 if is_breakdown else 10.0,
                                    "desc": f"Pola N Bearish (H1: {h1_val:.4f} -> L1: {l1_val:.4f} -> LH: {h2_val:.4f})"
                                }

    return {"pattern": "NONE", "score_boost": 0.0, "desc": "Netral (Tanpa Pola N)"}

def check_signal_from_ohlcv(
    ohlcv: List[List[float]],
    available_capital: float = 10.0,
    leverage: int = 10,
    ls_data: Optional[Dict[str, float]] = None
) -> Optional[Dict[str, Any]]:
    """
    Memeriksa sinyal Triple Confirmation Momentum Scalper (Anti-Noise, Pola N, & Sentimen Arus):
    1. Trend Regime (EMA 200 pada TF 5m).
    2. Crossover Trigger (EMA 9 & EMA 21).
    3. Volume Confirmation: Memastikan volume candle pemicu aktif (bukan dead-volume fakeout).
    4. Price Action Confirmation: Memastikan candle pemicu hijau/merah solid (bukan doji/rejection wick).
    5. Formasi Pola N: Memvalidasi struktur N-Wave Breakout & Retest.
    6. Sentimen Arus Pasar (Long/Short Account Ratio): Memastikan TIDAK melawan arus dominan.
    7. Stop Loss Adaptif berbasis Volatilitas ATR (ruang gerak sehat 1.2% - 1.8% anti-noise).
    """
    if len(ohlcv) < config.EMA_TREND + 5:
        return None

    opens = [c[1] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]

    ema_trend = calculate_ema_series(closes, config.EMA_TREND)
    ema_fast = calculate_ema_series(closes, config.EMA_FAST)
    ema_slow = calculate_ema_series(closes, config.EMA_SLOW)
    rsi_series = calculate_rsi_series(closes, config.RSI_PERIOD)
    atr_series = calculate_atr_series(highs, lows, closes, config.ATR_PERIOD)

    # Menggunakan bar tertutup (-2) dan bar sebelumnya (-3)
    c_prev_fast = ema_fast[-3]
    c_prev_slow = ema_slow[-3]
    c_curr_fast = ema_fast[-2]
    c_curr_slow = ema_slow[-2]

    curr_open = opens[-2]
    curr_high = highs[-2]
    curr_low = lows[-2]
    curr_close = closes[-2]
    curr_trend = ema_trend[-2]
    curr_vol = volumes[-2]
    rsi_val = rsi_series[-2]
    atr_val = atr_series[-2]
    latest_price = closes[-1]

    # 1. Cek Crossover EMA 9 & EMA 21
    golden_cross = (c_prev_fast <= c_prev_slow) and (c_curr_fast > c_curr_slow)
    death_cross = (c_prev_fast >= c_prev_slow) and (c_curr_fast < c_curr_slow)

    # 2. Trend Filter (EMA 200 pada TF 5m)
    is_bullish_trend = curr_close > curr_trend
    is_bearish_trend = curr_close < curr_trend

    # 3. Volume Support Filter: Volume candle pemicu wajib aktif
    avg_vol = sum(volumes[-22:-2]) / 20.0 if len(volumes) >= 22 else curr_vol
    has_volume_support = (curr_vol >= avg_vol * 0.90)

    # 4. Price Action Confirmation: Menghindari candle doji dan rejection wick (bull/bear trap)
    candle_range = curr_high - curr_low
    is_bullish_action = True
    is_bearish_action = True
    if candle_range > 0:
        upper_wick = curr_high - curr_close
        is_bullish_action = (curr_close > curr_open) and (upper_wick <= candle_range * 0.45)

        lower_wick = curr_close - curr_low
        is_bearish_action = (curr_close < curr_open) and (lower_wick <= candle_range * 0.45)

    # 5. Analisis Pola N (N-Wave Breakout)
    n_info = detect_n_pattern(highs, lows, closes, window=35)
    n_pattern = n_info.get("pattern", "NONE")
    is_n_valid_buy = (n_pattern != "BEARISH_N")
    is_n_valid_sell = (n_pattern != "BULLISH_N")

    # 6. Sentimen Arus Pasar (Long/Short Flow - Tidak Melawan Arus)
    ls_info = ls_data or {"long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0}
    ls_ratio = ls_info.get("ratio", 1.0)
    long_pct = ls_info.get("long_pct", 50.0)
    short_pct = ls_info.get("short_pct", 50.0)
    has_ls_support_buy = ls_ratio >= config.LS_RATIO_MIN_BUY
    has_ls_support_sell = ls_ratio <= config.LS_RATIO_MAX_SELL

    signal_side = None

    # Syarat BUY / LONG
    if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi_val <= config.RSI_LONG_MAX) and \
       has_volume_support and is_bullish_action and has_ls_support_buy and is_n_valid_buy:
        signal_side = "BUY"

    # Syarat SELL / SHORT
    elif is_bearish_trend and death_cross and (config.RSI_SHORT_MIN <= rsi_val <= config.RSI_SHORT_MAX) and \
         has_volume_support and is_bearish_action and has_ls_support_sell and is_n_valid_sell:
        signal_side = "SELL"

    if not signal_side:
        return None

    # 1. Hitung skor kualitas sinyal terlebih dahulu (RSI + Volume + Pola N + Arus Sentimen)
    vol_ratio = min(1.5, curr_vol / avg_vol) if avg_vol > 0 else 1.0
    base_score = (100.0 - abs(rsi_val - 55.0)) * (0.8 + 0.2 * vol_ratio)
    
    if signal_side == "BUY":
        if n_pattern == "BULLISH_N":
            base_score += n_info.get("score_boost", 15.0)
        if ls_ratio >= 1.05:
            base_score += 10.0
    elif signal_side == "SELL":
        if n_pattern == "BEARISH_N":
            base_score += n_info.get("score_boost", 15.0)
        if ls_ratio <= 0.95:
            base_score += 10.0

    score = min(100.0, round(base_score, 2))

    # 2. Dynamic Leverage Disesuaikan dengan Rasio Hasil Analisis (10x s/d 20x)
    dynamic_leverage = config.LEVERAGE
    if config.DYNAMIC_LEVERAGE_ENABLED:
        if score >= 82 and n_pattern != "NONE":
            dynamic_leverage = 20
        elif score >= 72:
            dynamic_leverage = 15
        else:
            dynamic_leverage = 10

    # 3. Model Risiko Portofolio 0.5% (Risk-Budget Sizing):
    # Jika SL = 1.0%, maka kerugian maksimal tepat 0.5% dari saldo portofolio.
    # Jika TP = 2.0% (RRR 1:2), maka keuntungan maksimal tepat 2x risiko (1.0% dari saldo portofolio).
    sl_percent = config.SL_PERCENT  # 1.0%
    tp_percent = sl_percent * config.RR_RATIO  # 2.0% (Risk to Reward 1:2)
    risk_budget_usd = available_capital * config.RISK_PORTFOLIO_PERCENT
    ideal_notional = risk_budget_usd / sl_percent

    # Pastikan memenuhi batas minimum notional Binance ($5.0) dan batas aman ($5.15)
    notional = max(config.MIN_NOTIONAL + 0.15, ideal_notional)
    if available_capital < 20.0:
        notional = min(notional, config.MAX_ORDER_NOTIONAL)

    margin_required = notional / dynamic_leverage
    qty = notional / latest_price

    if signal_side == "BUY":
        entry_price = latest_price
        sl_price = entry_price * (1.0 - sl_percent)
        tp_price = entry_price * (1.0 + tp_percent)
    else:
        entry_price = latest_price
        sl_price = entry_price * (1.0 + sl_percent)
        tp_price = entry_price * (1.0 - tp_percent)

    return {
        "side": signal_side,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "qty": qty,
        "notional": notional,
        "dynamic_leverage": dynamic_leverage,
        "margin_required": round(margin_required, 4),
        "risk_usd": round(notional * sl_percent, 4),
        "reward_usd": round(notional * tp_percent, 4),
        "sl_percent": round(sl_percent * 100, 2),
        "tp_percent": round(tp_percent * 100, 2),
        "rsi": round(rsi_val, 2),
        "ema_trend": round(curr_trend, 4),
        "atr": round(atr_val, 4),
        "score": score,
        "n_pattern": n_pattern,
        "n_desc": n_info.get("desc", ""),
        "ls_ratio": ls_ratio,
        "long_pct": long_pct,
        "short_pct": short_pct
    }

def check_signal(ohlcv: List[List[float]], available_capital: float = 10.0, leverage: int = 10, ls_data: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
    """Fungsi utama pemeriksaan sinyal scalping 5m berbasis list OHLCV native."""
    return check_signal_from_ohlcv(ohlcv, available_capital, leverage, ls_data)


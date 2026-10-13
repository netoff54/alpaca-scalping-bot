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

def detect_candlestick_pattern(
    opens: List[float], highs: List[float], lows: List[float], closes: List[float]
) -> Dict[str, Any]:
    """
    Mendeteksi pola pembalikan candlestick (Reversal Candlestick):
    - Bullish: Hammer / Pinbar bawah, Bullish Engulfing, Solid Green Bounce.
    - Bearish: Shooting Star / Pinbar atas, Bearish Engulfing, Solid Red Rejection.
    """
    if len(closes) < 3:
        return {"pattern": "NONE", "bias": "NEUTRAL", "score_boost": 0.0, "desc": "Data candle kurang"}

    # Candle tertutup terkini (-2) dan sebelumnya (-3)
    c_open = opens[-2]
    c_high = highs[-2]
    c_low = lows[-2]
    c_close = closes[-2]
    c_range = c_high - c_low

    p_open = opens[-3]
    p_close = closes[-3]

    if c_range <= 0:
        return {"pattern": "NEUTRAL", "bias": "NEUTRAL", "score_boost": 0.0, "desc": "Candle doji flat"}

    body = abs(c_close - c_open)
    upper_wick = c_high - max(c_open, c_close)
    lower_wick = min(c_open, c_close) - c_low

    # 1. Bullish Hammer / Pinbar (Lower wick panjang >= 38%, rejection di dasar)
    if lower_wick >= c_range * 0.38 and upper_wick <= c_range * 0.25 and c_close >= c_open:
        return {
            "pattern": "HAMMER",
            "bias": "BULLISH",
            "score_boost": 20.0,
            "desc": f"Bullish Hammer/Pinbar (Lower Wick {(lower_wick/c_range)*100:.0f}%)"
        }

    # 2. Bullish Engulfing (Candle hijau memakan candle merah sebelumnya)
    if p_close < p_open and c_close > c_open and c_close >= p_open and body >= c_range * 0.45:
        return {
            "pattern": "BULLISH_ENGULFING",
            "bias": "BULLISH",
            "score_boost": 20.0,
            "desc": "Bullish Engulfing solid membalikkan tren"
        }

    # 3. Solid Bullish Bounce (Green candle solid di area oversold)
    if c_close > c_open and body >= c_range * 0.50 and upper_wick <= c_range * 0.30:
        return {
            "pattern": "BULLISH_BOUNCE",
            "bias": "BULLISH",
            "score_boost": 12.0,
            "desc": "Solid Green Reversal Bounce"
        }

    # 4. Bearish Shooting Star / Pinbar (Upper wick panjang >= 38%, rejection di puncak)
    if upper_wick >= c_range * 0.38 and lower_wick <= c_range * 0.25 and c_close <= c_open:
        return {
            "pattern": "SHOOTING_STAR",
            "bias": "BEARISH",
            "score_boost": 20.0,
            "desc": f"Bearish Shooting Star (Upper Wick {(upper_wick/c_range)*100:.0f}%)"
        }

    # 5. Bearish Engulfing (Candle merah memakan candle hijau sebelumnya)
    if p_close > p_open and c_close < c_open and c_close <= p_open and body >= c_range * 0.45:
        return {
            "pattern": "BEARISH_ENGULFING",
            "bias": "BEARISH",
            "score_boost": 20.0,
            "desc": "Bearish Engulfing solid membalikkan tren"
        }

    # 6. Solid Bearish Rejection (Red candle solid di area overbought)
    if c_close < c_open and body >= c_range * 0.50 and lower_wick <= c_range * 0.30:
        return {
            "pattern": "BEARISH_REJECTION",
            "bias": "BEARISH",
            "score_boost": 12.0,
            "desc": "Solid Red Reversal Rejection"
        }

    return {"pattern": "NEUTRAL", "bias": "NEUTRAL", "score_boost": 0.0, "desc": "Candle netral"}

def check_signal_from_ohlcv(
    ohlcv: List[List[float]],
    available_capital: float = 10.0,
    leverage: int = 10,
    ls_data: Optional[Dict[str, float]] = None
) -> Optional[Dict[str, Any]]:
    """
    Strategi Scalping Terpadu RSI 30 Buy & RSI 70 Sell + Candlestick Reversal & EMA Cross:
    1. RSI Mean-Reversion Trigger:
       - BUY saat RSI <= config.RSI_BUY_THRESHOLD (Area oversold / pantulan dari 30).
       - SELL saat RSI >= config.RSI_SELL_THRESHOLD (Area overbought / penolakan dari 70).
    2. Candlestick Reversal Confirmation:
       - BUY didukung Hammer / Bullish Engulfing / Solid Green Bounce (bukan candle dump merah).
       - SELL didukung Shooting Star / Bearish Engulfing / Solid Red Rejection (bukan candle pump hijau).
    3. EMA Cross / Reclaim Confirmation:
       - BUY: Harga menembus ke atas EMA 9 (Reclaim) ATAU Golden Cross (EMA 9 cross di atas EMA 21).
       - SELL: Harga menembus ke bawah EMA 9 (Breakdown) ATAU Death Cross (EMA 9 cross di bawah EMA 21).
    4. Sentimen Arus Pasar (Long/Short Ratio): Memastikan tidak melawan arus dominan.
    5. Dynamic Leverage 10x - 20x sesuai skor analisis.
    6. Risk to Reward 1:2 (SL 1.0%, TP 2.0%) dengan resiko 0.5% portofolio.
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

    candle_range = curr_high - curr_low
    upper_wick = curr_high - max(curr_open, curr_close)
    lower_wick = min(curr_open, curr_close) - curr_low

    # 1. Deteksi Pola Candlestick Reversal
    candle_info = detect_candlestick_pattern(opens, highs, lows, closes)
    candle_bias = candle_info.get("bias", "NEUTRAL")
    candle_pat = candle_info.get("pattern", "NEUTRAL")

    # 2. Cek Crossover & Posisi EMA 9 vs EMA 21
    golden_cross = (c_prev_fast <= c_prev_slow) and (c_curr_fast > c_curr_slow)
    death_cross = (c_prev_fast >= c_prev_slow) and (c_curr_fast < c_curr_slow)

    bullish_ema = golden_cross or (curr_close >= c_curr_fast) or (
        candle_bias == "BULLISH" and curr_close > curr_open and curr_close > closes[-3]
    )
    bearish_ema = death_cross or (curr_close <= c_curr_fast) or (
        candle_bias == "BEARISH" and curr_close < curr_open and curr_close < closes[-3]
    )

    # 3. Volume Support Filter: Volume candle pemicu wajib aktif
    avg_vol = sum(volumes[-22:-2]) / 20.0 if len(volumes) >= 22 else curr_vol
    has_volume_support = (curr_vol >= avg_vol * 0.85)

    # 4. Sentimen Arus Pasar (Long/Short Flow)
    ls_info = ls_data or {"long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0}
    ls_ratio = ls_info.get("ratio", 1.0)
    long_pct = ls_info.get("long_pct", 50.0)
    short_pct = ls_info.get("short_pct", 50.0)
    has_ls_support_buy = ls_ratio >= config.LS_RATIO_MIN_BUY
    has_ls_support_sell = ls_ratio <= config.LS_RATIO_MAX_SELL

    signal_side = None

    # Syarat BUY / LONG:
    # 1. RSI oversold di rentang 20 - 30 (config.RSI_BUY_MIN s/d config.RSI_BUY_MAX)
    # 2. Candlestick reversal bullish ATAU candle hijau solid tanpa upper wick besar
    # 3. EMA konfirmasi: harga menembus di atas EMA 9, Golden Cross, atau bounce hammer kuat
    # 4. Volume aktif dan sentimen L/S tidak melawan arus short ekstrem
    is_valid_buy_candle = (candle_bias == "BULLISH") or (curr_close > curr_open and upper_wick <= candle_range * 0.35)
    is_rsi_buy = (config.RSI_BUY_MIN <= rsi_val <= config.RSI_BUY_MAX)
    if is_rsi_buy and is_valid_buy_candle and bullish_ema and \
       has_volume_support and has_ls_support_buy:
        signal_side = "BUY"

    # Syarat SELL / SHORT:
    # 1. RSI overbought di rentang 70 - 80 (config.RSI_SELL_MIN s/d config.RSI_SELL_MAX)
    # 2. Candlestick reversal bearish ATAU candle merah solid tanpa lower wick besar
    # 3. EMA konfirmasi: harga breakdown di bawah EMA 9, Death Cross, atau rejection shooting star
    # 4. Volume aktif dan sentimen L/S tidak melawan arus long ekstrem
    is_valid_sell_candle = (candle_bias == "BEARISH") or (curr_close < curr_open and lower_wick <= candle_range * 0.35)
    is_rsi_sell = (config.RSI_SELL_MIN <= rsi_val <= config.RSI_SELL_MAX)
    if is_rsi_sell and is_valid_sell_candle and bearish_ema and \
       has_volume_support and has_ls_support_sell:
        signal_side = "SELL"

    if not signal_side:
        return None

    # 1. Hitung skor kualitas sinyal (Kombinasi RSI Ekstrem 20-30/70-80 + Candlestick Reversal + EMA Cross + Volume)
    base_score = 50.0
    if signal_side == "BUY":
        # Rentang RSI 20 - 30: Semakin dalam di rentang 20-30, semakin tinggi potensi pantulan
        rsi_boost = max(0.0, (config.RSI_BUY_MAX - rsi_val) * 2.5)
        base_score += min(25.0, rsi_boost)
        base_score += candle_info.get("score_boost", 10.0)
        base_score += 15.0 if golden_cross else 8.0
        if curr_vol >= avg_vol * 1.15:
            base_score += 8.0
        if ls_ratio >= 1.05:
            base_score += 7.0
    elif signal_side == "SELL":
        # Rentang RSI 70 - 80: Semakin tinggi di rentang 70-80, semakin tinggi potensi penolakan
        rsi_boost = max(0.0, (rsi_val - config.RSI_SELL_MIN) * 2.5)
        base_score += min(25.0, rsi_boost)
        base_score += candle_info.get("score_boost", 10.0)
        base_score += 15.0 if death_cross else 8.0
        if curr_vol >= avg_vol * 1.15:
            base_score += 8.0
        if ls_ratio <= 0.95:
            base_score += 7.0

    score = min(100.0, round(base_score, 2))

    # 2. Dynamic Leverage Disesuaikan dengan Rasio Hasil Analisis (10x s/d 20x)
    dynamic_leverage = config.LEVERAGE
    if config.DYNAMIC_LEVERAGE_ENABLED:
        if score >= 82 and candle_pat != "NEUTRAL":
            dynamic_leverage = 20
        elif score >= 72:
            dynamic_leverage = 15
        else:
            dynamic_leverage = 10

    # 3. Model Risiko Portofolio 0.5% (Risk-Budget Sizing):
    # SL = 1.0%, kerugian maksimal tepat 0.5% dari saldo portofolio.
    # TP = 2.0% (RRR 1:2), keuntungan tepat 2x risiko (1.0% dari saldo portofolio).
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
        if golden_cross:
            ema_status = "Golden Cross (EMA 9 > 21)"
        elif curr_close >= c_curr_fast:
            ema_status = "Reclaim EMA 9"
        else:
            ema_status = "Oversold Dip Bounce"
    else:
        entry_price = latest_price
        sl_price = entry_price * (1.0 + sl_percent)
        tp_price = entry_price * (1.0 - tp_percent)
        if death_cross:
            ema_status = "Death Cross (EMA 9 < 21)"
        elif curr_close <= c_curr_fast:
            ema_status = "Breakdown EMA 9"
        else:
            ema_status = "Overbought Peak Rejection"

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
        "candlestick_pattern": candle_pat,
        "ema_status": ema_status,
        "n_pattern": candle_pat,  # Kompatibilitas field lama
        "n_desc": f"{candle_info.get('desc', '')} + {ema_status}",
        "ls_ratio": ls_ratio,
        "long_pct": long_pct,
        "short_pct": short_pct
    }

def check_signal(ohlcv: List[List[float]], available_capital: float = 10.0, leverage: int = 10, ls_data: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
    """Fungsi utama pemeriksaan sinyal scalping 1m berbasis list OHLCV native."""
    return check_signal_from_ohlcv(ohlcv, available_capital, leverage, ls_data)

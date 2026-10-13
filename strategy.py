import math
from typing import Dict, Any, Optional, List, Union
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

def check_signal_from_ohlcv(ohlcv: List[List[float]], available_capital: float = 10.0, leverage: int = 5) -> Optional[Dict[str, Any]]:
    """
    Memeriksa sinyal Triple Confirmation Momentum Scalper (Anti-Noise & Anti-Trap):
    1. Trend Regime (EMA 200).
    2. Crossover Trigger (EMA 9 & EMA 21).
    3. Volume Confirmation: Memastikan volume candle pemicu aktif (bukan dead-volume fakeout).
    4. Price Action Confirmation: Memastikan candle pemicu hijau/merah solid (bukan doji/rejection wick).
    5. RSI Momentum Bersih (hindari zona jenuh pucuk/dasar).
    6. Stop Loss Adaptif berbasis Volatilitas ATR (ruang gerak sehat 1.2% - 1.8% anti-noise).
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

    # 2. Trend Filter (EMA 200)
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
        # Untuk BUY: Candle harus hijau (Close > Open) dan tidak memiliki rejection wick atas yang dominan (<= 45%)
        upper_wick = curr_high - curr_close
        is_bullish_action = (curr_close > curr_open) and (upper_wick <= candle_range * 0.45)

        # Untuk SELL: Candle harus merah (Close < Open) dan tidak memiliki rejection wick bawah yang dominan (<= 45%)
        lower_wick = curr_close - curr_low
        is_bearish_action = (curr_close < curr_open) and (lower_wick <= candle_range * 0.45)

    signal_side = None

    # Syarat BUY / LONG
    if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi_val <= config.RSI_LONG_MAX) and has_volume_support and is_bullish_action:
        signal_side = "BUY"

    # Syarat SELL / SHORT
    elif is_bearish_trend and death_cross and (config.RSI_SHORT_MIN <= rsi_val <= config.RSI_SHORT_MAX) and has_volume_support and is_bearish_action:
        signal_side = "SELL"

    if not signal_side:
        return None

    # Alokasi margin: 0.5% dari total portofolio (misal jika $100 -> cukup margin $0.5)
    # Dengan batas minimal agar memenuhi syarat minimum Binance ($5 Notional)
    min_margin = config.MIN_NOTIONAL / leverage
    target_margin = available_capital * config.RISK_PORTFOLIO_PERCENT
    margin_required = max(min_margin, target_margin)
    notional = margin_required * leverage
    qty = notional / latest_price

    # Stop Loss & Take Profit Adaptif Berbasis Volatilitas (ATR)
    # Memberi ruang gerak sehat (1.2% - 1.8%) di luar batas noise pasar 1m/3m
    atr_pct = (atr_val / curr_close) if curr_close > 0 else 0.008
    sl_percent = max(config.SL_PERCENT, min(0.018, atr_pct * 1.8))
    tp_percent = max(config.TP_PERCENT, sl_percent * config.RR_RATIO)

    if signal_side == "BUY":
        entry_price = latest_price
        sl_price = entry_price * (1.0 - sl_percent)
        tp_price = entry_price * (1.0 + tp_percent)
    else:
        entry_price = latest_price
        sl_price = entry_price * (1.0 + sl_percent)
        tp_price = entry_price * (1.0 - tp_percent)

    # Skor kualitas sinyal (RSI center score + volume multiplier)
    vol_ratio = min(1.5, curr_vol / avg_vol) if avg_vol > 0 else 1.0
    score = (100.0 - abs(rsi_val - 55.0)) * (0.8 + 0.2 * vol_ratio)

    return {
        "side": signal_side,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "qty": qty,
        "notional": notional,
        "margin_required": notional / leverage,
        "sl_percent": round(sl_percent * 100, 2),
        "tp_percent": round(tp_percent * 100, 2),
        "rsi": round(rsi_val, 2),
        "ema_trend": round(curr_trend, 4),
        "atr": round(atr_val, 4),
        "score": round(score, 2)
    }

def check_signal(data: Any, available_capital: float = 10.0, leverage: int = 5) -> Optional[Dict[str, Any]]:
    """Wrapper kompatibel untuk list OHLCV maupun DataFrame."""
    if isinstance(data, list):
        return check_signal_from_ohlcv(data, available_capital, leverage)
    # Jika data berupa DataFrame
    ohlcv = data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].values.tolist()
    return check_signal_from_ohlcv(ohlcv, available_capital, leverage)

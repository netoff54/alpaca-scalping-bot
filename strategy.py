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
    Memeriksa sinyal Triple Filter Momentum Scalper langsung dari data candle OHLCV.
    Hemat memori 100% (tidak menggunakan Pandas DataFrame).
    """
    if len(ohlcv) < config.EMA_TREND + 5:
        return None

    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]

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

    curr_close = closes[-2]
    curr_trend = ema_trend[-2]
    rsi_val = rsi_series[-2]
    atr_val = atr_series[-2]
    latest_price = closes[-1]

    # 1. Cek Crossover EMA 9 & EMA 21
    golden_cross = (c_prev_fast <= c_prev_slow) and (c_curr_fast > c_curr_slow)
    death_cross = (c_prev_fast >= c_prev_slow) and (c_curr_fast < c_curr_slow)

    # 2. Trend Filter (EMA 200)
    is_bullish_trend = curr_close > curr_trend
    is_bearish_trend = curr_close < curr_trend

    signal_side = None

    # Syarat BUY / LONG
    if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi_val <= config.RSI_LONG_MAX):
        signal_side = "BUY"

    # Syarat SELL / SHORT
    elif is_bearish_trend and death_cross and (config.RSI_SHORT_MIN <= rsi_val <= config.RSI_SHORT_MAX):
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

    # Stop Loss & Take Profit (1:2 Risk to Reward)
    sl_percent = config.SL_PERCENT  # 0.5% (0.005)
    tp_percent = config.TP_PERCENT  # 1.0% (0.010)

    if signal_side == "BUY":
        entry_price = latest_price
        sl_price = entry_price * (1.0 - sl_percent)
        tp_price = entry_price * (1.0 + tp_percent)
    else:
        entry_price = latest_price
        sl_price = entry_price * (1.0 + sl_percent)
        tp_price = entry_price * (1.0 - tp_percent)

    score = 100.0 - abs(rsi_val - 55.0)

    return {
        "side": signal_side,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "qty": qty,
        "notional": notional,
        "margin_required": notional / leverage,
        "sl_percent": sl_percent * 100,
        "tp_percent": tp_percent * 100,
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

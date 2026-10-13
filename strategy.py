import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from config import config

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Menghitung Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Menghitung Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Menghitung Average True Range (ATR)."""
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Menghitung semua indikator scalping pada DataFrame OHLCV."""
    df = df.copy()
    df['ema_trend'] = calculate_ema(df['close'], config.EMA_TREND)
    df['ema_fast'] = calculate_ema(df['close'], config.EMA_FAST)
    df['ema_slow'] = calculate_ema(df['close'], config.EMA_SLOW)
    df['rsi'] = calculate_rsi(df['close'], config.RSI_PERIOD)
    df['atr'] = calculate_atr(df, config.ATR_PERIOD)
    return df

def check_signal(df: pd.DataFrame, available_capital: float = 10.0, leverage: int = 5) -> Optional[Dict[str, Any]]:
    """
    Memeriksa sinyal scalping berdasarkan closed candle terakhir (-2).
    Menggunakan candle tertutup untuk mencegah repaint pada candle aktif (-1).
    """
    if len(df) < config.EMA_TREND + 5:
        return None

    # Bar tertutup (-2) dan bar sebelumnya (-3)
    c_prev = df.iloc[-3]
    c_curr = df.iloc[-2]
    latest_price = float(df['close'].iloc[-1])

    # 1. Cek Crossover EMA 9 & EMA 21
    golden_cross = (c_prev['ema_fast'] <= c_prev['ema_slow']) and (c_curr['ema_fast'] > c_curr['ema_slow'])
    death_cross = (c_prev['ema_fast'] >= c_prev['ema_slow']) and (c_curr['ema_fast'] < c_curr['ema_slow'])

    # 2. Trend Filter (EMA 200)
    is_bullish_trend = c_curr['close'] > c_curr['ema_trend']
    is_bearish_trend = c_curr['close'] < c_curr['ema_trend']

    # 3. RSI Filter (Momentum Window)
    rsi_val = float(c_curr['rsi'])
    atr_val = float(c_curr['atr']) if not np.isnan(c_curr['atr']) else (latest_price * 0.002)

    signal_side = None

    # Syarat BUY / LONG
    if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi_val <= config.RSI_LONG_MAX):
        signal_side = "BUY"

    # Syarat SELL / SHORT
    elif is_bearish_trend and death_cross and (config.RSI_SHORT_MIN <= rsi_val <= config.RSI_SHORT_MAX):
        signal_side = "SELL"

    if not signal_side:
        return None

    # Perhitungan Notional Posisi & Compounding
    # Jika modal > $0, gunakan 100% modal * leverage
    # Nilai notional minimum dibatasi oleh MIN_NOTIONAL ($5.0)
    notional = max(config.MIN_NOTIONAL, available_capital * leverage)
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

    # Signal Score berdasarkan kedekatan momentum optimal
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
        "ema_trend": round(float(c_curr['ema_trend']), 4),
        "atr": round(atr_val, 4),
        "score": round(score, 2)
    }

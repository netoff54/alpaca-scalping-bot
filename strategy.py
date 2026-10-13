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

    # Perhitungan smoothed RSI
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

def check_signal(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Memeriksa sinyal scalping berdasarkan closed candle terakhir (-2).
    Menggunakan candle tertutup untuk mencegah repaint / sinyal palsu di candle aktif (-1).
    """
    if len(df) < config.EMA_TREND + 10:
        return None

    # Menggunakan bar tertutup terakhir (-2) dan bar sebelumnya (-3)
    c_prev = df.iloc[-3]
    c_curr = df.iloc[-2]
    latest_price = df['close'].iloc[-1]

    # Cek Crossover EMA 9 & EMA 21
    golden_cross = (c_prev['ema_fast'] <= c_prev['ema_slow']) and (c_curr['ema_fast'] > c_curr['ema_slow'])
    death_cross = (c_prev['ema_fast'] >= c_prev['ema_slow']) and (c_curr['ema_fast'] < c_curr['ema_slow'])

    # Trend Filter (EMA 200)
    is_bullish_trend = c_curr['close'] > c_curr['ema_trend']
    is_bearish_trend = c_curr['close'] < c_curr['ema_trend']

    # RSI Filter
    rsi_val = c_curr['rsi']
    atr_val = c_curr['atr'] if not np.isnan(c_curr['atr']) else (latest_price * 0.002)

    signal_side = None

    # Syarat BUY / LONG
    if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi_val <= config.RSI_LONG_MAX):
        signal_side = "BUY"

    # Syarat SELL / SHORT
    elif is_bearish_trend and death_cross and (config.RSI_SHORT_MIN <= rsi_val <= config.RSI_SHORT_MAX):
        signal_side = "SELL"

    if not signal_side:
        return None

    # Perhitungan Manajemen Risiko $10:
    # Modal $10, Risiko per trade 0.5% = $0.05
    max_loss_usd = config.TOTAL_CAPITAL * config.RISK_PER_TRADE_PERCENT  # $0.05
    position_notional = config.MIN_NOTIONAL                               # $5.0

    # Pada posisi $5, loss $0.05 setara dengan pergerakan harga 1.0%
    max_sl_percent = max_loss_usd / position_notional                     # 0.01 (1%)

    # Dynamic ATR Stop Loss
    atr_sl_dist = atr_val * config.ATR_SL_MULTIPLIER
    atr_sl_percent = atr_sl_dist / latest_price

    # Batasi Stop Loss agar kerugian TIDAK PERNAH melebihi $0.05 (1%)
    effective_sl_percent = min(atr_sl_percent, max_sl_percent)
    effective_sl_dist = latest_price * effective_sl_percent

    tp_dist = effective_sl_dist * config.RR_RATIO

    if signal_side == "BUY":
        entry_price = latest_price
        sl_price = entry_price - effective_sl_dist
        tp_price = entry_price + tp_dist
    else:
        entry_price = latest_price
        sl_price = entry_price + effective_sl_dist
        tp_price = entry_price - tp_dist

    # Ukuran koin (qty) untuk posisi $5 notional
    qty = round(position_notional / entry_price, 6)

    return {
        "side": signal_side,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "qty": qty,
        "notional": position_notional,
        "margin_required": position_notional / config.LEVERAGE,  # $5 / 5 = $1 margin (terisolasi)
        "max_risk_usd": max_loss_usd,                            # $0.05 (0.5% modal)
        "target_profit_usd": max_loss_usd * config.RR_RATIO,     # $0.10 (1.0% modal)
        "rsi": round(rsi_val, 2),
        "ema_trend": round(c_curr['ema_trend'], 2),
        "atr": round(atr_val, 2)
    }

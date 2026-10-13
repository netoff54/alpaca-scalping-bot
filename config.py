import os
from dataclasses import dataclass

@dataclass
class BotConfig:
    # --- Exchange Settings ---
    EXCHANGE_ID: str = "binance"          # "binance" atau "bybit"
    IS_TESTNET: bool = True               # Selalu tes di TESTNET dulu sebelum live
    API_KEY: str = os.getenv("API_KEY", "")
    API_SECRET: str = os.getenv("API_SECRET", "")

    # --- Trading Pair & Timeframe ---
    SYMBOL: str = "BTC/USDT:USDT"          # Futures perpetual contract
    TIMEFRAME: str = "1m"                  # 1m atau 3m untuk scalping
    CANDLE_LIMIT: int = 250                # Minimal 200+ candle untuk EMA 200

    # --- Account & Risk Management ---
    TOTAL_CAPITAL: float = 10.0            # Modal awal $10
    RISK_PER_TRADE_PERCENT: float = 0.005  # 0.5% dari modal ($0.05)
    LEVERAGE: int = 5                      # Leverage 5x
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED (melindungi sisa saldo)
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker fee rendah)

    # --- Position Sizing ---
    # Batas minimum order bursa adalah $5 notional
    MIN_NOTIONAL: float = 5.0              # Nilai posisi minimum bursa ($5)
    
    # --- Limit Order Settings ---
    LIMIT_TIMEOUT_SECONDS: int = 30        # Batalkan limit order jika tidak terisi dalam 30 detik
    POST_ONLY: bool = True                 # Memastikan hanya dieksekusi sebagai Maker

    # --- Indicator Parameters ---
    EMA_TREND: int = 200                   # Filter tren besar
    EMA_FAST: int = 9                      # Trigger cepat
    EMA_SLOW: int = 21                     # Trigger konfirmasi
    RSI_PERIOD: int = 14                   # Filter momentum
    RSI_LONG_MIN: float = 50.0             # Syarat Long: RSI > 50
    RSI_LONG_MAX: float = 68.0             # Cegah Long di pucuk overbought
    RSI_SHORT_MAX: float = 50.0            # Syarat Short: RSI < 50
    RSI_SHORT_MIN: float = 32.0            # Cegah Short di dasar oversold
    ATR_PERIOD: int = 14                   # Volatilitas adaptif

    # --- Risk / Reward Settings ---
    ATR_SL_MULTIPLIER: float = 1.5         # Jarak Stop Loss = 1.5 * ATR
    RR_RATIO: float = 2.0                  # Risk to Reward 1:2 (TP = 2 * SL)
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee

config = BotConfig()

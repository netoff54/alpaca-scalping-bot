import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class BotConfig:
    # --- Exchange Settings ---
    EXCHANGE_ID: str = "binance"
    IS_TESTNET: bool = False
    API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

    # --- Market Scanning ---
    TOP_COINS_LIMIT: int = 50              # Pindai 50 koin paling likuid & volatil di Binance Futures (Aman 100% dari rate limit)
    SCAN_INTERVAL_SECONDS: int = 60        # Selaras dengan penutupan candle 1m (1 menit)
    TIMEFRAME: str = "1m"                  # Timeframe 1 menit untuk scalping agresif
    CANDLE_LIMIT: int = 220                # 220 candle untuk perhitungan EMA 200 yang presisi

    # --- Account & Risk Management ---
    DEFAULT_CAPITAL: float = 10.0          # Modal dasar $10
    COMPOUNDING_ENABLED: bool = True       # 100% Saldo Kas Tersedia Digulung (Compounding)
    LEVERAGE: int = 5                      # Leverage 5x
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum bursa ($5.0)

    # --- Limit Order & Anti-FOMO Settings ---
    LIMIT_TIMEOUT_SECONDS: int = 30        # Batalkan limit order jika tidak terisi dalam 30 detik
    POST_ONLY: bool = True                 # Memastikan hanya dieksekusi sebagai Maker fee

    # --- Indicator Parameters ---
    EMA_TREND: int = 200                   # Filter tren besar (Trend Regime)
    EMA_FAST: int = 9                      # Trigger cepat EMA 9
    EMA_SLOW: int = 21                     # Trigger konfirmasi EMA 21
    RSI_PERIOD: int = 14                   # Momentum filter RSI 14
    RSI_LONG_MIN: float = 50.0             # Syarat Long: RSI >= 50
    RSI_LONG_MAX: float = 68.0             # Batas atas Long: RSI <= 68 (hindari pucuk)
    RSI_SHORT_MAX: float = 50.0            # Syarat Short: RSI <= 50
    RSI_SHORT_MIN: float = 32.0            # Batas bawah Short: RSI >= 32 (hindari dasar oversold)
    ATR_PERIOD: int = 14                   # Volatilitas adaptif

    # --- Risk / Reward Ratio (1:2 RRR) ---
    SL_PERCENT: float = 0.005              # Stop Loss tetap -0.5% ($0.05 pada modal $10)
    TP_PERCENT: float = 0.010              # Take Profit tetap +1.0% ($0.10 pada modal $10)
    RR_RATIO: float = 2.0                  # Risk to Reward 1:2
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

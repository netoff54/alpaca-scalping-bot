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

    # --- Database Neon Tech (PostgreSQL Cloud) ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_9cdnsQ6YefiX@ep-small-butterfly-b4dv7o7m-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )

    # --- Market Scanning (Timeframe 1m) ---
    TOP_COINS_LIMIT: int = 20              # Pindai 20 koin paling likuid & volatil di Binance Futures
    SCAN_INTERVAL_SECONDS: int = 15        # Selaras dengan candle 1m (pemindaian cepat setiap 15 detik)
    TIMEFRAME: str = "1m"                  # Timeframe 1 menit sesuai instruksi
    CANDLE_LIMIT: int = 220                # 220 candle untuk perhitungan EMA 200 yang presisi

    # --- Account & Risk Management ---
    DEFAULT_CAPITAL: float = 10.0          # Modal dasar $10
    RISK_PORTFOLIO_PERCENT: float = 0.005  # Posisi 0.5% dari total portofolio (Kalo $100 cukup $0.5)
    COMPOUNDING_ENABLED: bool = True       # Selalu compounding dengan risiko stabil
    LEVERAGE: int = 10                     # Leverage 10x
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only - Fee Rendah)
    CLOSE_ORDER_TYPE: str = "LIMIT"        # WAJIB LIMIT ORDER KELUAR (Maker Close - Post Only GTX)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum Binance ($5.0)
    MAX_ORDER_NOTIONAL: float = 6.50       # Batas maksimal notional agar margin tetap ~$0.50 (Mencegah koin raksasa seperti BTC yang memakan margin $8)

    # --- Limit Order & Anti-FOMO Settings ---
    LIMIT_TIMEOUT_SECONDS: int = 30        # Batalkan limit order jika tidak terisi dalam 30 detik
    POST_ONLY: bool = True                 # Memastikan hanya dieksekusi sebagai Maker fee (GTX)

    # --- Sentimen Arus Pasar (Long/Short Account Ratio) ---
    LS_RATIO_MIN_BUY: float = 0.90         # Syarat Long: Rasio L/S >= 0.90 (Tidak melawan arus dominan short)
    LS_RATIO_MAX_SELL: float = 1.15        # Syarat Short: Rasio L/S <= 1.15 (Tidak melawan arus dominan long)
    USE_N_PATTERN: bool = True             # Aktifkan validasi Pola N (Impulse -> Pullback -> Breakout)

    # --- Indicator Parameters ---
    EMA_TREND: int = 200                   # Filter tren besar (Trend Regime)
    EMA_FAST: int = 9                      # Trigger cepat EMA 9
    EMA_SLOW: int = 21                     # Trigger konfirmasi EMA 21
    RSI_PERIOD: int = 14                   # Momentum filter RSI 14
    RSI_LONG_MIN: float = 52.0             # Syarat Long: RSI >= 52 (Momentum bersih)
    RSI_LONG_MAX: float = 66.0             # Batas atas Long: RSI <= 66 (hindari pucuk)
    RSI_SHORT_MAX: float = 48.0            # Syarat Short: RSI <= 48 (Momentum turun)
    RSI_SHORT_MIN: float = 34.0            # Batas bawah Short: RSI >= 34 (hindari dasar oversold)
    ATR_PERIOD: int = 14                   # Volatilitas adaptif

    # --- Risk / Reward Ratio (Stop Loss 1.0%) ---
    SL_PERCENT: float = 0.010              # Stop Loss tepat 1.0% (Sesuai instruksi)
    TP_PERCENT: float = 0.018              # Take Profit 1.8% (Risk to Reward 1:1.8)
    RR_RATIO: float = 1.80                 # Risk to Reward 1:1.8
    BREAK_EVEN_TRIGGER: float = 0.005      # Geser SL ke Break-Even (+0.05%) saat profit mencapai +0.5%
    TRAILING_STOP_TRIGGER: float = 0.009   # Aktifkan trailing stop saat profit mencapai +0.9%
    TRAILING_STOP_DISTANCE: float = 0.004  # Jarak trailing 0.4% dari harga puncak
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

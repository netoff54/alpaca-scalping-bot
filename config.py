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

    # --- Account & Risk-Budget Management (0.5% Risiko Portofolio) ---
    DEFAULT_CAPITAL: float = 10.0          # Modal dasar $10
    RISK_PORTFOLIO_PERCENT: float = 0.005  # Resikokan 0.5% dari total portofolio (misal jika $100 -> resiko tepat $0.50)
    COMPOUNDING_ENABLED: bool = True       # Compounding dinamis berdasarkan saldo
    LEVERAGE: int = 10                     # Leverage basis (disesuaikan dinamis 10x - 20x sesuai analisis)
    DYNAMIC_LEVERAGE_ENABLED: bool = True  # Aktifkan penyesuaian leverage dinamis (10x - 20x) berdasarkan skor sinyal
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only - Fee Rendah)
    CLOSE_ORDER_TYPE: str = "LIMIT"        # WAJIB LIMIT ORDER KELUAR (Maker Close - Post Only GTX)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum Binance ($5.0)
    MAX_ORDER_NOTIONAL: float = 6.50       # Batas maksimal notional untuk akun modal mikro agar margin tetap ~$0.25 - $0.50

    # --- Limit Order & Anti-FOMO Settings ---
    LIMIT_TIMEOUT_SECONDS: int = 30        # Batalkan limit order jika tidak terisi dalam 30 detik
    POST_ONLY: bool = True                 # Memastikan hanya dieksekusi sebagai Maker fee (GTX)

    # --- Sentimen Arus Pasar (Long/Short Account Ratio) ---
    LS_RATIO_MIN_BUY: float = 0.90         # Syarat Long: Rasio L/S >= 0.90 (Tidak melawan arus dominan short)
    LS_RATIO_MAX_SELL: float = 1.15        # Syarat Short: Rasio L/S <= 1.15 (Tidak melawan arus dominan long)

    # --- Indicator Parameters: RSI 20-30 BUY & RSI 70-80 SELL + EMA Cross & Candlestick ---
    EMA_TREND: int = 200                   # Filter tren makro
    EMA_FAST: int = 9                      # Trigger cepat EMA 9
    EMA_SLOW: int = 21                     # Trigger konfirmasi EMA 21
    RSI_PERIOD: int = 14                   # Periode RSI 14
    RSI_BUY_MIN: float = 20.0              # Batas bawah BUY: RSI >= 20.0
    RSI_BUY_MAX: float = 30.0              # Batas atas BUY: RSI <= 30.0 (Area oversold 20-30)
    RSI_SELL_MIN: float = 70.0             # Batas bawah SELL: RSI >= 70.0 (Area overbought 70-80)
    RSI_SELL_MAX: float = 80.0             # Batas atas SELL: RSI <= 80.0
    ATR_PERIOD: int = 14                   # Volatilitas adaptif

    # --- Risk / Reward Ratio 1:2 & Fleksibilitas Pembalikan ---
    SL_PERCENT: float = 0.010              # Stop Loss dasar tepat 1.0% (Resiko 0.5% portofolio)
    TP_PERCENT: float = 0.020              # Take Profit penuh tepat 2.0% (Risk to Reward 1:2 -> Cuan 2x resiko)
    RR_RATIO: float = 2.00                 # Risk to Reward 1:2
    ENABLE_FLEXIBLE_EXIT: bool = True      # Keluar fleksibel jika candlestick & indikator membalik arah
    REVERSAL_PROFIT_TRIGGER: float = 0.003 # Amankan profit jika ada pembalikan saat profit >= +0.3%
    BREAK_EVEN_TRIGGER: float = 0.006      # Geser SL ke Break-Even (+0.05%) saat profit mencapai +0.6%
    TRAILING_STOP_TRIGGER: float = 0.012   # Aktifkan trailing stop saat profit mencapai +1.2%
    TRAILING_STOP_DISTANCE: float = 0.005  # Jarak trailing 0.5% dari harga puncak
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

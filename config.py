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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # --- Market Scanning: Rotasi 20 Koin x 10 Batch = 200 Koin Crypto Murni ---
    SCAN_UNIVERSE_LIMIT: int = 200         # Total 200 koin crypto murni (non-stablecoin)
    ROTATION_BATCH_SIZE: int = 20          # Ukuran batch per rotasi: 20 koin per siklus
    TOTAL_ROTATIONS: int = 10              # 10 kali rotasi berturut-turut (10 x 20 = 200 koin)
    TOP_COINS_LIMIT: int = 20              # Kompatibilitas alias ke 20 koin per siklus
    MIN_24H_VOLUME_USD: float = 3_000_000.0   # Minimal volume $3M agar semesta 200 koin terpenuhi
    SCAN_INTERVAL_SECONDS: int = 15        # Siklus rotasi setiap 15 detik (10 rotasi = 150 detik / 2.5 menit full scan)
    TIMEFRAME: str = "1m"                  # Timeframe 1 menit
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

    # --- Risk / Reward Ratio 1:2 & Fleksibilitas Pembalikan (Opsi A) ---
    SL_PERCENT: float = 0.007              # Stop Loss diperketat ke 0.7% (Resiko 0.5% portofolio)
    TP_PERCENT: float = 0.014              # Take Profit 1.4% (Risk to Reward 1:2 -> Cuan 2x resiko)
    RR_RATIO: float = 2.00                 # Risk to Reward 1:2
    ENABLE_FLEXIBLE_EXIT: bool = True      # Keluar fleksibel jika candlestick & indikator membalik arah
    REVERSAL_PROFIT_TRIGGER: float = 0.003 # Amankan profit jika ada pembalikan saat profit >= +0.3%
    BREAK_EVEN_TRIGGER: float = 0.0045     # Geser SL ke Break-Even (+0.05%) saat profit mencapai +0.45%
    TRAILING_STOP_TRIGGER: float = 0.009   # Aktifkan trailing stop saat profit mencapai +0.9%
    TRAILING_STOP_DISTANCE: float = 0.0035 # Jarak trailing 0.35% dari harga puncak
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

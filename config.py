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

    # --- Market Scanning: 500 Koin Murni, 1 Koin Per Rotasi (Analisis Menyeluruh) ---
    SCAN_UNIVERSE_LIMIT: int = 500         # Total hingga 500 koin crypto murni (non-stablecoin)
    ROTATION_BATCH_SIZE: int = 1           # 1 Koin per rotasi (Analisis Menyeluruh, Bukan Screening Singkat)
    TOTAL_ROTATIONS: int = 500             # 500 rotasi berurutan dari koin 1 s/d koin 500
    TOP_COINS_LIMIT: int = 1               # 1 koin per rotasi
    MIN_24H_VOLUME_USD: float = 1_000_000.0   # Minimal volume $1M agar semesta 500 koin terpenuhi
    SCAN_INTERVAL_SECONDS: int = 3         # Siklus 3 detik per koin (500 koin = 25 menit 1 siklus penuh)
    TIMEFRAME: str = "5m"                  # Timeframe eksekusi scalping 5 menit (Sesuai Akademi Crypto)
    STRUCTURE_TIMEFRAME: str = "15m"       # Timeframe struktur pasar, S&R teruji, & Area Likuidasi 15 menit
    CANDLE_LIMIT: int = 150                # 150 candle untuk perhitungan EMA 13/21/200 yang presisi
    MIN_SETUP_SCORE: float = 80.0          # Skor minimal agar sinyal dieksekusi (hanya setup matang)

    # --- Account & Risk-Budget Management (Leverage Range 50x -> 20x) ---
    DEFAULT_CAPITAL: float = 10.0          # Modal dasar $10
    FIXED_MARGIN_LOW_BALANCE: float = 1.00 # Margin tepat $1.00 jika saldo < $100 (Maksimal $1.00)
    MAX_MARGIN_LOW_BALANCE: float = 1.00   # Batas maksimal ketat margin $1.00 jika saldo < $100
    BALANCE_THRESHOLD_SCALING: float = 100.0# Batas ambang $100 untuk beralih ke 1.0% margin fleksibel
    RISK_PORTFOLIO_PERCENT: float = 0.01   # 1.0% margin fleksibel dari total portofolio jika saldo >= $100 (Compounding)
    COMPOUNDING_ENABLED: bool = True       # Compounding dinamis berdasarkan saldo
    LEVERAGE: int = 50                     # Leverage 50x target utama
    LEVERAGE_MAX: int = 50                 # Batas atas leverage (50x diutamakan)
    LEVERAGE_MIN: int = 20                 # Batas bawah leverage (20x ketat: koin di bawah 20x langsung di-skip demi mencegah pembengkakan margin)
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only - Fee Rendah)
    CLOSE_ORDER_TYPE: str = "LIMIT"        # WAJIB LIMIT ORDER KELUAR (Maker Close - Post Only GTX)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum Binance ($5.0)
    MAX_ORDER_NOTIONAL: float = 55.00      # Batas maksimal notional untuk akun modal mikro (Target notional $50 pada margin $1.00)

    # --- Limit Order & Anti-FOMO Settings ---
    LIMIT_TIMEOUT_SECONDS: int = 30        # Batalkan limit order jika tidak terisi dalam 30 detik
    POST_ONLY: bool = True                 # Memastikan hanya dieksekusi sebagai Maker fee (GTX)

    # --- Sentimen Arus Pasar (Long/Short Account Ratio & Derivatives) ---
    LS_RATIO_MIN_BUY: float = 0.90         # Syarat Long: Rasio L/S >= 0.90
    LS_RATIO_MAX_SELL: float = 1.15        # Syarat Short: Rasio L/S <= 1.15

    # --- Parameter Strategi Akademi Crypto (Kalimasada) ---
    # Formula: Price Action + S&R/Supply-Demand + EMA 13/21 Retest + Volume + Data Derivatif (OI/CVD)
    EMA_FAST: int = 13                     # EMA 13 (Sesuai video: Moving Average scalping ideal)
    EMA_SLOW: int = 21                     # EMA 21 (Sesuai video: Moving Average scalping ideal)
    EMA_TREND: int = 200                   # EMA 200 (Filter tren makro pasar)
    ATR_PERIOD: int = 14                   # Pengukuran volatilitas
    RSI_PERIOD: int = 14                   # Relative Strength Index (Poin 7 Kalimasada)
    VOLUME_SPIKE_FACTOR: float = 1.15      # Konfirmasi volume transaksi >= 115% rata-rata

    # --- Risk / Reward Ratio Presisi Dollar 1:2 Riil (SL 0.75% -> Net ~$0.19 & TP 2.00% -> Net ~$0.38+) ---
    SL_PERCENT: float = 0.0075             # Stop Loss 0.75% (Gross -$0.150 + Fee & Slippage = Net Loss Riil -$0.18 s/d -$0.19 / 1R Risiko)
    TP_PERCENT: float = 0.0200             # Take Profit 2.00% (Gross +$0.400 - Fee ~$0.018 = Net Win Riil +$0.38 s/d +$0.40 / 2R Untung Tepat 2x $SL)
    RR_RATIO: float = 2.00                 # Rasio Risk-to-Reward 1:2 Murni Seimbang Dollar Riil Dompet
    BEP_PROFIT_TRIGGER: float = 0.0075     # Saat profit mencapai 1R (+0.75%), geser SL ke BEP
    BEP_LOCK_PROFIT: float = 0.0025        # Kunci profit +0.25% (Menutup 100% fee bursa 0.08% + buffer slippage + garansi cuan bersih > $0.035)
    MAX_SPREAD_PERCENT: float = 0.0008     # Batas maksimal spread bid-ask 0.08% (Anti-Slippage & Anti-Illiquid Books)
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

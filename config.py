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
    MIN_24H_VOLUME_USD: float = 5_000_000.0# Minimal volume $5M agar koin likuid, orderbook tebal, bebas slippage & wick manipulation (Top 250+ Koin Binance)
    SCAN_INTERVAL_SECONDS: int = 8         # Siklus aman 8 detik per koin (hemat kuota weight bursa 96%, bebas shutdown rate-limit)
    TIMEFRAME: str = "15m"                 # Timeframe eksekusi entry 15 menit (Sesuai Akademi Crypto Kalimasada)
    STRUCTURE_TIMEFRAME: str = "1h"        # Timeframe struktur pasar, S&R teruji, & Area Likuidasi 1 Jam
    MACRO_TIMEFRAME: str = "4h"            # Timeframe tren makro institusi (EMA 200) 4 Jam
    CANDLE_LIMIT: int = 1000               # 1000 candle untuk minimalkan noise & validasi S&R / EMA presisi
    MIN_SETUP_SCORE: float = 80.0          # Skor minimal agar sinyal dieksekusi (hanya setup matang)

    # --- Account & Risk-Budget Management (Leverage Range 50x -> 20x) ---
    INITIAL_CAPITAL: float = 101.15        # Modal awal riil pengguna di Binance Futures ($101.15)
    DEFAULT_CAPITAL: float = 10.0          # Modal dasar cadangan jika saldo kosong ($10)
    FIXED_MARGIN_LOW_BALANCE: float = 1.00 # Margin tepat $1.00 jika saldo < $100 (Maksimal ketat $1.00)
    MAX_MARGIN_LOW_BALANCE: float = 1.00   # Batas maksimal ketat margin $1.00 jika saldo < $100
    BALANCE_THRESHOLD_SCALING: float = 100.0# Batas ambang $100 untuk beralih ke 1.0% margin fleksibel
    RISK_PORTFOLIO_PERCENT: float = 0.01   # 1.0% margin fleksibel dari total portofolio jika saldo >= $100 (Compounding)
    COMPOUNDING_ENABLED: bool = True       # Compounding dinamis berdasarkan saldo
    LEVERAGE: int = 50                     # Leverage 50x target utama
    LEVERAGE_MAX: int = 50                 # Batas atas leverage (50x diutamakan)
    LEVERAGE_MIN: int = 20                 # Batas bawah leverage: 20x (<35 hari) / 25x (>=35 hari)
    FUTURES_ACTIVATION_TIMESTAMP: float = 1791861617.021 # 13 Oktober 2026, 10:20:17 WIB
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only - Fee Rendah)
    CLOSE_ORDER_TYPE: str = "LIMIT"        # WAJIB LIMIT ORDER KELUAR (Maker Close - Post Only GTX)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum Binance ($5.0)

    @property
    def dynamic_min_leverage(self) -> int:
        """Batas bawah leverage: 25x setelah 35 hari, atau 20x sebelum 35 hari."""
        import time
        days = (time.time() - self.FUTURES_ACTIVATION_TIMESTAMP) / 86400.0
        return 25 if days >= 35.0 else 20

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

    # --- Risk / Reward Ratio Kalibrasi Grid Kalimasada (Win Rate >= 50%, Surplus >= 10%/bulan) ---
    SL_PERCENT: float = 0.0080             # Stop Loss presisi 0.80% (Cepat batasi risiko, hindari wick noise)
    TP_PERCENT: float = 0.0150             # Take Profit presisi 1.50% (Sering tercapai pada ekspansi impulsive 15m)
    BEP_PROFIT_TRIGGER: float = 0.0100     # Pemicu Break-Even saat profit mencapai +1.00%
    BEP_LOCK_PROFIT: float = 0.0030        # Kunci profit bersih saat BEP aktif (+0.30% setelah fee bursa)
    RR_RATIO: float = 1.875                # Rasio Risk-to-Reward Net Bersih 1:1.875
    STRUCTURAL_SL_ENABLED: bool = True     # Stop Loss struktural berbasis ekor lilin Price Action
    MIN_SL_PERCENT: float = 0.0080         # Batas bawah risiko 0.80% (Anti-Wick Noise Altcoin)
    MAX_SL_PERCENT: float = 0.0120         # Batas atas risiko 1.20% (Terkontrol ketat)
    BTC_FILTER_ENABLED: bool = True        # Kompas Makro BTC (Dilarang Long Altcoin jika BTC di bawah EMA 200 4 Jam)
    POST_SL_COOLDOWN_HOURS: float = 4.0    # Jeda cooldown 4 jam per koin setelah Stop Loss (Anti-Chop & Anti-Revenge Trading)
    CONSECUTIVE_LOSS_CIRCUIT_BREAKER: int = 3 # Circuit Breaker portofolio jika 3 loss berturut-turut
    CIRCUIT_BREAKER_PAUSE_HOURS: float = 36.0 # Jeda 36 jam untuk mendinginkan portofolio saat badai pasar
    MAX_SPREAD_PERCENT: float = 0.0008     # Batas maksimal spread bid-ask 0.08% (Anti-Slippage & Anti-Illiquid Books)
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

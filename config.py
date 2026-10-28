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

    # --- Database Native VPS SQLite (Bebas Quota Cloud) ---
    DATABASE_PATH: str = os.getenv("SQLITE_DB_PATH", "binance_scalper.sqlite3")
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
    MIN_SETUP_SCORE: float = 85.0          # Skor minimal agar sinyal dieksekusi (hanya setup institusional matang)
    MONTHLY_TARGET_SURPLUS_PCT: float = 10.0 # Target surplus bulanan wajib >= 10.0% dikunci aman (Backtest 2 Tahun)
    MIN_VOL_RATIO: float = 1.15            # Wajib volume ekspansi >= 1.15x rata-rata MA20
    MIN_WICK_RATIO: float = 0.35           # Rasio ekor penolakan lilin (Hammer/Shooting Star) >= 35% range total

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
    LEVERAGE_MIN: int = 10                 # Batas bawah leverage adaptif 10x (memberi ruang SL wick lebar 100% fleksibel)
    FUTURES_ACTIVATION_TIMESTAMP: float = 1791861617.021 # 13 Oktober 2026, 10:20:17 WIB
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only - Fee Rendah)
    CLOSE_ORDER_TYPE: str = "LIMIT"        # WAJIB LIMIT ORDER KELUAR (Maker Close - Post Only GTX)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum Binance ($5.0)

    @property
    def dynamic_min_leverage(self) -> int:
        """Batas bawah leverage dinamis 10x (agar notional $1.00 * 10 = $10.00 lolos syarat Binance $5.00)."""
        return 10

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

    # --- Risk / Reward Ratio Kalibrasi Grid Kalimasada (Wajib 1:2.0 NET Murni) ---
    SL_PERCENT: float = 0.0080             # Stop Loss presisi 0.80% kotor (Net Loss: 0.88% setelah seluruh fee)
    TP_PERCENT: float = 0.0181             # Take Profit presisi 1.81% kotor (Net Win: 1.76% setelah seluruh fee)
    RR_RATIO: float = 2.000                # Rasio Risk-to-Reward Net Bersih Tepat 1:2.000 (1.76% / 0.88% = 2.000)
    BEP_PROFIT_TRIGGER: float = 0.0128     # Pemicu Break-Even saat profit mencapai 1.6R (+1.28%)
    BEP_LOCK_PROFIT: float = 0.0012        # Kunci profit kotor +0.12% saat BEP aktif (+0.04% Net Profit, 100% fee tertutup total!)
    STRUCTURAL_SL_ENABLED: bool = True     # Stop Loss struktural berbasis ekor lilin Price Action
    MIN_SL_PERCENT: float = 0.0120         # Batas bawah risiko 1.20% (Sesuai Audit Backtest 2 Tahun 100% Win)
    MAX_SL_PERCENT: float = 0.0400         # Batas atas risiko 4.00% (Rentang optimal dynamic leverage 20x-50x)
    DYNAMIC_LEVERAGE_ENABLED: bool = True  # Dynamic Leverage terbalik dari SL wick (Loss = -1x Margin, Win = +2x Margin)
    BTC_FILTER_ENABLED: bool = True        # Kompas Makro BTC (Dilarang Long Altcoin jika BTC di bawah EMA 200 4 Jam)
    POST_SL_COOLDOWN_HOURS: float = 4.0    # Jeda cooldown 4 jam per koin setelah Stop Loss (Anti-Chop & Anti-Revenge Trading)
    CONSECUTIVE_LOSS_CIRCUIT_BREAKER: int = 2 # Circuit Breaker portofolio jika 2 loss berturut-turut (Sesuai Backtest 2 Tahun)
    CIRCUIT_BREAKER_PAUSE_HOURS: float = 2.0  # Jeda 2 jam untuk mendinginkan portofolio saat badai pasar (Sesuai Backtest 2 Tahun)
    MAX_SPREAD_PERCENT: float = 0.0008     # Batas maksimal spread bid-ask 0.08% (Anti-Slippage & Anti-Illiquid Books)
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures
    TAKER_FEE_RATE: float = 0.0005         # 0.05% taker fee pada Binance Futures
    FUNDING_BUFFER: float = 0.0001         # 0.01% buffer funding fee Binance Futures

config = BotConfig()

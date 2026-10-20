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
    MIN_24H_VOLUME_USD: float = 100_000.0  # Minimal volume $100k agar seluruh semesta 500 koin Binance Futures terakomodasi
    SCAN_INTERVAL_SECONDS: int = 3         # Siklus 3 detik per koin (500 koin = 25 menit 1 siklus penuh)
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
    LEVERAGE_MIN: int = 20                 # Batas bawah leverage 20x (Kompatibel penuh pembatasan akun Binance < 30 hari; koin < 20x di-skip agar tidak jomplang)
    MARGIN_MODE: str = "ISOLATED"          # WAJIB ISOLATED MARGIN
    ORDER_TYPE: str = "LIMIT"              # WAJIB LIMIT ORDER (Maker Only - Fee Rendah)
    CLOSE_ORDER_TYPE: str = "LIMIT"        # WAJIB LIMIT ORDER KELUAR (Maker Close - Post Only GTX)
    MIN_NOTIONAL: float = 5.0              # Nilai notional minimum Binance ($5.0)

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

    # --- Risk / Reward Ratio Presisi Dollar 1:2 NET Riil (Sudah Ditambahkan Seluruh Fee Bursa) ---
    # Fee Loss: Maker Entry 0.02% + Taker SL 0.05% = 0.07% -> Net Loss = 1.00% + 0.07% = 1.07% (-$0.5350 pada notional $50)
    # Fee Win: Maker Entry 0.02% + Maker TP 0.02% = 0.04% -> Gross TP 2.18% - 0.04% = Net Win 2.14% (+$1.0700 pada notional $50)
    # Rasio Dolar Bersih Riil Dompet: +$1.0700 / $0.5350 = TEPAT 1 : 2.00 NET
    SL_PERCENT: float = 0.0100             # Stop Loss 1.00% (Gross 1.00% + Fee 0.07% = Net Loss 1.07% / 1R Risiko)
    TP_PERCENT: float = 0.0218             # Take Profit 2.18% (Gross 2.18% - Fee 0.04% = Net Win 2.14% / Tepat 2x Net Loss 1.07%)
    RR_RATIO: float = 2.00                 # Rasio Risk-to-Reward 1:2.00 Net Bersih Sempurna Setelah Seluruh Biaya Transaksi
    BEP_PROFIT_TRIGGER: float = 0.0180     # Pemicu BEP saat profit mencapai 1.80% (memberi ruang napas penuh bagi trade menuju TP 2.18%)
    BEP_LOCK_PROFIT: float = 0.0035        # Kunci profit +0.35% (Menutup 100% fee bursa 0.07% + garansi cuan aman bersih > $0.14)
    MAX_SPREAD_PERCENT: float = 0.0008     # Batas maksimal spread bid-ask 0.08% (Anti-Slippage & Anti-Illiquid Books)
    MAKER_FEE_RATE: float = 0.0002         # 0.02% maker fee pada Binance Futures

config = BotConfig()

# Binance Futures Autonomous Scalper (Native Engine + Neon Tech)

Bot scalping otonom berbasis **Python Native REST API + FastAPI** yang memindai koin teratas di **Binance USDⓈ-M Futures**, tervalidasi dengan **Pola N (Breakout & Retest)**, **Sentimen Arus Long/Short Global**, dan dieksekusi 100% menggunakan **Maker Limit Order** (Post-Only GTX / fee terendah).

---

## Fitur Utama & Disiplin Risiko

1. **Model Risiko 0.5% Portofolio (Risk-Budget Sizing)**:
   - Resiko maksimal per trade dibatasi tepat **0.5% dari saldo kas** (misal saldo $100 -> resiko tepat $0.50; jika SL ya habis $0.50 tersebut).
   - Target keuntungan Take Profit penuh dirancang **2x dari risiko (Risk to Reward 1:2)**.
2. **Leverage Dinamis (10x s/d 20x)**:
   - Leverage disesuaikan secara dinamis tergantung rasio hasil analisis:
     - **Setup Istimewa (Skor $\ge 82$ & Pola N aktif):** Leverage **20x** (margin sangat hemat ~$0.25).
     - **Setup Kuat (Skor $\ge 72$):** Leverage **15x** (margin ~$0.34).
     - **Setup Standar (Skor $< 72$):** Leverage **10x** (margin ~$0.51).
3. **Exit Fleksibel Pembalikan Arah (*Anti-Kaku*)**:
   - Jika posisi sedang **PROFIT** ($\ge +0.3\%$) dan candlestick/indikator menunjukkan tanda pembalikan arah (*upper rejection wick*, *EMA death cross*, atau RSI melemah), bot **langsung Take Profit seketika** mengamankan keuntungan tanpa menunggu berbalik ke SL.
   - Jika posisi sedang **MINUS** dan terkonfirmasi breakdown di bawah EMA 21, bot melakukan **Early Cut Loss dini** (hanya -0.2% s/d -0.4%), mencegah kerugian menyentuh SL penuh (-1.0%).
4. **Timeframe 1 Menit (TF 1m Scalper)**:
   - Pemindaian candle 1 menit dengan filter momentum RSI ketat (52–62 untuk Long, 38–48 untuk Short) untuk mencegah masuk di pucuk atau dasar oversold.
5. **Proteksi Ukuran Akun Mikro**:
   - Filter `MAX_ORDER_NOTIONAL` ($6.50): Secara otomatis menyaring koin raksasa seperti BTCUSDT (di mana minimum lot 0.001 BTC bernilai $83+) sehingga margin selalu stabil di kisaran **~$0.25 – $0.50**.
6. **100% Limit Maker Order (Masuk & Keluar)**:
   - Order masuk dan penutupan posisi diprioritaskan menggunakan Limit Order Post-Only (`timeInForce=GTX`) pada harga terbaik untuk mendapatkan fee Maker terendah (0.02%).
7. **Database Neon Tech PostgreSQL Cloud**:
   - Schema terisolasi `binance_scalper` untuk merekam riwayat trade, riwayat sinyal, dan pertumbuhan saldo portofolio.

---

## Struktur File Proyek

- [`config.py`](config.py): Konfigurasi parameter bursa, modal, indikator, TF 1m, SL 1.0%, RRR 1:2, dan batas notional $6.50.
- [`strategy.py`](strategy.py): Algoritma matematis murni EMA, RSI, ATR, Pola N, kalkulasi leverage dinamis, dan risk-budget sizing.
- [`binance_client.py`](binance_client.py): Klien REST API Binance Futures Native (Zero CCXT), penanganan lot size, tick size, dan leverage.
- [`binance_bot.py`](binance_bot.py): Mesin pemindaian koin, eksekusi maker, pemantau posisi 5s, dan pemantau pembalikan arah fleksibel 10s.
- [`database.py`](database.py): Pengelola koneksi dan audit log Neon Tech PostgreSQL.
- [`main.py`](main.py): Service FastAPI untuk Render Cloud, keep-alive self-ping 24/7, dan REST API endpoints.

---

## REST Endpoints

- `GET /` : Dashboard ringkasan bot, saldo, koin dipantau, dan status rate limit.
- `GET /health` : Health check resmi Render Cloud (respon instan <1ms).
- `GET /positions` : Detail posisi aktif yang tersinkronisasi langsung dari Binance.
- `GET /scan-results` : Hasil pemindaian koin, analisis market regime, dan sinyal.
- `GET /outbound-ip` : Cek IP publik container Render.

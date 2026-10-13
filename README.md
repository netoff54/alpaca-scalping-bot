# Binance Futures Autonomous Scalper (Native Engine + Neon Tech)

Bot scalping otonom berbasis **Python Native REST API + FastAPI** yang memindai koin teratas di **Binance USDⓈ-M Futures**, tervalidasi dengan **Pola N (Breakout & Retest)**, **Sentimen Arus Long/Short Global**, dan dieksekusi 100% menggunakan **Maker Limit Order** (Post-Only GTX / fee terendah).

---

## Fitur Utama & Disiplin Risiko

1. **100% Limit Maker Order (Masuk & Keluar)**:
   - Order masuk menggunakan Limit Order Post-Only (`timeInForce=GTX`) pada harga terbaik untuk mendapatkan fee Maker terendah (0.02%) tanpa slippage.
   - Penutupan posisi (TP/SL) diprioritaskan menggunakan Limit Maker Exit sebelum beralih ke proteksi pasar darurat.
2. **Timeframe 1 Menit (TF 1m Scalper)**:
   - Pemindaian candle 1 menit dengan konfirmasi candle tertutup (`-2`), volume support aktif, dan price action tanpa rejection wick.
3. **Stop Loss 1.0% & Take Profit 2.0% (Risk to Reward 1:2)**:
   - Stop Loss tepat 1.0% dan Take Profit 2.0% (Risk to Reward 1:2).
   - Break-Even otomatis mengunci SL di Entry + 0.05% saat profit mencapai +0.6% (menutup biaya fee).
   - Trailing Stop dinamis mengunci keuntungan saat profit mencapai +1.2% (jarak 0.5% dari puncak).
4. **Proteksi Margin Ketat (~$0.50 per Posisi)**:
   - Alokasi margin: 0.5% portofolio (atau minimum notional ~$5.00 - $5.50 x 10x leverage = ~$0.50 margin).
   - Filter `MAX_ORDER_NOTIONAL` ($6.50): Menyaring koin raksasa seperti BTCUSDT yang memiliki ukuran minimum lot tinggi (0.001 BTC = $83+), mencegah penggunaan margin besar ($8+).
5. **Analisis Pola N & Sentimen Arus Pasar**:
   - Memvalidasi pembentukan struktur N-Wave Breakout (Bullish N / Bearish N).
   - Mengintegrasikan Binance Futures `globalLongShortAccountRatio` (anti-melawan arus pasar).
6. **Pemantauan Posisi Aktif Setiap 5 Detik**:
   - Loop frekuensi tinggi (5s) langsung memantau harga posisi terbuka secara presisi.
7. **Database Neon Tech PostgreSQL Cloud**:
   - Schema terisolasi `binance_scalper` untuk merekam riwayat trade, riwayat sinyal, dan pertumbuhan saldo portofolio.

---

## Struktur File Proyek

- [`config.py`](config.py): Konfigurasi terpusat parameter bursa, modal, indikator, TF 1m, SL 1.0%, dan batas notional $6.50.
- [`strategy.py`](strategy.py): Algoritma matematis murni EMA, RSI, ATR, Pola N, dan filter sentimen arus.
- [`binance_client.py`](binance_client.py): Klien REST API Binance Futures Native (Zero CCXT), penanganan presisi lot size & tick size.
- [`binance_bot.py`](binance_bot.py): Mesin pemindaian koin, filter ukuran akun, eksekusi limit maker, pemantau posisi aktif 5s.
- [`database.py`](database.py): Pengelola koneksi dan audit log Neon Tech PostgreSQL.
- [`main.py`](main.py): Service FastAPI untuk Render Cloud, keep-alive self-ping 24/7, dan REST API endpoints.

---

## REST Endpoints

- `GET /` : Dashboard ringkasan bot, saldo, koin dipantau, dan status rate limit.
- `GET /health` : Health check resmi Render Cloud (respon instan <1ms).
- `GET /positions` : Detail posisi aktif yang tersinkronisasi langsung dari Binance.
- `GET /scan-results` : Hasil pemindaian koin, analisis market regime, dan sinyal.
- `GET /outbound-ip` : Cek IP publik container Render.

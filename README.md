# Binance Futures Autonomous Scalper (Native Engine + Neon Tech)

Bot scalping otonom berbasis **Python Native REST API + FastAPI** yang memindai koin teratas di **Binance USDⓈ-M Futures**, tervalidasi dengan **Pola N (Breakout & Retest)**, **Sentimen Arus Long/Short Global**, dan dieksekusi 100% menggunakan **Maker Limit Order** (Post-Only GTX / fee terendah).

---

## Fitur Utama & Disiplin Risiko

1. **100% Limit Maker Order (Masuk & Keluar)**:
   - Order masuk menggunakan Limit Order Post-Only (`timeInForce=GTX`) pada harga terbaik untuk mendapatkan fee Maker terendah (0.02%) tanpa slippage.
   - Penutupan posisi (TP/SL) juga diprioritaskan menggunakan Limit Maker Exit sebelum beralih ke proteksi pasar darurat.
2. **Timeframe 5 Menit (TF 5m Anti-Noise)**:
   - Menghilangkan noise whip-saw 1 menit dengan konfirmasi candle 5m tertutup (`-2`), volume support aktif, dan price action tanpa rejection wick.
3. **Analisis Pola N (N-Wave Breakout & Retest)**:
   - Memvalidasi pembentukan swing low/high, Higher Low (Bullish N), atau Lower High (Bearish N) sebelum entry.
4. **Sentimen Arus Pasar (Anti-Melawan Arus)**:
   - Mengintegrasikan Binance Futures `globalLongShortAccountRatio`. Bot tidak akan membuka posisi yang melawan arus dominan pasar.
5. **Manajemen Risiko Adaptif & Compounding**:
   - Alokasi margin: 0.5% portofolio x 10x leverage (ISOLATED Margin).
   - Stop Loss adaptif berbasis ATR (1.2% - 1.8%).
   - Break-Even otomatis mengunci SL di Entry + 0.1% saat profit mencapai +0.6%.
   - Trailing Stop dinamis mengunci puncak saat profit mencapai +1.0%.
6. **Pemantauan Posisi Aktif Setiap 5 Detik**:
   - Loop frekuensi tinggi (5s) langsung memantau harga posisi terbuka, sedangkan pemindaian koin berjalan berkala dengan konsumsi IP weight rendah (<100/2400).
7. **Database Neon Tech PostgreSQL Cloud**:
   - Schema terisolasi `binance_scalper` untuk merekam riwayat trade, riwayat sinyal, dan pertumbuhan saldo portofolio.

---

## Struktur File Proyek

- [`config.py`](config.py): Konfigurasi terpusat parameter bursa, modal, indikator, TF 5m, dan alokasi risiko.
- [`strategy.py`](strategy.py): Algoritma matematis murni EMA, RSI, ATR, Pola N, dan filter sentimen arus.
- [`binance_client.py`](binance_client.py): Klien REST API Binance Futures Native (Zero CCXT), penanganan presisi lot size & tick size, auto-wait rate limit.
- [`binance_bot.py`](binance_bot.py): Mesin pemindaian koin, eksekusi limit maker, pemantau posisi aktif 5s, Break-Even & Trailing Stop.
- [`database.py`](database.py): Pengelola koneksi dan audit log Neon Tech PostgreSQL.
- [`main.py`](main.py): Service FastAPI untuk Render Cloud, keep-alive self-ping 24/7, dan REST API endpoints.

---

## REST Endpoints

- `GET /` : Dashboard ringkasan bot, saldo, koin dipantau, dan status rate limit.
- `GET /health` : Health check resmi Render Cloud (respon instan <1ms).
- `GET /positions` : Detail posisi aktif yang tersinkronisasi langsung dari Binance.
- `GET /scan-results` : Hasil pemindaian koin, analisis market regime, dan sinyal.
- `GET /outbound-ip` : Cek IP publik container Render.

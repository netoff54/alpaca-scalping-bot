# Bot Trading Scalping Otomatis (Modal $10)

Bot scalping otomatis berbasis **Python** dengan penegakan disiplin risiko:
1. **Always LIMIT ORDER (Maker Only)**: Menggunakan order buku untuk mendapatkan *fee* terendah (0.02% maker fee) dan mencegah *slippage*.
2. **Always ISOLATED Margin**: Margin terisolasi sebesar \$1 per posisi (5x leverage) untuk memastikan sisa saldo modal \$10 aman jika terjadi volatilitas ekstrim.
3. **Risiko 0.5% per Trade (\$0.05)**: Kerugian maksimal dibatasi hingga \$0.05 per posisi menggunakan Stop Loss adaptif berbasis ATR (Average True Range).
4. **Strategi Triple Filter Momentum**:
   - **Filter Tren**: EMA 200 (Long hanya saat Bullish, Short hanya saat Bearish).
   - **Trigger**: EMA 9 & EMA 21 Crossover (Golden Cross / Death Cross).
   - **Filter Momentum**: RSI 14 (Long jika > 50 & < 68, Short jika < 50 & > 32).
   - **Dynamic Exit**: ATR 14 dengan Risk-to-Reward Ratio (RRR) 1:2.

---

## Struktur File

- [`config.py`](file:///d:/bot%20trading/config.py): Konfigurasi parameter trading, exchange, modal, dan indikator.
- [`strategy.py`](file:///d:/bot%20trading/strategy.py): Perhitungan matematis EMA, RSI, ATR, sinyal posisi, dan ukuran lot.
- [`simulator.py`](file:///d:/bot%20trading/simulator.py): Engine simulasi *Paper Trading* langsung terhadap 1.000 candle riil Binance tanpa API key.
- [`live_bot.py`](file:///d:/bot%20trading/live_bot.py): Engine eksekusi Testnet/Live Binance dengan auto-cancel order menggantung.

---

## Cara Menjalankan

### 1. Uji Paper Trading / Backtest Terlebih Dahulu (Gratis & Tanpa API Key)
Gunakan perintah ini di terminal:
```powershell
py simulator.py
```
Script ini akan menarik 1.000 candle terbaru dari Binance, menghitung seluruh sinyal, mengeksekusi simulasi limit order, dan menampilkan tabel performa serta net profit setelah dipotong fee.

### 2. Menjalankan Bot di Binance Testnet / Live
1. Salin `.env.example` menjadi `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Isi `API_KEY` dan `API_SECRET` Anda di dalam `.env`.
3. Jalankan bot:
   ```powershell
   py live_bot.py
   ```

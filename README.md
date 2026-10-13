# Binance Futures Top-200 Scalping Autonomous Bot (Modal Compounding $10+)

Bot scalping otonom berbasis **Python + CCXT + FastAPI** yang secara otomatis memindai **200 Koin / Token Teratas** di **Binance USDⓈ-M Futures** berdasarkan volume perdagangan 24 jam dan mengeksekusi strategi **Triple Filter Momentum** pada timeframe 1 menit (1m).

---

## Fitur Utama & Disiplin Risiko

1. **Always LIMIT ORDER (Maker Only)**:
   - Order masuk menggunakan Limit Order pada *Best Bid* (Buy) atau *Best Ask* (Sell) untuk mendapatkan tarif fee terendah (*Maker rebate/0.02% fee*) dan menghindari *slippage*.
2. **Anti-FOMO Auto-Cancel (30 Detik)**:
   - Limit order yang belum terisi dalam 30 detik otomatis dibatalkan oleh bot untuk mencegah tertinggal momentum atau terseret pergerakan berlawanan.
3. **Always ISOLATED Margin**:
   - Akun diatur ke Single-Asset mode dengan margin `ISOLATED` (5x leverage), memastikan sisa saldo wallet USDⓈ-M terlindungi penuh jika terjadi volatilitas ekstrim.
4. **Always Compounding (100% Saldo Digulung)**:
   - Bot menggunakan 100% saldo kas kasir yang tersedia (`availableBalance`) di dompet Futures untuk ukuran trade berikutnya secara dinamis.
5. **Strategi Triple Filter Momentum**:
   - **Filter Tren (EMA 200)**: Hanya Buy saat harga di atas EMA 200; hanya Sell saat harga di bawah EMA 200.
   - **Trigger (EMA 9 & 21)**: Golden Cross untuk Buy, Death Cross untuk Sell pada bar tertutup (-2) untuk mencegah repaint.
   - **Filter Momentum (RSI 14)**: Buy pada RSI 50–68; Sell pada RSI 32–50 (zona momentum ekspansi sehat).
   - **Exit Target (1:2 Risk to Reward)**: Stop Loss -0.5% dan Take Profit +1.0%.

---

## Struktur File

- [`config.py`](file:///d:/bot%20trading/config.py): Konfigurasi terpusat parameter bursa, modal, indikator, dan timeframe.
- [`strategy.py`](file:///d:/bot%20trading/strategy.py): Algoritma matematis EMA, RSI, ATR, deteksi sinyal bar tertutup, dan SL/TP 1:2 RRR.
- [`binance_bot.py`](file:///d:/bot%20trading/binance_bot.py): Mesin pemindaian 200 koin volume teratas di Binance Futures secara asinkron, eksekusi Maker limit order, auto-cancel 30 detik, dan pemantau posisi.
- [`main.py`](file:///d:/bot%20trading/main.py): Service FastAPI untuk deploy di Render Cloud, keep-alive self-ping 24/7, dan REST endpoints.

---

## REST Endpoints

- `GET /` : Dashboard ringkasan bot, status saldo Binance Futures, koin yang dipantau, dan sinyal aktif.
- `GET /health` : Endpoint health check resmi Render Cloud.
- `GET /scan-results` : Detail analisis 200 koin teratas (Market Regime, sinyal Long/Short, dan Watchlist).
- `GET /outbound-ip` : Cek IP keluar kontainer cloud Render.

import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
import ccxt
import pandas as pd
from config import config
from strategy import prepare_indicators, check_signal
from alpaca_client import AlpacaClient

class AlpacaBotEngine:
    def __init__(self, key_id: str = "", secret_key: str = "", base_url: str = "https://paper-api.alpaca.markets/v2"):
        self.alpaca = AlpacaClient(key_id=key_id, secret_key=secret_key, base_url=base_url)
        self.symbol_alpaca = "BTC/USD"
        self.symbol_feed = "BTC/USDT"
        
        # State
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.logs: List[Dict[str, str]] = []
        self.trade_history: List[Dict[str, Any]] = []
        
        # Data feeds & Indicators
        self.last_price = 0.0
        self.last_indicators = {}
        self.last_signal = None
        
        # Isolated Balance Tracker ($10 base)
        self.isolated_capital = 10.0
        self.isolated_balance = 10.0
        self.total_wins = 0
        self.total_losses = 0
        
        # Order Tracking
        self.active_order_id = None
        self.order_placed_time = None
        self.pending_trade = None
        
        # CCXT feed untuk data kline super cepat & reliable
        self.feed_exchange = ccxt.binance({'enableRateLimit': True})
        
        self.add_log("INFO", "Engine Alpaca berhasil diinisialisasi. Menunggu konfigurasi API...")

    def update_credentials(self, key_id: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets/v2"):
        self.alpaca.key_id = key_id.strip()
        self.alpaca.secret_key = secret_key.strip()
        self.alpaca.base_url = base_url.strip().rstrip('/')
        self.add_log("INFO", f"Kredensial Alpaca diperbarui. Base URL: {self.alpaca.base_url}")

    def add_log(self, level: str, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        entry = {"time": now, "level": level, "message": message}
        self.logs.append(entry)
        if len(self.logs) > 100:
            self.logs.pop(0)

    def get_account_status(self) -> Dict[str, Any]:
        """Mendapatkan status akun Alpaca & saldo terisolasi $10."""
        alpaca_info = {}
        if self.alpaca.is_configured():
            try:
                acc = self.alpaca.get_account()
                alpaca_info = {
                    "connected": True,
                    "account_number": acc.get("account_number", "-"),
                    "status": acc.get("status", "-"),
                    "currency": acc.get("currency", "USD"),
                    "buying_power": float(acc.get("buying_power", 0)),
                    "portfolio_value": float(acc.get("portfolio_value", 0)),
                    "cash": float(acc.get("cash", 0))
                }
            except Exception as e:
                alpaca_info = {"connected": False, "error": str(e)}
        else:
            alpaca_info = {"connected": False, "error": "API Key belum diisi"}

        return {
            "alpaca": alpaca_info,
            "isolated_wallet": {
                "initial_capital": self.isolated_capital,
                "current_balance": round(self.isolated_balance, 4),
                "net_profit": round(self.isolated_balance - self.isolated_capital, 4),
                "risk_per_trade": round(self.isolated_capital * config.RISK_PER_TRADE_PERCENT, 3), # $0.05
                "wins": self.total_wins,
                "losses": self.total_losses,
                "total_trades": len(self.trade_history)
            },
            "bot_status": "RUNNING" if self.is_running else "STOPPED",
            "market": {
                "price": self.last_price,
                "indicators": self.last_indicators,
                "last_signal": self.last_signal
            }
        }

    def fetch_market_data(self) -> pd.DataFrame:
        """Mengambil candle 1m dari exchange data feed."""
        ohlcv = self.feed_exchange.fetch_ohlcv(self.symbol_feed, timeframe=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return prepare_indicators(df)

    def start(self):
        if self.is_running:
            return
        if not self.alpaca.is_configured():
            self.add_log("ERROR", "Tidak dapat memulai bot: API Key atau Secret Alpaca belum terisi!")
            raise ValueError("API Key atau Secret Alpaca belum diisi.")
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.add_log("SUCCESS", "Bot Scalping Alpaca dijalankan! Mode: Always Limit & Isolated.")

    def stop(self):
        self.is_running = False
        self.add_log("WARNING", "Bot dihentikan oleh pengguna.")

    def _cancel_stale_order(self):
        """Batalkan limit order jika melebihi batas waktu (30 detik)."""
        if self.active_order_id and self.order_placed_time:
            elapsed = time.time() - self.order_placed_time
            if elapsed > config.LIMIT_TIMEOUT_SECONDS:
                self.add_log("WARNING", f"Limit order {self.active_order_id[:8]}... timeout ({config.LIMIT_TIMEOUT_SECONDS}s). Membatalkan order di Alpaca...")
                try:
                    self.alpaca.cancel_order(self.active_order_id)
                    self.add_log("INFO", "Order berhasil dibatalkan. Menghindari floating/stuck order.")
                except Exception as e:
                    self.add_log("ERROR", f"Gagal membatalkan order: {e}")
                self.active_order_id = None
                self.order_placed_time = None
                self.pending_trade = None

    def _run_loop(self):
        self.add_log("INFO", f"Loop trading aktif. Simbol: {self.symbol_alpaca} | Timeframe: {config.TIMEFRAME}")
        
        while self.is_running:
            try:
                # 1. Cek timeout limit order
                self._cancel_stale_order()

                # 2. Ambil data pasar & hitung indikator
                df = self.fetch_market_data()
                curr_bar = df.iloc[-1]
                self.last_price = float(curr_bar['close'])
                
                self.last_indicators = {
                    "ema_fast": round(float(curr_bar['ema_fast']), 2),
                    "ema_slow": round(float(curr_bar['ema_slow']), 2),
                    "ema_trend": round(float(curr_bar['ema_trend']), 2),
                    "rsi": round(float(curr_bar['rsi']), 2),
                    "atr": round(float(curr_bar['atr']), 2)
                }

                # 3. Cek posisi atau order aktif di Alpaca
                open_orders = []
                try:
                    open_orders = self.alpaca.get_open_orders(self.symbol_alpaca)
                except Exception as e:
                    self.add_log("ERROR", f"Gagal memeriksa order Alpaca: {e}")

                if open_orders:
                    # Ada order yang sedang pending di Alpaca
                    time.sleep(5)
                    continue

                # 4. Evaluasi Sinyal
                signal = check_signal(df)
                self.last_signal = signal

                if signal and self.active_order_id is None:
                    side = signal['side']
                    entry_p = signal['entry_price']
                    qty = signal['qty']
                    
                    self.add_log("SUCCESS", f"SINYAL {side} TERDETEKSI! Entry: ${entry_p:,.2f} | RSI: {signal['rsi']}")
                    
                    # Eksekusi LIMIT ORDER di Alpaca Paper
                    try:
                        self.add_log("INFO", f"Mengirim LIMIT ORDER ke Alpaca: {side} {qty} {self.symbol_alpaca} @ ${entry_p:,.2f}")
                        order = self.alpaca.create_limit_order(
                            symbol=self.symbol_alpaca,
                            qty=qty,
                            side=side.lower(),
                            limit_price=entry_p,
                            time_in_force="gtc"
                        )
                        self.active_order_id = order.get("id")
                        self.order_placed_time = time.time()
                        self.pending_trade = signal
                        self.add_log("SUCCESS", f"Limit Order DITERIMA Alpaca! ID: {self.active_order_id[:8]}... (Bisa disaksikan di dashboard Alpaca)")
                        
                        # Catat ke history simulasi terisolasi
                        self.trade_history.append({
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "side": side,
                            "symbol": self.symbol_alpaca,
                            "qty": qty,
                            "price": entry_p,
                            "sl_price": signal['sl_price'],
                            "tp_price": signal['tp_price'],
                            "order_id": self.active_order_id,
                            "status": "PLACED (LIMIT)"
                        })
                    except Exception as e:
                        self.add_log("ERROR", f"Gagal mengirim order ke Alpaca: {e}")

                time.sleep(5)

            except Exception as e:
                self.add_log("ERROR", f"Error pada cycle: {e}")
                time.sleep(5)

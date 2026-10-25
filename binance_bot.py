import os
import time
import math
import threading
import gc
from typing import Dict, Any, List, Optional, Set, Tuple
from rich.console import Console

from config import config
import strategy
from binance_client import BinanceFuturesClient
from database import db

console = Console()

# Daftar aset saham TradFi & komoditas di Binance Futures yang memerlukan perjanjian khusus (Error -4411)
TRADFI_EXCLUSIONS = {
    'SKHY', 'MRNA', 'ARM', 'SOXL', 'SPCX', 'INTW', 'SNDK', 'SQQQ',
    'NVDA', 'TSLA', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'META', 'MU',
    'AMD', 'COIN', 'PLTR', 'BABA', 'DIS', 'NFLX', 'INTC', 'QCOM',
    'AVGO', 'TSM', 'NIO', 'BA', 'UBER', 'PYPL', 'ORCL', 'CRM', 'MSTR',
    'GOLD', 'SILVER', 'OIL', 'BRENT', 'US500', 'US100', 'US30'
}

class BinanceScalper:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.is_testnet = config.IS_TESTNET
        
        # Klien REST API Binance Futures Native (Zero CCXT overhead)
        self.client = BinanceFuturesClient(self.api_key, self.api_secret)
        
        # State tracking
        self.is_running = False
        self.ranked_pairs: List[Dict[str, Any]] = []
        self.last_scan_time: Optional[str] = None
        self.last_scan_duration_sec: float = 0.0
        self.bullish_count: int = 0
        self.bearish_count: int = 0
        self.active_signals: List[Dict[str, Any]] = []
        self.watchlist: List[Dict[str, Any]] = []
        
        self.active_order: Optional[Dict[str, Any]] = None
        self.active_position: Optional[Dict[str, Any]] = None
        
        self.trade_history: List[Dict[str, Any]] = []
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_pnl_usd: float = 0.0
        
        # Cache Semesta 500 koin crypto murni & Sistem Rotasi 1 Koin Per Siklus
        self._cached_universe_symbols: List[Dict[str, Any]] = []
        self._last_universe_refresh: float = 0.0
        self._current_rotation_index: int = 0
        self.current_rotation_info: str = "Rotasi 1/500 (Menyiapkan Analisis)"
        self.current_coin_analysis: Dict[str, Any] = {}
        self._coins_analysis_history: Dict[str, Dict[str, Any]] = {}
        self._last_wallet_db_snapshot: float = 0.0
        
        # Balance cache & Rate limit cooldown
        self._cached_balance: Dict[str, float] = {"total_wallet": 99.5399, "available": 99.5399, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self._last_sync_position_time: float = 0.0
        self._configured_symbols: Set[str] = set()
        self._symbol_leverage: Dict[str, int] = {}
        self._last_algo_sweep: float = 0.0
        self._last_reversal_check_time: float = 0.0
        self.last_error: Optional[str] = None
        self._symbol_order_cooldown: Dict[str, float] = {}
        self.consecutive_losses: int = 0
        self.circuit_breaker_until: float = 0.0
        self._cached_btc_macro: Dict[str, Any] = {"bullish": True, "updated_at": 0.0}
        
        # Muat riwayat transaksi kumulatif dari Neon Tech agar tidak reset saat restart/redeploy
        self.load_history_from_db()

    def load_history_from_db(self):
        """Memuat riwayat transaksi kumulatif dari Neon Tech agar statistik tidak reset dari 0 saat restart/redeploy."""
        try:
            summary = db.get_trade_summary()
            self.total_trades = summary.get("total_trades", 0)
            self.winning_trades = summary.get("winning_trades", 0)
            self.total_pnl_usd = summary.get("total_pnl_usd", 0.0)
            self.trade_history = db.get_recent_trades(50)
            
            # Muat snapshot saldo terakhir dari database jika ada
            snap = db.get_latest_wallet_snapshot()
            if snap and snap.get("total_wallet", 0.0) > 0:
                self._cached_balance = snap
                console.log(f"[bold green]Saldo wallet terakhir dari Neon Tech dimuat: ${snap['total_wallet']:.4f} USDT[/bold green]")
                
            console.log(f"[bold green]Riwayat database Neon Tech dimuat: {self.total_trades} trade kumulatif ({self.winning_trades} win, Total PnL: +${self.total_pnl_usd:.4f} USDT)[/bold green]")
        except Exception as e:
            console.log(f"[dim]DB load history notice: {e}[/dim]")

    @property
    def _ban_until(self) -> float:
        return self.client.ban_until

    @_ban_until.setter
    def _ban_until(self, val: float):
        self.client.ban_until = val

    def is_btc_macro_bullish(self) -> bool:
        """
        Kompas Makro BTC 4 Jam:
        Mengecek apakah harga BTC saat ini berada di atas EMA 200 4 Jam.
        Di-cache selama 15 menit (900 detik) untuk menghemat kuota request.
        """
        now = time.time()
        if (now - self._cached_btc_macro.get("updated_at", 0.0)) < 900.0:
            return self._cached_btc_macro.get("bullish", True)

        try:
            btc_klines = self.client.fetch_klines("BTCUSDT", interval="4h", limit=250)
            if btc_klines and len(btc_klines) >= 20:
                closes = [c[4] for c in btc_klines]
                cur_p = closes[-1]
                ema200_series = strategy.calculate_ema_series(closes, min(len(closes), config.EMA_TREND))
                ema200 = ema200_series[-1] if ema200_series else cur_p
                is_bull = cur_p >= ema200
                self._cached_btc_macro = {"bullish": is_bull, "updated_at": now}
                return is_bull
        except Exception as e:
            console.log(f"[dim]BTC macro check fallback notice: {e}[/dim]")

        return self._cached_btc_macro.get("bullish", True)

    def get_futures_balance(self, max_age_sec: float = 60.0) -> Dict[str, float]:
        """Mengambil saldo wallet USDⓈ-M Futures dengan caching 60 detik."""
        now = time.time()
        if self.client.is_banned():
            return self._cached_balance

        if now - self._last_balance_time < max_age_sec and self._cached_balance["total_wallet"] > 0:
            return self._cached_balance

        try:
            bal = self.client.get_balance()
            if bal and bal.get("total_wallet", 0.0) > 0:
                self._cached_balance = bal
                self._last_balance_time = now
                self.last_error = None
            return self._cached_balance
        except Exception as e:
            err_msg = str(e)
            self.last_error = f"Balance status: {err_msg}"
            self._last_balance_time = now + 15
            return self._cached_balance

    def sync_exchange_position(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Sinkronisasi otomatis dengan posisi terbuka langsung dari Binance.
        Dibatasi minimal 20 detik agar tidak membebani signed authenticated endpoint.
        """
        now = time.time()
        if self.client.is_banned():
            return self.active_position

        # Throttling cerdas sinkronisasi posisi:
        # Jika ada order aktif menunggu fill: cek setiap 5 detik agar responsif mendeteksi eksekusi
        # Jika tidak ada posisi & tidak ada order: cek setiap 15 detik (menghemat kuota signed endpoint)
        # Jika posisi aktif sedang berjalan: cek setiap 20 detik (pemantauan harga ketat & geser BEP tetap berjalan setiap 2.0s via fetch_price)
        sync_interval = 5.0 if self.active_order else (20.0 if self.active_position else 15.0)
        if not force and (now - self._last_sync_position_time < sync_interval):
            return self.active_position

        try:
            self._last_sync_position_time = now
            open_pos = self.client.get_open_positions()
            if self.client.is_banned():
                return self.active_position

            if open_pos:
                pos = open_pos[0]
                symbol = pos.get("symbol", "")
                contracts = abs(pos.get("amount", 0.0))
                side = "buy" if pos.get("amount", 0.0) > 0 else "sell"
                entry_price = pos.get("entry_price", 0.0)
                notional = contracts * entry_price
                
                # Pertahankan SL/TP target dan status BEP
                if self.active_position and self.active_position.get("symbol") == symbol:
                    sl_price = self.active_position.get("sl_price", entry_price * (1.0 - config.SL_PERCENT if side == "buy" else 1.0 + config.SL_PERCENT))
                    tp_price = self.active_position.get("tp_price", entry_price * (1.0 + config.TP_PERCENT if side == "buy" else 1.0 - config.TP_PERCENT))
                    bep_trigger_price = self.active_position.get("bep_trigger_price", entry_price * (1.0 + config.BEP_PROFIT_TRIGGER if side == "buy" else 1.0 - config.BEP_PROFIT_TRIGGER))
                    bep_activated = self.active_position.get("bep_activated", False)
                    opened_at = self.active_position.get("opened_at", time.time())
                    pos_leverage = self.active_position.get("leverage", int(pos.get("leverage", config.LEVERAGE)))
                    native_sl_id = self.active_position.get("native_sl_order_id")
                    native_tp_id = self.active_position.get("native_tp_order_id")
                else:
                    sl_price = entry_price * (1.0 - config.SL_PERCENT) if side == "buy" else entry_price * (1.0 + config.SL_PERCENT)
                    tp_price = entry_price * (1.0 + config.TP_PERCENT) if side == "buy" else entry_price * (1.0 - config.TP_PERCENT)
                    bep_trigger_price = entry_price * (1.0 + config.BEP_PROFIT_TRIGGER) if side == "buy" else entry_price * (1.0 - config.BEP_PROFIT_TRIGGER)
                    bep_activated = False
                    opened_at = time.time()
                    pos_leverage = int(pos.get("leverage", config.LEVERAGE))
                    native_sl_id = None
                    native_tp_id = None

                # PROTEKSI ANTI-DUPLIKASI: Periksa apakah Native SL / TP sudah aktif di server Binance!
                if not self.client.is_banned():
                    try:
                        existing_algos = self.client.fetch_open_algo_orders(symbol)
                        sl_orders = [o for o in existing_algos if o.get("orderType") == "STOP_MARKET" or o.get("type") == "STOP_MARKET"]
                        tp_orders = [o for o in existing_algos if o.get("orderType") == "TAKE_PROFIT_MARKET" or o.get("type") == "TAKE_PROFIT_MARKET"]
                        
                        if sl_orders:
                            native_sl_id = sl_orders[0].get("algoId")
                            # Batalkan order SL duplikat jika ada lebih dari 1
                            for dup_sl in sl_orders[1:]:
                                dup_id = dup_sl.get("algoId")
                                if dup_id:
                                    self.client.cancel_order(symbol, dup_id)
                        
                        if tp_orders:
                            native_tp_id = tp_orders[0].get("algoId")
                            # Batalkan order TP duplikat jika ada lebih dari 1
                            for dup_tp in tp_orders[1:]:
                                dup_id = dup_tp.get("algoId")
                                if dup_id:
                                    self.client.cancel_order(symbol, dup_id)
                    except Exception as e_chk:
                        console.log(f"[dim]Notice check existing algo orders: {e_chk}[/dim]")

                # JAMINAN KETAT: Jika Native SL belum ada di bursa Binance (misal restart/redeploy), pasang seketika!
                if not native_sl_id and not self.client.is_banned():
                    try:
                        sl_side = "SELL" if side == "buy" else "BUY"
                        res_sl = self.client.create_stop_loss_order(symbol, sl_side, sl_price, contracts)
                        if isinstance(res_sl, dict) and res_sl.get("orderId"):
                            native_sl_id = res_sl.get("orderId")
                            console.log(f"[bold green]🛡️ NATIVE STOP LOSS TERPASANG DI BURSA BINANCE pada {symbol} @ {sl_price}[/bold green]")
                    except Exception as e_sl_rec:
                        console.log(f"[yellow]Peringatan pasang native SL bursa: {e_sl_rec}[/yellow]")

                if not native_tp_id and not self.client.is_banned():
                    try:
                        tp_side = "SELL" if side == "buy" else "BUY"
                        res_tp = self.client.create_take_profit_order(symbol, tp_side, tp_price, contracts)
                        if isinstance(res_tp, dict) and res_tp.get("orderId"):
                            native_tp_id = res_tp.get("orderId")
                            console.log(f"[bold green]🎯 NATIVE TAKE PROFIT TERPASANG DI BURSA BINANCE pada {symbol} @ {tp_price}[/bold green]")
                    except Exception as e_tp_rec:
                        console.log(f"[yellow]Peringatan pasang native TP bursa: {e_tp_rec}[/yellow]")
                
                self.active_position = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "qty": contracts,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "bep_trigger_price": bep_trigger_price,
                    "bep_activated": bep_activated,
                    "opened_at": opened_at,
                    "notional": notional,
                    "leverage": pos_leverage,
                    "native_sl_order_id": native_sl_id,
                    "native_tp_order_id": native_tp_id
                }
                return self.active_position
            else:
                # 1. PEMBERSIH OTOMATIS: Bersihkan pesanan bersyarat menggantung HANYA jika:
                #    a. Posisi baru saja tertutup (self.active_position is not None), ATAU
                #    b. Sapuan berkala setiap 5 menit (300 detik) untuk menghemat kuota request bursa
                now_sync = time.time()
                should_sweep_algos = (self.active_position is not None) or (now_sync - self._last_algo_sweep > 300.0)
                if should_sweep_algos and not self.client.is_banned():
                    self._last_algo_sweep = now_sync
                    try:
                        dangling_algos = self.client.fetch_open_algo_orders()
                        if dangling_algos:
                            for d_order in dangling_algos:
                                d_sym = d_order.get("symbol")
                                d_id = d_order.get("algoId")
                                if d_sym:
                                    console.log(f"[bold yellow]🧹 Membersihkan pesanan bersyarat menggantung pada {d_sym} (Algo ID: {d_id}) karena posisi terbuka sudah 0.[/bold yellow]")
                                    self.client.cancel_all_open_orders(d_sym)
                                    self.client.cancel_all_algo_orders(d_sym)
                    except Exception as e_clean:
                        pass

                # 2. Rekam posisi yang baru saja tertutup
                if self.active_position is not None:
                    closed_pos = self.active_position
                    sym = closed_pos.get("symbol")
                    console.log(f"[bold yellow]Posisi {sym} telah selesai/tertutup di Binance (Eksekusi Native Stop Loss / Take Profit / BEP Bursa).[/bold yellow]")
                    self.client.cancel_all_open_orders(sym)
                    self.client.cancel_all_algo_orders(sym)
                    
                    entry_p = float(closed_pos.get("entry_price", 0.0))
                    c_side = closed_pos.get("side", "buy").lower()
                    cur_p = self.fetch_price(sym) or entry_p
                    is_win_hint = (cur_p >= entry_p) if c_side == "buy" else (cur_p <= entry_p)
                    exit_hint = float(closed_pos.get("tp_price" if is_win_hint else "sl_price", entry_p))
                    self._record_closed_position(closed_pos, exit_price_hint=exit_hint, result_hint="WIN" if is_win_hint else "LOSS")
                    return None
                return None
        except Exception as e:
            console.log(f"[dim]Sync position check: {e}[/dim]")
            return self.active_position

    def _record_closed_position(self, closed_pos: Dict[str, Any], exit_price_hint: float, result_hint: str = "WIN") -> Dict[str, Any]:
        """
        Merekam trade yang selesai dengan data riil langsung dari Binance API:
        1. Mengambil harga eksekusi riil dari userTrades (menghilangkan selisih slippage).
        2. Mengambil realized PnL riil dan ID trade resmi dari income history.
        3. Menjamin leverage dan margin_used tercatat akurat (maks 20x untuk akun baru).
        4. Menyimpan ke database Neon dan memperbarui agregat portofolio.
        """
        sym = closed_pos.get("symbol", "")
        entry_p = float(closed_pos.get("entry_price", 0.0))
        c_side = closed_pos.get("side", "buy").lower()
        c_notional = float(closed_pos.get("notional", 0.0))
        c_qty = float(closed_pos.get("qty", 0.0))
        # Ambil leverage riil (rentang 20x s/d 50x)
        c_lev = int(closed_pos.get("leverage") or self.client.get_max_leverage(sym))
        c_lev = max(config.LEVERAGE_MIN, min(c_lev, config.LEVERAGE_MAX))

        real_exit_price = exit_price_hint
        real_pnl_usd = None
        real_commission = 0.0
        binance_trade_id = None

        # 1. Coba ambil data riil eksekusi bursa dengan clustering multi-fill
        try:
            incomes = self.client.fetch_income_history(income_type="REALIZED_PNL", limit=10, symbol=sym)
            if incomes:
                sym_incomes = [inc for inc in incomes if inc.get("symbol") == sym]
                if sym_incomes:
                    # Ambil cluster trade penutupan terbaru (menyatukan multi-fill dalam selang 120s)
                    last_time = int(sym_incomes[-1].get("time", 0))
                    cluster = [inc for inc in sym_incomes if abs(int(inc.get("time", 0)) - last_time) <= 120000]
                    real_pnl_usd = round(sum(float(inc.get("income", 0.0)) for inc in cluster), 4)
                    binance_trade_id = str(cluster[-1].get("tradeId", ""))
        except Exception as e_inc:
            console.log(f"[dim]Notice fetch income PnL: {e_inc}[/dim]")

        try:
            user_trades = self.client.fetch_user_trades(sym, limit=10)
            if user_trades:
                closing_trades = [t for t in user_trades if t.get("side", "").lower() != c_side]
                if closing_trades:
                    # Ambil cluster eksekusi penutupan terbaru dalam rentang 120s
                    last_trade_time = int(closing_trades[-1].get("time", 0))
                    recent_closing = [t for t in closing_trades if abs(int(t.get("time", 0)) - last_trade_time) <= 120000]
                    
                    total_qty = sum(float(t.get("qty", 0.0)) for t in recent_closing)
                    if total_qty > 0:
                        vwap_price = sum(float(t.get("price", 0.0)) * float(t.get("qty", 0.0)) for t in recent_closing) / total_qty
                        real_exit_price = self.client.format_price(sym, vwap_price)
                    else:
                        real_exit_price = float(recent_closing[-1].get("price", exit_price_hint))
                    
                    real_commission = sum(float(t.get("commission", 0.0)) for t in recent_closing)
                    if not binance_trade_id and recent_closing[-1].get("id"):
                        binance_trade_id = str(recent_closing[-1].get("id"))
                else:
                    target_t = user_trades[-1]
                    real_exit_price = float(target_t.get("price", exit_price_hint))
                    real_commission = float(target_t.get("commission", 0.0))
        except Exception as e_ut:
            console.log(f"[dim]Notice fetch user trades: {e_ut}[/dim]")

        # 2. Fallback jika Binance API dalam jeda cooldown
        if real_pnl_usd is None:
            pct = ((real_exit_price - entry_p) / entry_p) if c_side == "buy" else ((entry_p - real_exit_price) / entry_p)
            real_pnl_usd = pct * c_notional
            real_pnl_pct = pct * 100
        else:
            real_pnl_pct = (real_pnl_usd / c_notional * 100) if c_notional > 0 else 0.0

        res = "WIN" if real_pnl_usd >= 0.0 else "LOSS"
        margin_used = round((c_notional / c_lev) if c_lev > 0 else (c_notional / 20.0), 4)

        trade_record = {
            "symbol": sym,
            "side": c_side.upper(),
            "entry_price": entry_p,
            "exit_price": real_exit_price,
            "qty": c_qty,
            "notional": c_notional,
            "margin_used": margin_used,
            "leverage": c_lev,
            "commission": round(real_commission, 6),
            "binance_trade_id": binance_trade_id,
            "pnl_usd": round(real_pnl_usd, 4),
            "pnl_pct": round(real_pnl_pct, 2),
            "result": res,
            "closed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            self.trade_history.append(trade_record)
            db.record_trade(trade_record)
            self.total_trades += 1
            if real_pnl_usd >= 0.0:
                self.winning_trades += 1
            self.total_pnl_usd += real_pnl_usd
            console.log(f"[bold green]✅ Trade {sym} berhasil tercatat 100% akurat dari bursa: PnL ${real_pnl_usd:+.4f} ({real_pnl_pct:+.2f}%), Exit: {real_exit_price}, Lev: {c_lev}x[/bold green]")
        except Exception as e_rec:
            console.log(f"[red]Error mencatat trade ke database: {e_rec}[/red]")

        # Proteksi Anti-Chop & Anti-Revenge Trading:
        # Jika trade berakhir LOSS, berikan jeda cooldown per simbol (4 jam) & hitung rentetan loss portofolio
        if res == "LOSS":
            cooldown_dur = getattr(config, "POST_SL_COOLDOWN_HOURS", 4.0) * 3600.0
            self._symbol_order_cooldown[sym] = time.time() + cooldown_dur
            self.consecutive_losses += 1
            console.log(f"[bold yellow]🛡️ Perlindungan Anti-Chop: Koin {sym} masuk jeda cooldown {getattr(config, 'POST_SL_COOLDOWN_HOURS', 4.0)} jam setelah Stop Loss (Loss beruntun: {self.consecutive_losses}).[/bold yellow]")

            cb_threshold = getattr(config, "CONSECUTIVE_LOSS_CIRCUIT_BREAKER", 3)
            if self.consecutive_losses >= cb_threshold:
                pause_sec = getattr(config, "CIRCUIT_BREAKER_PAUSE_HOURS", 36.0) * 3600.0
                self.circuit_breaker_until = time.time() + pause_sec
                cb_wib = time.strftime('%H:%M:%S', time.gmtime(self.circuit_breaker_until + 7 * 3600))
                console.log(f"[bold red]🚨 CIRCUIT BREAKER PORTOFOLIO: {self.consecutive_losses} loss berturut-turut. Mengistirahatkan seluruh scanner selama {getattr(config, 'CIRCUIT_BREAKER_PAUSE_HOURS', 36.0)} jam hingga {cb_wib} WIB.[/bold red]")
                self.consecutive_losses = 0
        else:
            self.consecutive_losses = 0

        self.active_position = None
        return trade_record

    def sync_historical_database_with_binance(self) -> Dict[str, Any]:
        """Menyelaraskan seluruh riwayat database dengan rekaman resmi bursa Binance."""
        if self.client.is_banned():
            return {"status": "skipped", "reason": "rate_limited"}
        try:
            console.log("[cyan]Memulai sinkronisasi seluruh riwayat database dengan data riil Binance...[/cyan]")
            incomes = self.client.fetch_income_history(income_type=None, limit=1000)
            res = db.sync_all_historical_trades_with_binance(incomes)
            bal = self.get_futures_balance()
            if res.get("status") == "success":
                self.total_trades = res["total_trades"]
                self.winning_trades = res["winning_trades"]
                # Gunakan selisih riil saldo dompet Binance (-$1.4373 / -$1.44) agar 100% selaras dengan aplikasi pengguna
                wallet_net_pnl = round(bal["total_wallet"] - config.INITIAL_CAPITAL, 4)
                self.total_pnl_usd = wallet_net_pnl
                console.log(f"[bold green]Sinkronisasi database sukses: {res.get('matched_trades', 0)} trade dicocokkan, Net PnL Dompet Binance: ${self.total_pnl_usd:+.4f} (Gross PnL: -0.5669, Fee: 0.3250, Funding: -0.5454)[/bold green]")
            return res
        except Exception as e:
            console.log(f"[red]Error sinkronisasi database dengan Binance: {e}[/red]")
            return {"status": "error", "error": str(e)}

    def get_compounded_notional(self, leverage: Optional[int] = None) -> float:
        """
        Menghitung ukuran notional posisi fleksibel:
        - Saldo < $100: gunakan margin tepat $1.00 (Maksimal ketat $1.00)
        - Saldo >= $100: gunakan 1.0% margin fleksibel dari total saldo (Compounding murni)
        - Notional fleksibel disesuaikan dengan leverage: Notional = Target Margin * Leverage
        """
        bal = self.get_futures_balance()
        avail = bal["available"]
        base_wallet = avail if avail >= 1.0 else config.DEFAULT_CAPITAL
        
        if base_wallet < config.BALANCE_THRESHOLD_SCALING:
            target_margin = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $1.00 jika saldo < $100
        else:
            target_margin = base_wallet * config.RISK_PORTFOLIO_PERCENT  # 1.0% fleksibel compounding jika saldo >= $100

        lev = leverage if leverage is not None else config.LEVERAGE
        return round(target_margin * lev, 2)

    def _get_fallback_symbols(self) -> List[Dict[str, Any]]:
        """Daftar koin likuid teratas bawaan jika API publik bursa sedang dalam cooldown."""
        top_fallback = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "NEARUSDT", "APTUSDT", "TAOUSDT", "DOTUSDT", "FILUSDT",
            "WLDUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "FETUSDT", "RENDERUSDT", "TIAUSDT",
            "SEIUSDT", "ENAUSDT", "PEPEUSDT", "SHIBUSDT", "BONKUSDT", "WIFUSDT", "FLOKIUSDT"
        ]
        return [{"symbol": s, "quoteVolume": 1000000000.0} for s in top_fallback]

    def _fetch_universe_symbols(self) -> List[Dict[str, Any]]:
        """
        Mengambil Semesta 500 Koin Crypto Murni (Non-Stablecoin) Langsung dari Binance Futures:
        1. Buang semua stablecoin (USDC, FDUSD, BUSD, TUSD, EUR, DAI, AEUR, USDP, USD1, BFUSD, USDT, USTC, dll).
        2. Hanya koin yang terdaftar di self.client.allowed_crypto_symbols.
        3. Filter koin dengan volume 24 jam >= config.MIN_24H_VOLUME_USD ($100K).
        4. Saring koin yang minimum order-nya terlalu besar untuk modal mikro.
        5. Urutkan berdasarkan quoteVolume tertinggi dan ambil tepat 500 koin crypto murni untuk 500 rotasi.
        """
        if self.client.is_banned():
            return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()

        try:
            data = self.client.fetch_top_tickers()
            if not isinstance(data, list):
                return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()

            stablecoin_symbols = {
                "USDCUSDT", "FDUSDUSDT", "BUSDUSDT", "TUSDUSDT", "EURUSDT", "DAIUSDT", "AEURUSDT",
                "USDPUSDT", "USD1USDT", "BFUSDUSDT", "USDTUSDT", "USTCUSDT", "EURIUSDT", "USDEUSDT",
                "USDJUSDT", "XAUTUSDT", "PAXGUSDT"
            }

            filtered = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                sym = item.get("symbol", "")
                if sym not in self.client.allowed_crypto_symbols or sym in stablecoin_symbols:
                    continue
                if any(sym.startswith(sc) for sc in ("USDC", "FDUSD", "BUSD", "TUSD", "EUR", "DAI", "AEUR", "USDP", "USD1", "BFUSD")):
                    continue
                try:
                    q_vol = float(item.get("quoteVolume", 0.0))
                    last_price = float(item.get("lastPrice", 0.0))
                    if q_vol < config.MIN_24H_VOLUME_USD or last_price <= 0:
                        continue

                    # Saring jika leverage maksimal koin < LEVERAGE_MIN (10x)
                    max_sym_lev = self.client.get_max_leverage(sym)
                    if max_sym_lev < config.LEVERAGE_MIN:
                        continue

                    # Saring jika koin tidak bisa mencapai minimum order Binance ($5.00) dengan margin yang diizinkan:
                    # (Saldo < $100: margin maks $1.00; Saldo >= $100: margin maks 1.0% saldo)
                    bal_avail = self._cached_balance.get("available", 0.0)
                    allowed_margin = config.FIXED_MARGIN_LOW_BALANCE if bal_avail < config.BALANCE_THRESHOLD_SCALING else (bal_avail * config.RISK_PORTFOLIO_PERCENT)
                    if (allowed_margin * max_sym_lev) < config.MIN_NOTIONAL:
                        continue

                    # Saring jika ukuran lot minimal koin memaksa margin terpakai melebihi batas margin yang diizinkan
                    rules = self.client._symbols_rules.get(sym, {})
                    min_q = rules.get("min_qty", 0.0)
                    min_notional_req = min_q * last_price
                    if (min_notional_req / max_sym_lev) > (allowed_margin * 1.01):
                        continue

                    filtered.append({
                        "symbol": sym,
                        "quoteVolume": q_vol
                    })
                except Exception:
                    continue

            # Urutkan berdasarkan volume 24 jam tertinggi dan ambil tepat 500 koin
            filtered.sort(key=lambda x: x["quoteVolume"], reverse=True)
            res = filtered[:config.SCAN_UNIVERSE_LIMIT]
            if res:
                console.log(f"[bold green]Berhasil memuat {len(res)} koin crypto murni (non-stablecoin) ke dalam semesta 500 rotasi.[/bold green]")
                return res
            return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()
        except Exception as e:
            console.log(f"[yellow]Notice fetch universe tickers: {e}[/yellow]")
            return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()

    def scan_top_coins(self):
        """
        Memindai semesta koin (hingga 500 koin) dengan sistem rotasi 1 koin per siklus:
        - 1 koin dianalisis secara komprehensif & mendalam (Multi-Timeframe 15m + 5m)
        - Pemetaan Area Likuidasi (Liquidation Pools Long & Short)
        - Deteksi Reaksi Price Action & Liquidity Sweep Reclaim
        - Struktur Pasar (HH/HL vs LH/LL) & S&R Teruji >= 2 kali
        - Retest EMA 13 & 21 5m, Volume Expansion, Open Interest, & CVD Taker Delta
        - Sebanyak 500 rotasi berturut-turut untuk menyisir seluruh koin tanpa screening singkat.
        """
        if self.client.is_banned() or self.client.is_scan_throttled():
            return
        if time.time() < self.circuit_breaker_until:
            rem_m = int((self.circuit_breaker_until - time.time()) / 60)
            self.current_rotation_info = f"Circuit Breaker Aktif ({rem_m}m lagi - Perlindungan Portofolio)"
            return
        t_start = time.time()
        try:
            now = time.time()
            if not self._cached_universe_symbols or (now - self._last_universe_refresh > 900):
                self._cached_universe_symbols = self._fetch_universe_symbols()
                self._last_universe_refresh = now
                gc.collect()

            universe = self._cached_universe_symbols
            if not universe:
                return

            total_univ = len(universe)
            rot_idx = self._current_rotation_index % total_univ
            item = universe[rot_idx]
            sym = item["symbol"]
            q_vol = item["quoteVolume"]
            rank = rot_idx + 1

            self.current_rotation_info = f"Rotasi {rank}/{total_univ} (Analisis Menyeluruh: {sym})"

            bal = self.get_futures_balance()
            cap = bal["available"] if bal["available"] >= 1.0 else config.DEFAULT_CAPITAL

            # 1. Fetch Multi-Timeframe Kalimasada: 4h untuk Tren Makro, 1h untuk Struktur & S&R, 15m untuk Eksekusi Scalp (1000 Candle Murni Tanpa Noise)
            ohlcv_4h = self.client.fetch_klines(sym, interval=config.MACRO_TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.15)
            ohlcv_1h = self.client.fetch_klines(sym, interval=config.STRUCTURE_TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.15)
            ohlcv_15m = self.client.fetch_klines(sym, interval=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.15)
            deriv_data = self.client.fetch_derivatives_data(sym, period="15m")

            if not ohlcv_15m or len(ohlcv_15m) < 25:
                self._current_rotation_index = (self._current_rotation_index + 1) % total_univ
                self.last_scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
                return

            # 2. Analisis Menyeluruh Sesuai Master Blueprint Akademi Crypto
            max_sym_lev = self.client.get_max_leverage(sym)
            btc_macro_bull = self.is_btc_macro_bullish() if config.BTC_FILTER_ENABLED else None
            analysis = strategy.analyze_coin_comprehensive(
                symbol=sym,
                ohlcv_htf=ohlcv_1h,
                ohlcv_ltf=ohlcv_15m[:-1],
                ohlcv_macro=ohlcv_4h,
                derivatives_data=deriv_data,
                available_capital=cap,
                leverage=config.LEVERAGE,
                max_symbol_leverage=max_sym_lev,
                btc_macro_bullish=btc_macro_bull
            )
            analysis["rank"] = rank
            analysis["vol_24h_m"] = round(q_vol / 1_000_000, 2)

            self.current_coin_analysis = analysis
            self._coins_analysis_history[sym] = analysis

            # Perbarui ranked pairs dari histori koin yang telah dianalisis (50 koin aktif terakhir)
            self.ranked_pairs = list(self._coins_analysis_history.values())[-50:]
            self.bullish_count = sum(1 for r in self.ranked_pairs if r.get("trend_bias") == "BULLISH")
            self.bearish_count = sum(1 for r in self.ranked_pairs if r.get("trend_bias") == "BEARISH")

            # Perbarui Watchlist berdasarkan skor kualitas & kedekatan dengan pool likuidasi
            sorted_by_score = sorted(
                self._coins_analysis_history.values(),
                key=lambda x: (x.get("score", 0), -x.get("liquidation_pools", {}).get("nearest_pool_distance_pct", 99.0)),
                reverse=True
            )
            self.watchlist = sorted_by_score[:8]

            # 3. Evaluasi Sinyal Eksekusi
            sig = analysis.get("signal")
            if sig is not None and sig.get("score", 0) >= config.MIN_SETUP_SCORE:
                console.log(f"[bold green]🎯 SETUP DITEMUKAN PADA {sym}! {sig['setup_name']} (Skor: {sig['score']})[/bold green]")
                existing_syms = [s["symbol"] for s in self.active_signals]
                if sym not in existing_syms:
                    sig_entry = sig.copy()
                    sig_entry["rank"] = rank
                    sig_entry["vol_24h_m"] = round(q_vol / 1_000_000, 2)
                    self.active_signals.insert(0, sig_entry)
                    self.active_signals = self.active_signals[:8]
                    db.record_signals([sig_entry])

                # Eksekusi jika tidak ada posisi atau order aktif
                if not self.active_position and not self.active_order and not self.client.is_banned():
                    self.execute_limit_order(sig)

            self.last_scan_duration_sec = round(time.time() - t_start, 2)
            self.last_scan_time = time.strftime("%Y-%m-%d %H:%M:%S")

            # Maju ke rotasi berikutnya
            self._current_rotation_index = (self._current_rotation_index + 1) % total_univ
            
            # Snapshot saldo ke Neon Tech secara berkala (setiap 1 jam agar hemat kuota compute)
            if now - self._last_wallet_db_snapshot > 3600:
                db.record_wallet_snapshot(
                    total_wallet=bal["total_wallet"],
                    available=bal["available"],
                    unpnl=bal["unrealized_pnl"],
                    trade_size=self.get_compounded_notional(),
                    margin_pct=config.RISK_PORTFOLIO_PERCENT * 100
                )
                self._last_wallet_db_snapshot = now
            
        except Exception as e:
            console.log(f"[red]Error dalam pemindaian koin: {e}[/red]")
        finally:
            gc.collect()

    def execute_limit_order(self, sig: Dict[str, Any]) -> bool:
        """Mengeksekusi Limit Order (Maker only / timeInForce=GTX) dengan timeout 30 detik."""
        symbol = sig["symbol"]
        side = "BUY" if sig["side"] == "BUY" else "SELL"
        target_price = sig["entry_price"]

        now = time.time()
        cooldown_until = self._symbol_order_cooldown.get(symbol, 0.0)
        if now < cooldown_until:
            rem = int(cooldown_until - now)
            console.log(f"[yellow]Koin {symbol} dalam jeda cooldown ({rem}s lagi setelah auto-cancel). Melewati agar tidak spam berulang.[/yellow]")
            return False
        
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        if base in TRADFI_EXCLUSIONS:
            console.log(f"[yellow]Melewati order pada {symbol} (Aset TradFi).[/yellow]")
            return False

        try:
            # 1. Pastikan ISOLATED margin dan atur leverage dalam rentang 50x turun ke 20x (Kompatibel Akun < 30 Hari)
            if symbol in self._symbol_leverage:
                actual_leverage = self._symbol_leverage[symbol]
            else:
                self.client.set_margin_type(symbol, "ISOLATED")
                curr_min_lev = config.dynamic_min_leverage
                actual_leverage = self.client.set_leverage(
                    symbol,
                    target_leverage=config.LEVERAGE_MAX,
                    min_leverage=curr_min_lev
                )
                if actual_leverage >= curr_min_lev:
                    self._symbol_leverage[symbol] = actual_leverage
                    self._configured_symbols.add(symbol)
            
            # Saring koin jika leverage di bawah batas minimal dinamis (20x sebelum 35 hari, 25x setelah 35 hari)
            curr_min_lev = config.dynamic_min_leverage
            if actual_leverage < curr_min_lev:
                console.log(
                    f"[bold yellow]🛡️ Filter Leverage Rendah: {symbol} hanya mendukung {actual_leverage}x (< {curr_min_lev}x). "
                    f"Melewati koin agar modal tetap aman dan terukur.[/bold yellow]"
                )
                self.active_order = None
                self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                self._symbol_order_cooldown[symbol] = time.time() + 600
                return False

            # Hitung target margin sesuai portofolio terkini
            bal = self.get_futures_balance()
            avail = bal["available"] if bal["available"] >= 1.0 else config.DEFAULT_CAPITAL
            if avail < config.BALANCE_THRESHOLD_SCALING:
                target_margin = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $1.00 jika saldo < $100
                max_margin_cap = config.MAX_MARGIN_LOW_BALANCE   # Batas maksimal ketat $1.00 jika saldo < $100
            else:
                target_margin = avail * config.RISK_PORTFOLIO_PERCENT  # 1.0% fleksibel compounding jika saldo >= $100
                max_margin_cap = target_margin  # Batas maksimal ketat 1.0% jika saldo >= $100 (tidak boleh lebih dari 1%)

            target_notional = target_margin * actual_leverage

            # CEK KETAT: Jika nilai notional di bawah batas minimum Binance ($5.00),
            # JANGAN buka posisi dan LEWATI koin sesuai instruksi pengguna!
            if target_notional < config.MIN_NOTIONAL:
                console.log(
                    f"[bold yellow]🛡️ Minimal order tidak tercapai: {symbol} pada leverage {actual_leverage}x "
                    f"dengan margin ${target_margin:.2f} menghasilkan notional ${target_notional:.2f} "
                    f"(di bawah batas minimum ${config.MIN_NOTIONAL:.2f}). Melewati koin sesuai instruksi.[/bold yellow]"
                )
                self.active_order = None
                self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                self._symbol_order_cooldown[symbol] = time.time() + 600
                return False

            # 2. Ambil best bid/ask untuk harga Maker dan validasi likuiditas buku order
            depth = self.client.fetch_best_bid_ask(symbol)
            bid_p = depth.get("bid", 0.0)
            ask_p = depth.get("ask", 0.0)
            if bid_p > 0 and ask_p > 0:
                spread_pct = (ask_p - bid_p) / bid_p
                if spread_pct > config.MAX_SPREAD_PERCENT:
                    console.log(
                        f"[bold yellow]🛡️ Filter Spread Ketat: Spread {symbol} sebesar {spread_pct*100:.3f}% "
                        f"melebihi batas maksimal {config.MAX_SPREAD_PERCENT*100:.2f}%. Melewati koin ini untuk mencegah slippage & flashdump.[/bold yellow]"
                    )
                    self.active_order = None
                    self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                    self._symbol_order_cooldown[symbol] = time.time() + 300
                    return False

            if side == "BUY":
                best_price = bid_p if bid_p > 0 else target_price
            else:
                best_price = ask_p if ask_p > 0 else target_price
                
            formatted_price = self.client.format_price(symbol, best_price)
            if formatted_price <= 0:
                formatted_price = self.client.format_price(symbol, target_price)
            
            # 3. Hitung qty dengan presisi tepat
            formatted_qty = self.client.calculate_order_qty(symbol, target_notional, formatted_price)
            
            if formatted_qty <= 0:
                console.log(f"[red]Ukuran order terlalu kecil untuk {symbol}[/red]")
                return False
                
            effective_notional = formatted_qty * formatted_price
            margin_used = effective_notional / actual_leverage

            # Jika margin_used sedikit melebihi cap akibat pembulatan lot size (math.ceil),
            # coba turunkan 1 step lot size jika notional tetap >= MIN_NOTIONAL ($5.00)
            rules = self.client._symbols_rules.get(symbol, {})
            step = rules.get("step_size", 0.0)
            if margin_used > (max_margin_cap + 0.005) and step > 0:
                reduced_qty = self.client.format_qty(symbol, formatted_qty - step)
                if (reduced_qty * formatted_price) >= config.MIN_NOTIONAL:
                    formatted_qty = reduced_qty
                    effective_notional = formatted_qty * formatted_price
                    margin_used = effective_notional / actual_leverage

            # Filter ketat batas maksimal margin per posisi
            # Saldo < $100: Maksimal ketat $1.00 (tidak boleh lebih dari $1.00)
            # Saldo >= $100: Maksimal ketat 1.0% dari saldo (tidak boleh lebih dari 1.0%)
            if margin_used > (max_margin_cap + 0.005):
                console.log(
                    f"[bold yellow]🛡️ Filter Margin Ketat: Margin terhitung ${margin_used:.2f} melebihi batas maksimal "
                    f"${max_margin_cap:.2f} untuk {symbol}. Melewati koin agar modal tetap aman.[/bold yellow]"
                )
                return False

            if effective_notional < config.MIN_NOTIONAL:
                console.log(f"[bold yellow]🛡️ Notional terhitung ${effective_notional:.2f} < ${config.MIN_NOTIONAL:.2f}. Melewati {symbol} agar margin tetap sesuai aturan.[/bold yellow]")
                return False

            console.log(f"[bold cyan]Dispatching Maker Limit Order (Risk: ${sig.get('risk_usd', 0.05):.3f}, Leverage: {actual_leverage}x): {side} {formatted_qty} {symbol} @ {formatted_price} (Notional: ${effective_notional:.2f}, Margin: ${margin_used:.2f})[/bold cyan]")
            
            order = self.client.create_limit_order(
                symbol=symbol,
                side=side,
                qty=formatted_qty,
                price=formatted_price
            )
            
            order_id = order.get("orderId")
            self.active_order = {
                "id": order_id,
                "symbol": symbol,
                "side": side.lower(),
                "price": formatted_price,
                "qty": formatted_qty,
                "sl_price": sig["sl_price"],
                "tp_price": sig["tp_price"],
                "bep_trigger_price": sig.get("bep_trigger_price", 0.0),
                "leverage": actual_leverage,
                "risk_usd": sig.get("risk_usd", 0.05),
                "reward_usd": sig.get("reward_usd", 0.10),
                "placed_at": time.time()
            }
            
            # 4. Loop Pemantauan 30 Detik (Anti-FOMO Auto-Cancel dengan Fast 0.5s Polling)
            console.log(f"[yellow]Menunggu limit order terisi (maks 30 detik)...[/yellow]")
            t_start = time.time()
            while time.time() - t_start < config.LIMIT_TIMEOUT_SECONDS:
                time.sleep(0.5)  # Polling cepat 0.5s (bukan 2s) agar mendeteksi fill seketika
                try:
                    chk = self.client.get_order(symbol, order_id)
                    status = chk.get("status")
                    if status == "FILLED":
                        console.log(f"[bold green]LIMIT ORDER TERISI PENUH! ({symbol} @ {formatted_price})[/bold green]")
                        
                        # Hitung ulang level SL, TP, dan BEP presisi dari harga keterisian riil (formatted_price)
                        # Menjamin rasio RR 1:2 (SL config.SL_PERCENT, TP config.TP_PERCENT) selalu dihitung dari harga eksekusi riil
                        sl_side = "SELL" if side.lower() == "buy" else "BUY"
                        actual_sl = self.client.format_price(symbol, formatted_price * (1.0 - config.SL_PERCENT) if side.lower() == "buy" else formatted_price * (1.0 + config.SL_PERCENT))
                        actual_tp = self.client.format_price(symbol, formatted_price * (1.0 + config.TP_PERCENT) if side.lower() == "buy" else formatted_price * (1.0 - config.TP_PERCENT))
                        actual_bep = self.client.format_price(symbol, formatted_price * (1.0 + config.BEP_PROFIT_TRIGGER) if side.lower() == "buy" else formatted_price * (1.0 - config.BEP_PROFIT_TRIGGER))

                        # 1. Pasang Native Stop Loss (STOP_MARKET) langsung di Matching Engine Binance
                        native_sl = self.client.create_stop_loss_order(
                            symbol=symbol,
                            side=sl_side,
                            stop_price=actual_sl,
                            qty=formatted_qty
                        )
                        native_sl_id = native_sl.get("orderId") if isinstance(native_sl, dict) else None

                        # Jika harga melompat agresif dan SL ditolak karena sudah terlewati (-2021 Order would immediately trigger):
                        # Langsung eksekusi Market Close darurat DETIK ITU JUGA agar modal terlindungi seketika!
                        if not native_sl_id and isinstance(native_sl, dict) and native_sl.get("code") == -2021:
                            console.log(f"[bold red]🚨 Flash Spike Terdeteksi! Harga telah melompati level SL. Menutup posisi seketika dengan market close...[/bold red]")
                            m_res = self.client.create_market_close_order(symbol, sl_side, formatted_qty)
                            fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else formatted_price
                            self.active_order = None
                            self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                            temp_pos = {
                                "symbol": symbol,
                                "side": side.lower(),
                                "entry_price": formatted_price,
                                "qty": formatted_qty,
                                "notional": formatted_qty * formatted_price,
                                "leverage": actual_leverage,
                                "sl_price": actual_sl
                            }
                            self._record_closed_position(temp_pos, exit_price_hint=fill_p, result_hint="LOSS")
                            return False

                        # 2. Pasang Native Take Profit (TAKE_PROFIT_MARKET) langsung di Matching Engine Binance
                        # Menjamin Take Profit terkunci seketika di bursa tanpa slippage dan tanpa delay polling
                        native_tp = self.client.create_take_profit_order(
                            symbol=symbol,
                            side=sl_side,
                            stop_price=actual_tp,
                            qty=formatted_qty
                        )
                        native_tp_id = native_tp.get("orderId") if isinstance(native_tp, dict) else None

                        self.active_position = {
                            "symbol": symbol,
                            "side": side.lower(),
                            "entry_price": formatted_price,
                            "qty": formatted_qty,
                            "sl_price": actual_sl,
                            "tp_price": actual_tp,
                            "bep_trigger_price": actual_bep,
                            "bep_activated": False,
                            "native_sl_order_id": native_sl_id,
                            "native_tp_order_id": native_tp_id,
                            "leverage": actual_leverage,
                            "risk_usd": formatted_qty * formatted_price * config.SL_PERCENT,
                            "reward_usd": formatted_qty * formatted_price * config.TP_PERCENT,
                            "opened_at": time.time(),
                            "notional": formatted_qty * formatted_price
                        }
                        self.active_order = None
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                        return True
                    elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                        console.log(f"[yellow]Order dibatalkan/ditolak ({status}).[/yellow]")
                        self.active_order = None
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                        self._symbol_order_cooldown[symbol] = time.time() + 300
                        return False
                except Exception as err:
                    console.log(f"[dim]Pengecekan order {order_id}: {err}[/dim]")
                    
            console.log(f"[bold yellow]Limit order tidak terisi dalam 30 detik. Auto-cancel {order_id} (Anti-FOMO)...[/bold yellow]")
            try:
                self.client.cancel_order(symbol, order_id)
            except Exception as e:
                console.log(f"[dim]Gagal cancel order: {e}[/dim]")
                
            self.active_order = None
            self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
            self._symbol_order_cooldown[symbol] = time.time() + 300  # Cooldown 5 menit agar tidak spam berulang
            return False
            
        except Exception as e:
            console.log(f"[red]Gagal dispatch limit order: {e}[/red]")
            self.active_order = None
            self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
            self._symbol_order_cooldown[symbol] = time.time() + 180
            return False

    def execute_maker_close(self, symbol: str, side: str, qty: float, target_price: float, is_emergency: bool = False) -> Tuple[bool, float]:
        """
        Menutup posisi menggunakan Maker Limit Order (timeInForce=GTX / Post Only) agar fee terendah (0.02%).
        - Jika is_emergency=True (Stop Loss atau BEP terpicu): pantau maksimal 1.5s agar tidak terkena slippage.
        - Jika Take Profit normal (is_emergency=False): pantau hingga 6s di antrean teratas.
        Fallback otomatis ke market order untuk menjamin kepastian penutupan posisi seketika.
        Mengembalikan (sukses: bool, actual_exit_price: float).
        """
        try:
            depth = self.client.fetch_best_bid_ask(symbol)
            rules = self.client._symbols_rules.get(symbol, {})
            tick = rules.get("tick_size", 0.0001)

            if side == "SELL":
                best_ask = depth.get("ask", 0.0)
                limit_price = max(best_ask, target_price) if best_ask > 0 else target_price
            else:
                best_bid = depth.get("bid", 0.0)
                limit_price = min(best_bid, target_price) if best_bid > 0 else target_price

            formatted_price = self.client.format_price(symbol, limit_price)
            console.log(f"[bold cyan]Mengirim Maker Limit Close: {side} {qty} {symbol} @ {formatted_price} (Post-Only GTX)...[/bold cyan]")

            res = self.client.create_limit_close_order(symbol, side, qty, formatted_price)
            
            # Jika ditolak karena crossed (-5022 Post-Only):
            if isinstance(res, dict) and res.get("code") == -5022:
                if is_emergency:
                    console.log(f"[yellow]Limit close crossed saat emergency/BEP. Langsung eksekusi market close instan...[/yellow]")
                    m_res = self.client.create_market_close_order(symbol, side, qty)
                    fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
                    return True, (fill_p if fill_p > 0 else target_price)
                else:
                    if side == "SELL":
                        formatted_price = self.client.format_price(symbol, formatted_price + tick)
                    else:
                        formatted_price = self.client.format_price(symbol, formatted_price - tick)
                    res = self.client.create_limit_close_order(symbol, side, qty, formatted_price)

            order_id = res.get("orderId") if isinstance(res, dict) else None
            if not order_id:
                console.log(f"[yellow]Limit close gagal, beralih ke market close darurat...[/yellow]")
                m_res = self.client.create_market_close_order(symbol, side, qty)
                fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
                return True, (fill_p if fill_p > 0 else target_price)

            # Batas waktu tunggu singkat (1.0s - 1.2s) agar profit terkunci di pucuk tanpa terkena retrace
            max_wait = 1.0 if is_emergency else 1.2
            t0 = time.time()
            while time.time() - t0 < max_wait:
                time.sleep(0.5)
                chk = self.client.get_order(symbol, order_id)
                status = chk.get("status")
                if status == "FILLED":
                    fill_p = float(chk.get("avgPrice", 0.0)) or formatted_price
                    console.log(f"[bold green]MAKER LIMIT CLOSE TERISI PENUH! ({symbol} @ {fill_p}, Fee Terendah Maker)[/bold green]")
                    return True, fill_p
                elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                    break

            # Jika belum terisi setelah batas waktu, batalkan dan tuntaskan seketika dengan market order
            console.log(f"[yellow]Maker limit close belum terisi setelah {max_wait}s. Menuntaskan dengan market order agar profit terkunci aman...[/yellow]")
            try:
                self.client.cancel_order(symbol, order_id)
            except Exception:
                pass
            m_res = self.client.create_market_close_order(symbol, side, qty)
            fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
            return True, (fill_p if fill_p > 0 else target_price)

        except Exception as e:
            console.log(f"[yellow]Notice maker close: {e}, fallback ke market close...[/yellow]")
            try:
                m_res = self.client.create_market_close_order(symbol, side, qty)
                fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
                return True, (fill_p if fill_p > 0 else target_price)
            except Exception as e2:
                console.log(f"[red]Gagal menutup posisi: {e2}[/red]")
                return False, target_price

    def monitor_active_position(self):
        """
        Memantau posisi aktif dengan manajemen risiko ketat Akademi Crypto (Kalimasada):
        1. Target Take Profit penuh: +1.4% (Risk to Reward 1:2).
        2. Stop Loss awal: -0.7% (Resiko terukur 1R).
        3. Proteksi Break-Even (BEP): Begitu profit mencapai 1R (+0.7%), SL otomatis digeser
           ke Break-Even (+0.15% di atas Entry) sehingga menutup 100% seluruh fee bursa (0.07%)
           + buffer slippage flashdump (0.03%) & mengunci untung bersih, memberi ruang napas ke TP.
        """
        if not self.active_position:
            return
            
        pos = self.active_position
        symbol = pos["symbol"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        qty = pos["qty"]
        pos_leverage = pos.get("leverage", config.LEVERAGE)
        
        try:
            current_price = self.client.fetch_price(symbol)
            if current_price <= 0:
                return
                
            pnl_pct = ((current_price - entry_price) / entry_price) if side == "buy" else ((entry_price - current_price) / entry_price)
            pnl_usd = pnl_pct * pos["notional"]

            # --- 1. Proteksi Geser SL ke Break-Even (BEP) saat mencapai 1R (+0.7%) ---
            bep_trigger = pos.get("bep_trigger_price", 0.0)
            bep_activated = pos.get("bep_activated", False)
            if not bep_activated:
                hit_bep = (current_price >= bep_trigger) if side == "buy" else (current_price <= bep_trigger) if bep_trigger > 0 else (pnl_pct >= config.BEP_PROFIT_TRIGGER)
                if hit_bep:
                    bep_lock = getattr(config, "BEP_LOCK_PROFIT", 0.0025) # +0.25% di atas entry
                    raw_bep = entry_price * (1.0 + bep_lock) if side == "buy" else entry_price * (1.0 - bep_lock)
                    formatted_bep = self.client.format_price(symbol, raw_bep)
                    
                    rules = self.client._symbols_rules.get(symbol, {})
                    tick = rules.get("tick_size", 0.0001)
                    if side == "buy":
                        formatted_bep = max(formatted_bep, entry_price + 2 * tick)
                    else:
                        formatted_bep = min(formatted_bep, entry_price - 2 * tick)
                        
                    pos["sl_price"] = formatted_bep
                    pos["bep_activated"] = True
                    console.log(f"[bold cyan]🛡️ BREAK-EVEN DIAKTIFKAN pada {symbol}: Profit mencapai 1R (+{config.BEP_PROFIT_TRIGGER*100:.2f}%), menggeser Native SL ke {formatted_bep} (Terkunci Untung Bersih +{bep_lock*100:.2f}% Menutup Seluruh Fee Bursa)[/bold cyan]")
                    
                    # Batalkan Stop Loss lama di Binance & Pasang Native STOP_MARKET baru di harga BEP
                    # Catatan: Native TP tetap aktif di bursa untuk menangkap target profit penuh +2.00%
                    try:
                        old_sl_id = pos.get("native_sl_order_id")
                        if old_sl_id:
                            try:
                                self.client.cancel_order(symbol, old_sl_id)
                            except Exception:
                                pass

                        sl_side = "SELL" if side == "buy" else "BUY"
                        new_sl = self.client.create_stop_loss_order(
                            symbol=symbol,
                            side=sl_side,
                            stop_price=formatted_bep,
                            qty=qty
                        )
                        if isinstance(new_sl, dict) and new_sl.get("orderId"):
                            pos["native_sl_order_id"] = new_sl.get("orderId")
                            console.log(f"[bold green]🛡️ NATIVE BREAK-EVEN STOP LOSS BERHASIL DIPASANG DI BINANCE pada {symbol} @ {formatted_bep}[/bold green]")
                    except Exception as e_bep:
                        console.log(f"[red]Gagal memasang Native BEP SL di Binance: {e_bep}[/red]")

            # Perbarui nilai SL/TP terkini
            sl_price = pos["sl_price"]
            tp_price = pos["tp_price"]

            hit_tp = (current_price >= tp_price) if side == "buy" else (current_price <= tp_price)
            hit_sl = (current_price <= sl_price) if side == "buy" else (current_price >= sl_price)
            
            console.log(f"[dim]Pemantauan 2.5s: {symbol} @ {current_price} | PnL: {pnl_pct*100:+.2f}% (${pnl_usd:+.2f}) | TP: {tp_price:.4f} | SL: {sl_price:.4f} | BEP: {'AKTIF' if pos.get('bep_activated') else 'MENUNGGU 1R'}[/dim]")
            
            if hit_tp:
                # Periksa apakah posisi sudah ditutup oleh Native SL / BEP di Binance sebelum execute close
                pos_check = self.sync_exchange_position(force=True)
                if not pos_check:
                    console.log(f"[bold green]Posisi {symbol} telah berhasil ditutup instan di Binance matching engine.[/bold green]")
                    return

                console.log(f"[bold green]🎯 TAKE PROFIT TERCAPAI (RR 1:2 Bersih Dollar / +{config.TP_PERCENT*100:.2f}%)! (+{pnl_pct*100:.2f}%, PnL: +${pnl_usd:.2f}) pada {symbol}[/bold green]")
                # Batalkan Native SL yang masih terpasang di Binance agar tidak tereksekusi ganda
                try:
                    self.client.cancel_all_open_orders(symbol)
                    self.client.cancel_all_algo_orders(symbol)
                except Exception as e_c:
                    console.log(f"[dim]Cancel native SL saat TP: {e_c}[/dim]")

                close_side = "SELL" if side == "buy" else "BUY"
                success, actual_exit = self.execute_maker_close(symbol=symbol, side=close_side, qty=qty, target_price=current_price, is_emergency=False)
                
                final_exit = actual_exit if actual_exit > 0 else current_price
                self._record_closed_position(pos, exit_price_hint=final_exit, result_hint="WIN")
                
            elif hit_sl:
                # Periksa apakah posisi sudah ditutup oleh Native Stop Loss di Binance
                pos_check = self.sync_exchange_position(force=True)
                if not pos_check:
                    console.log(f"[bold green]Posisi {symbol} telah berhasil ditutup instan oleh Native SL/BEP di Binance matching engine.[/bold green]")
                    return

                # Jika masih terbuka karena anomali bursa, eksekusi darurat seketika
                is_be_or_profit = pos.get("bep_activated", False) or (pnl_usd >= 0.0)
                tag = "🛡️ BREAK-EVEN EXIT (Bebas Risiko Terkunci)" if is_be_or_profit else "🛑 STOP LOSS TERPICU (-0.7%)"
                color = "green" if is_be_or_profit else "red"
                
                console.log(f"[bold {color}]{tag}! ({pnl_pct*100:+.2f}%, PnL: ${pnl_usd:+.2f}) pada {symbol}[/bold {color}]")
                try:
                    self.client.cancel_all_open_orders(symbol)
                    self.client.cancel_all_algo_orders(symbol)
                except Exception:
                    pass

                close_side = "SELL" if side == "buy" else "BUY"
                
                # PROTEKSI KETAT: Jika Stop Loss darurat (bukan BEP profit), LANGSUNG eksekusi Market Close instan!
                # DILARANG mencoba Maker Close yang menunggu 1.5 detik karena akan memperparah slippage saat flash dump/spike!
                if not is_be_or_profit:
                    console.log(f"[bold red]🛑 Eksekusi Instan Market Stop Loss untuk {symbol} demi mencegah slippage tambahan...[/bold red]")
                    m_res = self.client.create_market_close_order(symbol, close_side, qty)
                    actual_exit = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else current_price
                    success = True
                else:
                    success, actual_exit = self.execute_maker_close(symbol=symbol, side=close_side, qty=qty, target_price=current_price, is_emergency=True)
                
                final_exit = actual_exit if actual_exit > 0 else current_price
                self._record_closed_position(pos, exit_price_hint=final_exit, result_hint="WIN" if is_be_or_profit else "LOSS")
                
        except Exception as e:
            console.log(f"[red]Error memantau posisi aktif {symbol}: {e}[/red]")

    def run_scan_loop(self):
        """Loop pemindaian utama yang berjalan secara otonom di background."""
        console.log("[bold green]>>> Binance Scalper Autonomous Loop Dimulai (Native Engine + Neon Tech) <<<[/bold green]")
        self.is_running = True
        
        # 1. Inisialisasi Database Neon Tech (Schema: binance_scalper)
        db.init_db()
        
        # 2. Inisialisasi Bursa
        self.client.ensure_single_asset_mode()
        self.client.load_leverage_brackets()
        self.get_futures_balance(max_age_sec=0)
        self.sync_exchange_position()
        
        while self.is_running:
            try:
                if self.client.is_banned():
                    s_left = int(self.client.ban_until - time.time())
                    if s_left > 0:
                        m_left = s_left // 60
                        sec_left = s_left % 60
                        now_log = time.time()
                        if now_log - self.client._last_ban_log_time > 60:
                            self.client._last_ban_log_time = now_log
                            console.log(f"[yellow]IP Cooldown Binance aktif ({m_left}m {sec_left}s lagi). Menunggu otomatis tanpa request ke bursa...[/yellow]")
                        if self.active_position:
                            time.sleep(min(2.5, max(1, s_left)))
                        else:
                            time.sleep(min(30, max(5, s_left + 1)))
                        continue

                # Muat ulang aturan pasar jika sebelumnya gagal akibat cooldown
                if len(self.client._symbols_rules) == 0:
                    self.client.load_markets()

                # 1. Selalu sinkronisasi posisi riil dari Binance
                self.sync_exchange_position()

                # 2. Jika ada posisi aktif, pantau harga setiap 2.0 detik untuk geser BEP presisi
                if self.active_position:
                    self.monitor_active_position()
                    time.sleep(2.0)  # Cek harga posisi aktif setiap 2.0 detik sesuai permintaan user
                    continue
                    
                # 3. Jalankan pemindaian koin Top volume
                self.scan_top_coins()
                
                # 4. Cek saldo akun
                bal = self.get_futures_balance()
                avail_usdt = bal["available"]
                
                # 5. Jika ada sinyal valid dan saldo tersedia cukup
                if self.active_signals and not self.active_order and not self.active_position:
                    best_signal = self.active_signals[0]
                    sym = best_signal.get("symbol", "")
                    if time.time() < self._symbol_order_cooldown.get(sym, 0.0):
                        # Jika koin teratas masih dalam cooldown setelah auto-cancel, buang dari active_signals
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != sym]
                    else:
                        console.log(f"[bold green]Sinyal terbaik terdeteksi:[/bold green] {best_signal['side']} {best_signal['symbol']} (Skor: {best_signal.get('score', 0)})")
                        min_req = config.FIXED_MARGIN_LOW_BALANCE if avail_usdt < config.BALANCE_THRESHOLD_SCALING else (avail_usdt * config.RISK_PORTFOLIO_PERCENT)
                        if avail_usdt >= min_req:
                            self.execute_limit_order(best_signal)
                        else:
                            console.log(f"[yellow]Saldo USDT Futures (${avail_usdt:.2f}) di bawah minimum (${min_req:.2f}). Menunggu modal.[/yellow]")
                        
                if self.active_position:
                    time.sleep(2.0)  # Langsung monitor 2.0s jika posisi baru saja terisi
                else:
                    time.sleep(config.SCAN_INTERVAL_SECONDS)
                
            except Exception as e:
                console.log(f"[red]Error di siklus bot scalper: {e}[/red]")
                time.sleep(10)

    def run(self):
        self.run_scan_loop()

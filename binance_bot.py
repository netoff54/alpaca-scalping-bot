import os
import time
import math
import threading
import gc
from typing import Dict, Any, List, Optional
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
        
        # Cache Top 50 koin (diperbarui setiap 30 menit)
        self._cached_top_symbols: List[Dict[str, Any]] = []
        self._last_top_symbols_refresh: float = 0.0
        self._last_wallet_db_snapshot: float = 0.0
        
        # Balance cache & Rate limit cooldown
        self._cached_balance: Dict[str, float] = {"total_wallet": 0.0, "available": 0.0, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self._last_sync_position_time: float = 0.0
        self._configured_symbols: Set[str] = set()
        self.last_error: Optional[str] = None

    @property
    def _ban_until(self) -> float:
        return self.client.ban_until

    @_ban_until.setter
    def _ban_until(self, val: float):
        self.client.ban_until = val

    def get_futures_balance(self, max_age_sec: float = 60.0) -> Dict[str, float]:
        """Mengambil saldo wallet USDⓈ-M Futures dengan caching 60 detik."""
        now = time.time()
        if self.client.is_banned():
            return self._cached_balance

        if now - self._last_balance_time < max_age_sec and self._cached_balance["total_wallet"] > 0:
            return self._cached_balance

        try:
            bal = self.client.get_balance()
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

        # Throttling 20 detik jika posisi sudah tercatat
        if not force and (now - self._last_sync_position_time < 20.0) and self.active_position is not None:
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
                
                # Pertahankan SL/TP target
                if self.active_position and self.active_position.get("symbol") == symbol:
                    sl_price = self.active_position.get("sl_price", entry_price * (1.0 - config.SL_PERCENT if side == "buy" else 1.0 + config.SL_PERCENT))
                    tp_price = self.active_position.get("tp_price", entry_price * (1.0 + config.TP_PERCENT if side == "buy" else 1.0 - config.TP_PERCENT))
                    opened_at = self.active_position.get("opened_at", time.time())
                else:
                    sl_price = entry_price * (1.0 - config.SL_PERCENT) if side == "buy" else entry_price * (1.0 + config.SL_PERCENT)
                    tp_price = entry_price * (1.0 + config.TP_PERCENT) if side == "buy" else entry_price * (1.0 - config.TP_PERCENT)
                    opened_at = time.time()
                
                self.active_position = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "qty": contracts,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "opened_at": opened_at,
                    "notional": notional
                }
                return self.active_position
            else:
                # Pastikan tidak dalam cooldown sebelum menyatakan posisi telah tertutup
                if not self.client.is_banned() and self.active_position is not None:
                    console.log(f"[bold yellow]Posisi {self.active_position.get('symbol')} telah selesai/tertutup di Binance.[/bold yellow]")
                    self.active_position = None
                return None
        except Exception as e:
            console.log(f"[dim]Sync position check: {e}[/dim]")
            return self.active_position

    def get_compounded_notional(self) -> float:
        """
        Menghitung ukuran notional posisi berdasarkan alokasi 0.5% modal kas portofolio x Leverage (10x).
        Jika portofolio $100 -> modal alokasi $0.5 -> dengan leverage 10x = $5.0 notional.
        Memastikan notional tidak di bawah batas minimal Binance ($5.0).
        """
        bal = self.get_futures_balance()
        avail = bal["available"]
        base_wallet = avail if avail >= 1.0 else config.DEFAULT_CAPITAL
        
        min_margin = config.MIN_NOTIONAL / config.LEVERAGE
        target_margin = base_wallet * config.RISK_PORTFOLIO_PERCENT
        margin_used = max(min_margin, target_margin)
        return round(margin_used * config.LEVERAGE, 2)

    def _get_fallback_symbols(self) -> List[Dict[str, Any]]:
        """Daftar koin likuid teratas bawaan jika API publik bursa sedang dalam cooldown."""
        top_fallback = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "NEARUSDT", "APTUSDT", "TAOUSDT", "DOTUSDT", "FILUSDT",
            "WLDUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "FETUSDT", "RENDERUSDT", "TIAUSDT",
            "SEIUSDT", "ENAUSDT", "PEPEUSDT", "SHIBUSDT", "BONKUSDT", "WIFUSDT", "FLOKIUSDT"
        ]
        return [{"symbol": s, "quoteVolume": 1000000000.0} for s in top_fallback]

    def _fetch_top_symbols(self) -> List[Dict[str, Any]]:
        """Mengambil Top 50 koin crypto murni langsung dari Binance Futures REST API."""
        if self.client.is_banned():
            return self._cached_top_symbols if self._cached_top_symbols else self._get_fallback_symbols()

        try:
            data = self.client.fetch_top_tickers()
            if not isinstance(data, list):
                return self._cached_top_symbols if self._cached_top_symbols else self._get_fallback_symbols()

            filtered = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                sym = item.get("symbol", "")
                if sym not in self.client.allowed_crypto_symbols:
                    continue
                try:
                    q_vol = float(item.get("quoteVolume", 0.0))
                    filtered.append({
                        "symbol": sym,
                        "quoteVolume": q_vol
                    })
                except Exception:
                    continue
            filtered.sort(key=lambda x: x["quoteVolume"], reverse=True)
            res = filtered[:config.TOP_COINS_LIMIT]
            if res:
                return res
            return self._cached_top_symbols if self._cached_top_symbols else self._get_fallback_symbols()
        except Exception as e:
            console.log(f"[yellow]Notice fetch top tickers: {e}[/yellow]")
            return self._cached_top_symbols if self._cached_top_symbols else self._get_fallback_symbols()

    def scan_top_coins(self):
        """Memindai 20 koin likuid secara sekuensial (Super cepat ~1.5s, RAM <30MB)."""
        if self.client.is_banned() or self.client.is_scan_throttled():
            return
        t_start = time.time()
        try:
            now = time.time()
            if not self._cached_top_symbols or (now - self._last_top_symbols_refresh > 1800):
                self._cached_top_symbols = self._fetch_top_symbols()
                self._last_top_symbols_refresh = now
                gc.collect()

            bal = self.get_futures_balance()
            cap = bal["available"] if bal["available"] >= 1.0 else config.DEFAULT_CAPITAL
            
            results = []
            signals = []
            
            for rank, item in enumerate(self._cached_top_symbols, 1):
                if self.client.is_banned() or self.client.is_scan_throttled():
                    break
                sym = item["symbol"]
                q_vol = item["quoteVolume"]
                try:
                    # Jeda adaptif: 200ms normal, atau 1000ms jika weight bursa tinggi (>2200)
                    spacing = 1.0 if self.client.current_weight_1m >= 2200 else 0.20
                    time.sleep(spacing)
                    ohlcv = self.client.fetch_klines(sym, interval=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
                    if not ohlcv or len(ohlcv) < config.EMA_TREND + 5:
                        continue
                        
                    sig = strategy.check_signal_from_ohlcv(ohlcv, available_capital=cap, leverage=config.LEVERAGE)
                    
                    closes = [c[4] for c in ohlcv]
                    highs = [c[2] for c in ohlcv]
                    lows = [c[3] for c in ohlcv]
                    
                    ema_trend = strategy.calculate_ema_series(closes, config.EMA_TREND)[-2]
                    rsi_val = strategy.calculate_rsi_series(closes, config.RSI_PERIOD)[-2]
                    atr_val = strategy.calculate_atr_series(highs, lows, closes, config.ATR_PERIOD)[-2]
                    latest_price = closes[-1]
                    is_bullish = closes[-2] > ema_trend
                    
                    del ohlcv
                    del closes
                    del highs
                    del lows
                    
                    coin_data = {
                        "rank": rank,
                        "symbol": sym,
                        "price": latest_price,
                        "vol_24h_m": round(q_vol / 1_000_000, 2),
                        "trend": "BULLISH" if is_bullish else "BEARISH",
                        "rsi": round(rsi_val, 2),
                        "atr": round(atr_val, 4),
                        "signal": sig
                    }
                    results.append(coin_data)
                    
                    if sig is not None:
                        sig_data = sig.copy()
                        sig_data["symbol"] = sym
                        sig_data["rank"] = rank
                        sig_data["vol_24h_m"] = round(q_vol / 1_000_000, 2)
                        signals.append(sig_data)
                except Exception:
                    continue
                    
            gc.collect()
            
            self.ranked_pairs = results
            self.bullish_count = sum(1 for r in results if r["trend"] == "BULLISH")
            self.bearish_count = sum(1 for r in results if r["trend"] == "BEARISH")
            self.active_signals = sorted(signals, key=lambda x: x.get("score", 0), reverse=True)
            self.watchlist = sorted(results, key=lambda x: abs(x["rsi"] - 55.0))[:8]
            
            self.last_scan_duration_sec = round(time.time() - t_start, 2)
            self.last_scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Rekam sinyal dan snapshot saldo ke Neon Tech
            if self.active_signals:
                db.record_signals(self.active_signals)
                
            if now - self._last_wallet_db_snapshot > 300:
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
        
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        if base in TRADFI_EXCLUSIONS:
            console.log(f"[yellow]Melewati order pada {symbol} (Aset TradFi).[/yellow]")
            return False

        try:
            # 1. Pastikan ISOLATED margin dan Leverage (cukup sekali per simbol)
            if symbol not in self._configured_symbols:
                self.client.set_margin_type(symbol, "ISOLATED")
                self.client.set_leverage(symbol, config.LEVERAGE)
                self._configured_symbols.add(symbol)
            
            # 2. Ambil best bid/ask untuk harga Maker
            depth = self.client.fetch_best_bid_ask(symbol)
            if side == "BUY":
                best_price = depth["bid"] if depth.get("bid", 0.0) > 0 else target_price
            else:
                best_price = depth["ask"] if depth.get("ask", 0.0) > 0 else target_price
                
            formatted_price = self.client.format_price(symbol, best_price)
            if formatted_price <= 0:
                formatted_price = self.client.format_price(symbol, target_price)
            
            # 3. Hitung qty dengan jaminan nilai notional >= $5.00 dan presisi tepat
            notional = max(5.15, sig.get("notional", 5.15))
            formatted_qty = self.client.calculate_order_qty(symbol, notional, formatted_price)
            
            if formatted_qty <= 0:
                console.log(f"[red]Ukuran order terlalu kecil untuk {symbol}[/red]")
                return False
                
            console.log(f"[bold cyan]Dispatching Maker Limit Order (0.5% Portofolio): {side} {formatted_qty} {symbol} @ {formatted_price}[/bold cyan]")
            
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
                "placed_at": time.time()
            }
            
            # 4. Loop Pemantauan 30 Detik (Anti-FOMO Auto-Cancel)
            console.log(f"[yellow]Menunggu limit order terisi (maks 30 detik)...[/yellow]")
            t_start = time.time()
            while time.time() - t_start < config.LIMIT_TIMEOUT_SECONDS:
                time.sleep(2)
                try:
                    chk = self.client.get_order(symbol, order_id)
                    status = chk.get("status")
                    if status == "FILLED":
                        console.log(f"[bold green]LIMIT ORDER TERISI PENUH! ({symbol} @ {formatted_price})[/bold green]")
                        self.active_position = {
                            "symbol": symbol,
                            "side": side.lower(),
                            "entry_price": formatted_price,
                            "qty": formatted_qty,
                            "sl_price": sig["sl_price"],
                            "tp_price": sig["tp_price"],
                            "opened_at": time.time(),
                            "notional": formatted_qty * formatted_price
                        }
                        self.active_order = None
                        return True
                    elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                        console.log(f"[yellow]Order dibatalkan/ditolak ({status}).[/yellow]")
                        self.active_order = None
                        return False
                except Exception as err:
                    console.log(f"[dim]Pengecekan order {order_id}: {err}[/dim]")
                    
            console.log(f"[bold yellow]Limit order tidak terisi dalam 30 detik. Auto-cancel {order_id} (Anti-FOMO)...[/bold yellow]")
            try:
                self.client.cancel_order(symbol, order_id)
            except Exception as e:
                console.log(f"[dim]Gagal cancel order: {e}[/dim]")
                
            self.active_order = None
            return False
            
        except Exception as e:
            console.log(f"[red]Gagal dispatch limit order: {e}[/red]")
            self.active_order = None
            return False

    def monitor_active_position(self):
        """Memantau posisi aktif terhadap target Take Profit (+1.0%) dan Stop Loss (-0.5%)."""
        if not self.active_position:
            return
            
        pos = self.active_position
        symbol = pos["symbol"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        qty = pos["qty"]
        sl_price = pos["sl_price"]
        tp_price = pos["tp_price"]
        
        try:
            current_price = self.client.fetch_price(symbol)
            if current_price <= 0:
                return
                
            pnl_pct = ((current_price - entry_price) / entry_price) if side == "buy" else ((entry_price - current_price) / entry_price)
            pnl_usd = pnl_pct * pos["notional"]
            
            # --- 1. Break-Even Protection (+0.6% profit) ---
            if side == "buy":
                if pnl_pct >= config.BREAK_EVEN_TRIGGER and pos["sl_price"] < entry_price:
                    pos["sl_price"] = entry_price * 1.001  # Kunci di Entry + 0.1% (tutup biaya fee)
                    console.log(f"[bold cyan]🛡️ BREAK-EVEN DIAKTIFKAN pada {symbol}: SL digeser ke {pos['sl_price']:.4f} (Posisi Bebas Risiko)[/bold cyan]")
                
                # --- 2. Trailing Stop (+1.0% profit) ---
                if pnl_pct >= config.TRAILING_STOP_TRIGGER:
                    trailing_target = current_price * (1.0 - config.TRAILING_STOP_DISTANCE)
                    if trailing_target > pos["sl_price"]:
                        pos["sl_price"] = trailing_target
                        console.log(f"[bold green]📈 TRAILING STOP NAIK pada {symbol}: SL dikunci di {trailing_target:.4f}[/bold green]")
                        
            elif side == "sell":
                if pnl_pct >= config.BREAK_EVEN_TRIGGER and pos["sl_price"] > entry_price:
                    pos["sl_price"] = entry_price * 0.999
                    console.log(f"[bold cyan]🛡️ BREAK-EVEN DIAKTIFKAN pada {symbol}: SL digeser ke {pos['sl_price']:.4f} (Posisi Bebas Risiko)[/bold cyan]")
                
                if pnl_pct >= config.TRAILING_STOP_TRIGGER:
                    trailing_target = current_price * (1.0 + config.TRAILING_STOP_DISTANCE)
                    if trailing_target < pos["sl_price"]:
                        pos["sl_price"] = trailing_target
                        console.log(f"[bold green]📈 TRAILING STOP TURUN pada {symbol}: SL dikunci di {trailing_target:.4f}[/bold green]")

            # Perbarui nilai SL/TP terkini
            sl_price = pos["sl_price"]
            tp_price = pos["tp_price"]

            hit_tp = (current_price >= tp_price) if side == "buy" else (current_price <= tp_price)
            hit_sl = (current_price <= sl_price) if side == "buy" else (current_price >= sl_price)
            
            console.log(f"[dim]Pemantauan 5s: {symbol} @ {current_price} | PnL: {pnl_pct*100:+.2f}% (${pnl_usd:+.2f}) | TP: {tp_price:.4f} | SL: {sl_price:.4f}[/dim]")
            
            if hit_tp:
                console.log(f"[bold green]TAKE PROFIT TERCAPAI! (+{pnl_pct*100:.2f}%, PnL: +${pnl_usd:.2f}) pada {symbol}[/bold green]")
                close_side = "SELL" if side == "buy" else "BUY"
                self.client.create_market_close_order(symbol=symbol, side=close_side, qty=qty)
                
                trade_record = {
                    "symbol": symbol,
                    "side": side.upper(),
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "qty": qty,
                    "notional": pos["notional"],
                    "margin_used": pos["notional"] / config.LEVERAGE,
                    "pnl_usd": round(pnl_usd, 4),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "result": "WIN",
                    "closed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.trade_history.append(trade_record)
                db.record_trade(trade_record)
                
                self.total_trades += 1
                self.winning_trades += 1
                self.total_pnl_usd += pnl_usd
                self.active_position = None
                
            elif hit_sl:
                is_be_or_profit = pnl_usd >= 0.0
                tag = "BREAK-EVEN / TRAILING EXIT" if is_be_or_profit else "STOP LOSS TERPICU"
                res = "WIN" if is_be_or_profit else "LOSS"
                color = "green" if is_be_or_profit else "red"
                
                console.log(f"[bold {color}]{tag}! ({pnl_pct*100:+.2f}%, PnL: ${pnl_usd:+.2f}) pada {symbol}[/bold {color}]")
                close_side = "SELL" if side == "buy" else "BUY"
                self.client.create_market_close_order(symbol=symbol, side=close_side, qty=qty)
                
                trade_record = {
                    "symbol": symbol,
                    "side": side.upper(),
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "qty": qty,
                    "notional": pos["notional"],
                    "margin_used": pos["notional"] / config.LEVERAGE,
                    "pnl_usd": round(pnl_usd, 4),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "result": res,
                    "closed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.trade_history.append(trade_record)
                db.record_trade(trade_record)
                
                self.total_trades += 1
                if is_be_or_profit:
                    self.winning_trades += 1
                self.total_pnl_usd += pnl_usd
                self.active_position = None
                
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
                            time.sleep(min(5, max(1, s_left)))
                        else:
                            time.sleep(min(30, max(5, s_left + 1)))
                        continue

                # Muat ulang aturan pasar jika sebelumnya gagal akibat cooldown
                if len(self.client._symbols_rules) == 0:
                    self.client.load_markets()

                # 1. Selalu sinkronisasi posisi riil dari Binance
                self.sync_exchange_position()

                # 2. Jika ada posisi aktif, pantau harga setiap 5 detik
                if self.active_position:
                    self.monitor_active_position()
                    time.sleep(5)  # Cek harga posisi aktif setiap 5 detik sesuai permintaan
                    continue
                    
                # 3. Jalankan pemindaian koin Top volume
                self.scan_top_coins()
                
                # 4. Cek saldo akun
                bal = self.get_futures_balance()
                avail_usdt = bal["available"]
                
                # 5. Jika ada sinyal valid dan saldo tersedia cukup
                if self.active_signals and not self.active_order and not self.active_position:
                    best_signal = self.active_signals[0]
                    console.log(f"[bold green]Sinyal terbaik terdeteksi:[/bold green] {best_signal['side']} {best_signal['symbol']} (Skor: {best_signal.get('score', 0)})")
                    
                    min_req = config.MIN_NOTIONAL / config.LEVERAGE
                    if avail_usdt >= min_req:
                        self.execute_limit_order(best_signal)
                    else:
                        console.log(f"[yellow]Saldo USDT Futures (${avail_usdt:.2f}) di bawah minimum (${min_req:.2f}). Menunggu modal.[/yellow]")
                        
                if self.active_position:
                    time.sleep(5)  # Langsung monitor 5s jika posisi baru saja terisi
                else:
                    time.sleep(config.SCAN_INTERVAL_SECONDS)
                
            except Exception as e:
                console.log(f"[red]Error di siklus bot scalper: {e}[/red]")
                time.sleep(10)

    def run(self):
        self.run_scan_loop()

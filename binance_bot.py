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
        self._cached_balance: Dict[str, float] = {"total_wallet": 0.0, "available": 0.0, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self._last_sync_position_time: float = 0.0
        self._configured_symbols: Set[str] = set()
        self._last_reversal_check_time: float = 0.0
        self.last_error: Optional[str] = None
        self._symbol_order_cooldown: Dict[str, float] = {}

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
                
                # Pertahankan SL/TP target dan status BEP
                if self.active_position and self.active_position.get("symbol") == symbol:
                    sl_price = self.active_position.get("sl_price", entry_price * (1.0 - config.SL_PERCENT if side == "buy" else 1.0 + config.SL_PERCENT))
                    tp_price = self.active_position.get("tp_price", entry_price * (1.0 + config.TP_PERCENT if side == "buy" else 1.0 - config.TP_PERCENT))
                    bep_trigger_price = self.active_position.get("bep_trigger_price", entry_price * (1.0 + config.BEP_PROFIT_TRIGGER if side == "buy" else 1.0 - config.BEP_PROFIT_TRIGGER))
                    bep_activated = self.active_position.get("bep_activated", False)
                    opened_at = self.active_position.get("opened_at", time.time())
                else:
                    sl_price = entry_price * (1.0 - config.SL_PERCENT) if side == "buy" else entry_price * (1.0 + config.SL_PERCENT)
                    tp_price = entry_price * (1.0 + config.TP_PERCENT) if side == "buy" else entry_price * (1.0 - config.TP_PERCENT)
                    bep_trigger_price = entry_price * (1.0 + config.BEP_PROFIT_TRIGGER) if side == "buy" else entry_price * (1.0 - config.BEP_PROFIT_TRIGGER)
                    bep_activated = False
                    opened_at = time.time()
                
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
        Menghitung ukuran notional posisi berdasarkan aturan margin bertingkat (Leverage 50x):
        - Saldo < $50: gunakan margin $0.20 (Notional $10.00 pada 50x)
        - Saldo >= $50: kembali ke 0.5% margin per posisi dari total saldo
        """
        bal = self.get_futures_balance()
        avail = bal["available"]
        base_wallet = avail if avail >= 1.0 else config.DEFAULT_CAPITAL
        
        if base_wallet < config.BALANCE_THRESHOLD_SCALING:
            target_margin = config.FIXED_MARGIN_LOW_BALANCE
        else:
            target_margin = base_wallet * config.RISK_PORTFOLIO_PERCENT

        raw_notional = target_margin * config.LEVERAGE
        notional = max(config.MIN_NOTIONAL + 0.15, raw_notional)
        if base_wallet < config.BALANCE_THRESHOLD_SCALING:
            notional = min(notional, config.MAX_ORDER_NOTIONAL)
        return round(notional, 2)

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
        Mengambil Semesta 200 Koin Crypto Murni (Non-Stablecoin) Langsung dari Binance Futures:
        1. Buang semua stablecoin (USDC, FDUSD, BUSD, TUSD, EUR, DAI, AEUR, USDP, USD1, BFUSD, USDT, USTC, dll).
        2. Hanya koin yang terdaftar di self.client.allowed_crypto_symbols.
        3. Filter koin dengan volume 24 jam >= config.MIN_24H_VOLUME_USD ($3M).
        4. Saring koin yang minimum order-nya terlalu besar untuk modal mikro ($11 USDT).
        5. Urutkan berdasarkan quoteVolume tertinggi dan ambil tepat 200 koin crypto murni.
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

                    # Filter koin dengan ukuran lot minimum terlalu besar untuk akun modal mikro ($11 USDT)
                    rules = self.client._symbols_rules.get(sym, {})
                    min_q = rules.get("min_qty", 0.0)
                    if (min_q * last_price) > config.MAX_ORDER_NOTIONAL:
                        continue

                    filtered.append({
                        "symbol": sym,
                        "quoteVolume": q_vol
                    })
                except Exception:
                    continue

            # Urutkan berdasarkan volume 24 jam tertinggi
            filtered.sort(key=lambda x: x["quoteVolume"], reverse=True)
            res = filtered[:config.SCAN_UNIVERSE_LIMIT]
            if res:
                console.log(f"[bold green]Berhasil memuat {len(res)} koin crypto murni (non-stablecoin) ke dalam semesta rotasi.[/bold green]")
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

            # 1. Fetch Multi-Timeframe: 15m untuk Struktur & Area Likuidasi, 5m untuk Eksekusi Scalp
            ohlcv_15m = self.client.fetch_klines(sym, interval=config.STRUCTURE_TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.08)
            ohlcv_5m = self.client.fetch_klines(sym, interval=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.08)
            deriv_data = self.client.fetch_derivatives_data(sym, period="5m")

            if not ohlcv_5m or len(ohlcv_5m) < 25:
                self._current_rotation_index = (self._current_rotation_index + 1) % total_univ
                return

            # 2. Analisis Menyeluruh Sesuai Master Blueprint Akademi Crypto
            analysis = strategy.analyze_coin_comprehensive(
                symbol=sym,
                ohlcv_htf=ohlcv_15m,
                ohlcv_ltf=ohlcv_5m,
                derivatives_data=deriv_data,
                available_capital=cap,
                leverage=config.LEVERAGE
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
            # 1. Pastikan ISOLATED margin dan Dynamic Leverage sesuai analisis
            dynamic_leverage = sig.get("dynamic_leverage", config.LEVERAGE)
            self.client.set_margin_type(symbol, "ISOLATED")
            self.client.set_leverage(symbol, dynamic_leverage)
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
                
            effective_notional = formatted_qty * formatted_price
            margin_used = effective_notional / dynamic_leverage
            if effective_notional > config.MAX_ORDER_NOTIONAL:
                console.log(f"[bold yellow]🛡️ Filter Ukuran Akun: Minimum order {symbol} bernilai ${effective_notional:.2f} (Margin: ${margin_used:.2f}). Melewati agar margin tetap aman (Maks Notional: ${config.MAX_ORDER_NOTIONAL:.2f}).[/bold yellow]")
                return False

            console.log(f"[bold cyan]Dispatching Maker Limit Order (Risk: ${sig.get('risk_usd', 0.05):.3f}, Leverage: {dynamic_leverage}x): {side} {formatted_qty} {symbol} @ {formatted_price} (Notional: ${effective_notional:.2f}, Margin: ${margin_used:.2f})[/bold cyan]")
            
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
                "leverage": dynamic_leverage,
                "risk_usd": sig.get("risk_usd", 0.05),
                "reward_usd": sig.get("reward_usd", 0.10),
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
                            "bep_trigger_price": sig.get("bep_trigger_price", 0.0),
                            "bep_activated": False,
                            "leverage": dynamic_leverage,
                            "risk_usd": sig.get("risk_usd", 0.05),
                            "reward_usd": sig.get("reward_usd", 0.10),
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

    def execute_maker_close(self, symbol: str, side: str, qty: float, target_price: float) -> bool:
        """
        Menutup posisi menggunakan Maker Limit Order (timeInForce=GTX / Post Only) agar fee terendah (0.02%).
        Memantau order hingga 8 detik di posisi harga teratas (top of book).
        Jika pergerakan pasar cepat tak kunjung terisi, fallback otomatis ke market order agar modal terlindungi.
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
            
            # Jika ditolak karena crossed (-5022), geser 1 tick agar tetap maker
            if isinstance(res, dict) and res.get("code") == -5022:
                if side == "SELL":
                    formatted_price = self.client.format_price(symbol, formatted_price + tick)
                else:
                    formatted_price = self.client.format_price(symbol, formatted_price - tick)
                res = self.client.create_limit_close_order(symbol, side, qty, formatted_price)

            order_id = res.get("orderId") if isinstance(res, dict) else None
            if not order_id:
                console.log(f"[yellow]Limit close gagal, beralih ke market close darurat...[/yellow]")
                self.client.create_market_close_order(symbol, side, qty)
                return True

            # Pantau hingga 8 detik agar terisi sebagai Maker
            t0 = time.time()
            while time.time() - t0 < 8:
                time.sleep(1.5)
                chk = self.client.get_order(symbol, order_id)
                status = chk.get("status")
                if status == "FILLED":
                    console.log(f"[bold green]MAKER LIMIT CLOSE TERISI PENUH! ({symbol} @ {formatted_price}, Fee Terendah Maker)[/bold green]")
                    return True
                elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                    break

            # Jika belum terisi setelah 8 detik, batalkan dan tuntaskan dengan market order
            console.log(f"[yellow]Maker limit close belum terisi setelah 8s. Menuntaskan dengan market order...[/yellow]")
            try:
                self.client.cancel_order(symbol, order_id)
            except Exception:
                pass
            self.client.create_market_close_order(symbol, side, qty)
            return True

        except Exception as e:
            console.log(f"[yellow]Notice maker close: {e}, fallback ke market close...[/yellow]")
            try:
                self.client.create_market_close_order(symbol, side, qty)
                return True
            except Exception as e2:
                console.log(f"[red]Gagal menutup posisi: {e2}[/red]")
                return False

    def monitor_active_position(self):
        """
        Memantau posisi aktif dengan manajemen risiko ketat Akademi Crypto (Kalimasada):
        1. Target Take Profit penuh: +1.4% (Risk to Reward 1:2).
        2. Stop Loss awal: -0.7% (Resiko terukur 0.5% portofolio).
        3. Proteksi Break-Even (BEP): Begitu profit mencapai 1R (+0.7%), SL otomatis digeser
           ke Break-Even (Entry + 0.05% untuk cover fee) sehingga transaksi 100% bebas risiko.
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
                    new_sl = entry_price * 1.0005 if side == "buy" else entry_price * 0.9995
                    pos["sl_price"] = new_sl
                    pos["bep_activated"] = True
                    console.log(f"[bold cyan]🛡️ BREAK-EVEN DIAKTIFKAN pada {symbol}: Profit mencapai 1R (+0.7%), SL digeser ke {new_sl:.4f} (Posisi Bebas Risiko Bebas Fee)[/bold cyan]")

            # Perbarui nilai SL/TP terkini
            sl_price = pos["sl_price"]
            tp_price = pos["tp_price"]

            hit_tp = (current_price >= tp_price) if side == "buy" else (current_price <= tp_price)
            hit_sl = (current_price <= sl_price) if side == "buy" else (current_price >= sl_price)
            
            console.log(f"[dim]Pemantauan 5s: {symbol} @ {current_price} | PnL: {pnl_pct*100:+.2f}% (${pnl_usd:+.2f}) | TP: {tp_price:.4f} | SL: {sl_price:.4f} | BEP: {'AKTIF' if pos.get('bep_activated') else 'MENUNGGU 1R'}[/dim]")
            
            if hit_tp:
                console.log(f"[bold green]🎯 TAKE PROFIT TERCAPAI (RR 1:2 / +1.4%)! (+{pnl_pct*100:.2f}%, PnL: +${pnl_usd:.2f}) pada {symbol}[/bold green]")
                close_side = "SELL" if side == "buy" else "BUY"
                self.execute_maker_close(symbol=symbol, side=close_side, qty=qty, target_price=current_price)
                
                trade_record = {
                    "symbol": symbol,
                    "side": side.upper(),
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "qty": qty,
                    "notional": pos["notional"],
                    "margin_used": pos["notional"] / pos_leverage,
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
                tag = "🛡️ BREAK-EVEN EXIT (Bebas Risiko)" if is_be_or_profit else "🛑 STOP LOSS TERPICU (-0.7%)"
                res = "WIN" if is_be_or_profit else "LOSS"
                color = "green" if is_be_or_profit else "red"
                
                console.log(f"[bold {color}]{tag}! ({pnl_pct*100:+.2f}%, PnL: ${pnl_usd:+.2f}) pada {symbol}[/bold {color}]")
                close_side = "SELL" if side == "buy" else "BUY"
                self.execute_maker_close(symbol=symbol, side=close_side, qty=qty, target_price=current_price)
                
                trade_record = {
                    "symbol": symbol,
                    "side": side.upper(),
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "qty": qty,
                    "notional": pos["notional"],
                    "margin_used": pos["notional"] / pos_leverage,
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
                    sym = best_signal.get("symbol", "")
                    if time.time() < self._symbol_order_cooldown.get(sym, 0.0):
                        # Jika koin teratas masih dalam cooldown setelah auto-cancel, buang dari active_signals
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != sym]
                    else:
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

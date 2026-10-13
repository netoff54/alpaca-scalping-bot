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
        
        # Cache Top 50 koin (diperbarui setiap 30 menit)
        self._cached_top_symbols: List[Dict[str, Any]] = []
        self._last_top_symbols_refresh: float = 0.0
        self._last_wallet_db_snapshot: float = 0.0
        
        # Balance cache & Rate limit cooldown
        self._cached_balance: Dict[str, float] = {"total_wallet": 0.0, "available": 0.0, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self._last_sync_position_time: float = 0.0
        self._configured_symbols: Set[str] = set()
        self._last_reversal_check_time: float = 0.0
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
        Menghitung ukuran notional posisi berdasarkan model Risk-Budget 0.5% portofolio.
        Jika SL = 1.0%, kerugian maksimal saat SL tepat 0.5% dari saldo kas portofolio.
        """
        bal = self.get_futures_balance()
        avail = bal["available"]
        base_wallet = avail if avail >= 1.0 else config.DEFAULT_CAPITAL
        
        risk_budget = base_wallet * config.RISK_PORTFOLIO_PERCENT
        ideal_notional = risk_budget / config.SL_PERCENT
        notional = max(config.MIN_NOTIONAL + 0.15, ideal_notional)
        if base_wallet < 20.0:
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
                    closes = [c[4] for c in ohlcv]
                    highs = [c[2] for c in ohlcv]
                    lows = [c[3] for c in ohlcv]
                    latest_price = closes[-1]

                    # 1. Filter koin dengan ukuran lot minimum terlalu besar untuk akun modal mikro (misal BTCUSDT di mana 0.001 BTC = $83+)
                    rules = self.client._symbols_rules.get(sym, {})
                    min_q = rules.get("min_qty", 0.0)
                    if (min_q * latest_price) > config.MAX_ORDER_NOTIONAL:
                        del ohlcv
                        del closes
                        del highs
                        del lows
                        continue

                    # Ambil data sentimen arus akun Long vs Short global (TF 5m)
                    ls_data = self.client.fetch_long_short_ratio(sym, period="5m")
                    sig = strategy.check_signal_from_ohlcv(ohlcv, available_capital=cap, leverage=config.LEVERAGE, ls_data=ls_data)
                    
                    ema_trend = strategy.calculate_ema_series(closes, config.EMA_TREND)[-2]
                    rsi_val = strategy.calculate_rsi_series(closes, config.RSI_PERIOD)[-2]
                    atr_val = strategy.calculate_atr_series(highs, lows, closes, config.ATR_PERIOD)[-2]
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
                        "long_pct": ls_data.get("long_pct", 50.0),
                        "short_pct": ls_data.get("short_pct", 50.0),
                        "ls_ratio": ls_data.get("ratio", 1.0),
                        "n_pattern": sig.get("n_pattern") if sig else "NONE",
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
                console.log(f"[bold yellow]🛡️ Filter Ukuran Akun: Minimum order {symbol} bernilai ${effective_notional:.2f} (Margin: ${margin_used:.2f}). Melewati agar margin tetap ~$0.25 - $0.50 (Maks Notional: ${config.MAX_ORDER_NOTIONAL:.2f}).[/bold yellow]")
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
                            "leverage": dynamic_leverage,
                            "risk_usd": sig.get("risk_usd", 0.05),
                            "reward_usd": sig.get("reward_usd", 0.10),
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

    def check_market_reversal(self, symbol: str, side: str, pnl_pct: float) -> Tuple[bool, str]:
        """
        Mendeteksi pembalikan arah candlestick & indikator secara fleksibel:
        1. Jika posisi dalam kondisi PROFIT (>= +0.3%):
           - Muncul candle penolakan / reversal wick (shooting star / hammer)
           - EMA 9 memotong balik EMA 21
           - RSI kehilangan momentum (<48 untuk buy / >52 untuk sell)
           -> Segera Take Profit lebih awal! Jangan kaku menunggu full TP atau terseret balik ke SL.
        2. Jika posisi dalam kondisi MINUS / BREAK-EVEN:
           - Candlestick breakdown dan konfirmasi pembalikan arah di bawah EMA 21
           -> Cut loss kecil lebih awal sebelum menyentuh SL penuh (-1.0%).
        """
        try:
            ohlcv = self.client.fetch_klines(symbol, interval="1m", limit=30)
            if not ohlcv or len(ohlcv) < 22:
                return False, ""

            closes = [c[4] for c in ohlcv]
            opens = [c[1] for c in ohlcv]
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]

            c_prev_close = closes[-3]
            c_open = opens[-2]
            c_close = closes[-2]
            c_high = highs[-2]
            c_low = lows[-2]
            c_range = c_high - c_low

            ema9 = strategy.calculate_ema_series(closes, 9)
            ema21 = strategy.calculate_ema_series(closes, 21)
            rsi = strategy.calculate_rsi_series(closes, 14)[-2]

            # 1. Analisis untuk posisi BUY (Long)
            if side == "buy":
                # A. KONDISI PROFIT (>= +0.3%): Amankan profit jika ada tanda pembalikan turun
                if pnl_pct >= config.REVERSAL_PROFIT_TRIGGER:
                    # Sinyal Reversal 1: Upper rejection wick pada puncak (Shooting star / Bull trap)
                    if c_range > 0 and (c_high - max(c_open, c_close)) >= (c_range * 0.45) and c_close < c_open:
                        return True, f"Candle Rejection di puncak (Upper Wick {((c_high - c_open)/c_range)*100:.0f}%)"
                    
                    # Sinyal Reversal 2: EMA 9 memotong ke bawah EMA 21 (Death Cross 1m)
                    if ema9[-2] < ema21[-2] and ema9[-3] >= ema21[-3]:
                        return True, "EMA 9 Death Cross ke bawah EMA 21 pada TF 1m"

                    # Sinyal Reversal 3: Momentum RSI melemah drastis
                    if rsi < 48.0 and c_close < c_open:
                        return True, f"Momentum RSI melemah ({rsi:.1f} < 48)"

                    # Sinyal Reversal 4: Bearish Engulfing solid
                    if c_close < c_open and c_close < c_prev_close and (c_open - c_close) >= (c_range * 0.65):
                        return True, "Candle Bearish Engulfing solid membalikkan tren"

                # B. KONDISI MINUS: Cut loss dini jika terjadi pembalikan tren terkonfirmasi
                elif pnl_pct < -0.002:
                    if ema9[-2] < ema21[-2] and c_close < ema21[-2] and c_close < c_open:
                        return True, "Breakdown terkonfirmasi di bawah EMA 21 (Cut loss dini sebelum SL 1%)"

            # 2. Analisis untuk posisi SELL (Short)
            elif side == "sell":
                # A. KONDISI PROFIT (>= +0.3%): Amankan profit jika ada tanda pembalikan naik
                if pnl_pct >= config.REVERSAL_PROFIT_TRIGGER:
                    # Sinyal Reversal 1: Lower rejection wick di dasar (Hammer / Buyer absorption)
                    if c_range > 0 and (min(c_open, c_close) - c_low) >= (c_range * 0.45) and c_close > c_open:
                        return True, f"Candle Rejection di dasar (Lower Wick {((c_close - c_low)/c_range)*100:.0f}%)"
                    
                    # Sinyal Reversal 2: EMA 9 memotong ke atas EMA 21 (Golden Cross 1m)
                    if ema9[-2] > ema21[-2] and ema9[-3] <= ema21[-3]:
                        return True, "EMA 9 Golden Cross ke atas EMA 21 pada TF 1m"

                    # Sinyal Reversal 3: Momentum RSI memantul naik
                    if rsi > 52.0 and c_close > c_open:
                        return True, f"Momentum RSI memantul naik ({rsi:.1f} > 52)"

                    # Sinyal Reversal 4: Bullish Engulfing solid
                    if c_close > c_open and c_close > c_prev_close and (c_close - c_open) >= (c_range * 0.65):
                        return True, "Candle Bullish Engulfing solid membalikkan tren"

                # B. KONDISI MINUS: Cut loss dini jika terjadi breakout ke atas
                elif pnl_pct < -0.002:
                    if ema9[-2] > ema21[-2] and c_close > ema21[-2] and c_close > c_open:
                        return True, "Breakout terkonfirmasi di atas EMA 21 (Cut loss dini sebelum SL 1%)"

            return False, ""
        except Exception:
            return False, ""

    def monitor_active_position(self):
        """Memantau posisi aktif terhadap target Take Profit (+2.0%) dan Stop Loss (-1.0%) dengan Maker Limit Exit & Fleksibel Reversal."""
        if not self.active_position:
            return
            
        pos = self.active_position
        symbol = pos["symbol"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        qty = pos["qty"]
        sl_price = pos["sl_price"]
        tp_price = pos["tp_price"]
        pos_leverage = pos.get("leverage", config.LEVERAGE)
        
        try:
            current_price = self.client.fetch_price(symbol)
            if current_price <= 0:
                return
                
            pnl_pct = ((current_price - entry_price) / entry_price) if side == "buy" else ((entry_price - current_price) / entry_price)
            pnl_usd = pnl_pct * pos["notional"]

            # --- 0. Cek Pembalikan Arah Fleksibel (Jangan Kaku: Amankan Profit Lebih Awal / Cut Loss Dini) ---
            now = time.time()
            if config.ENABLE_FLEXIBLE_EXIT and (now - self._last_reversal_check_time >= 10.0):
                self._last_reversal_check_time = now
                is_reversal, rev_reason = self.check_market_reversal(symbol, side, pnl_pct)
                if is_reversal:
                    is_win = pnl_usd >= 0
                    tag = "AMANKAN PROFIT FLEKSIBEL" if is_win else "EARLY CUT LOSS (CEGAH SL PENUH)"
                    color = "bold green" if is_win else "bold yellow"
                    console.log(f"[{color}]⚡ {tag}: {rev_reason} ({pnl_pct*100:+.2f}%, ${pnl_usd:+.2f}) pada {symbol}[/{color}]")
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
                        "result": "WIN" if is_win else "LOSS",
                        "closed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.trade_history.append(trade_record)
                    db.record_trade(trade_record)
                    self.total_trades += 1
                    if is_win:
                        self.winning_trades += 1
                    self.total_pnl_usd += pnl_usd
                    self.active_position = None
                    return
            
            # --- 1. Break-Even Protection (+0.5% profit) ---
            if side == "buy":
                if pnl_pct >= config.BREAK_EVEN_TRIGGER and pos["sl_price"] < entry_price:
                    pos["sl_price"] = entry_price * 1.0005  # Kunci di Entry + 0.05% (tutup biaya fee maker)
                    console.log(f"[bold cyan]🛡️ BREAK-EVEN DIAKTIFKAN pada {symbol}: SL digeser ke {pos['sl_price']:.4f} (Posisi Bebas Risiko)[/bold cyan]")
                
                # --- 2. Trailing Stop (+0.9% profit) ---
                if pnl_pct >= config.TRAILING_STOP_TRIGGER:
                    trailing_target = current_price * (1.0 - config.TRAILING_STOP_DISTANCE)
                    if trailing_target > pos["sl_price"]:
                        pos["sl_price"] = trailing_target
                        console.log(f"[bold green]📈 TRAILING STOP NAIK pada {symbol}: SL dikunci di {trailing_target:.4f}[/bold green]")
                        
            elif side == "sell":
                if pnl_pct >= config.BREAK_EVEN_TRIGGER and pos["sl_price"] > entry_price:
                    pos["sl_price"] = entry_price * 0.9995
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
                tag = "BREAK-EVEN / TRAILING EXIT" if is_be_or_profit else "STOP LOSS TERPICU"
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

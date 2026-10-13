import os
import time
import math
import threading
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
import requests
import ccxt
from rich.console import Console

from config import config
import strategy

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
        
        # CCXT Client Sinkron untuk eksekusi order & balance
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
                'warnOnFetchOpenOrdersWithoutSymbol': False,
                'fetchCurrencies': False
            }
        })
        
        # HTTP Session persisten untuk scanning super cepat & hemat memori (<40MB)
        self.http_session = requests.Session()
        self.http_session.headers.update({
            'User-Agent': 'BinanceScalper/2.0 (Render Frankfurt)'
        })
        
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
        
        # Balance cache & Rate limit cooldown
        self._cached_balance: Dict[str, float] = {"total_wallet": 0.0, "available": 0.0, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self._ban_until: float = 0.0
        self._last_ban_log_time: float = 0.0
        self.last_error: Optional[str] = None

    def _ensure_single_asset_mode(self):
        """Memastikan mode Multi-Assets dimatikan agar ISOLATED margin dapat digunakan."""
        if time.time() < self._ban_until:
            return
        try:
            res = self.exchange.fapiPrivateGetMultiAssetsMargin()
            if res.get('multiAssetsMargin') is True:
                console.log("[yellow]Mengubah akun ke Single-Asset Margin Mode untuk ISOLATED margin...[/yellow]")
                self.exchange.fapiPrivatePostMultiAssetsMargin({'multiAssetsMargin': 'false'})
                console.log("[green]Single-Asset Mode berhasil diaktifkan.[/green]")
        except Exception as e:
            console.log(f"[dim]Cek MultiAssetsMargin: {e}[/dim]")

    def get_futures_balance(self, max_age_sec: float = 60.0) -> Dict[str, float]:
        """Mengambil saldo wallet USDⓈ-M Futures dengan caching 60 detik (Sangat aman dari rate limit)."""
        now = time.time()
        if now < self._ban_until:
            if now - self._last_ban_log_time > 120:
                self._last_ban_log_time = now
                s_left = int(self._ban_until - now)
                console.log(f"[yellow]IP server dalam cooldown rate limit ({s_left} detik tersisa)...[/yellow]")
            return self._cached_balance

        if now - self._last_balance_time < max_age_sec and self._cached_balance["total_wallet"] > 0:
            return self._cached_balance

        try:
            bal = self.exchange.fetch_balance()
            info = bal.get('info', {})
            total_wallet = float(info.get('totalWalletBalance', 0.0))
            available_balance = float(info.get('availableBalance', 0.0))
            unrealized_pnl = float(info.get('totalUnrealizedProfit', 0.0))
            
            for a in info.get('assets', []):
                if a.get('asset') == 'USDT':
                    available_balance = float(a.get('availableBalance', available_balance))
                    total_wallet = float(a.get('walletBalance', total_wallet))
                    break
                    
            self._cached_balance = {
                "total_wallet": total_wallet,
                "available": available_balance,
                "unrealized_pnl": unrealized_pnl
            }
            self._last_balance_time = now
            self.last_error = None
            return self._cached_balance
        except Exception as e:
            err_msg = str(e)
            self.last_error = f"Balance error: {err_msg}"
            self._last_balance_time = now + 15
            
            if "-1003" in err_msg or "IP banned" in err_msg:
                import re
                match = re.search(r"IP banned until (\d+)", err_msg)
                if match:
                    self._ban_until = float(match.group(1)) / 1000.0
                else:
                    self._ban_until = now + 600.0
                console.log(f"[bold yellow]Rate limit Binance terpicu. Menunda request hingga {time.strftime('%H:%M:%S', time.localtime(self._ban_until))}[/bold yellow]")
            else:
                console.log(f"[red]Error mengambil balance Futures: {e}[/red]")
            return self._cached_balance

    def sync_exchange_position(self) -> Optional[Dict[str, Any]]:
        """
        Sinkronisasi otomatis dengan posisi terbuka di bursa Binance Futures.
        Jika posisi sudah ditutup oleh bursa (TP/SL), bot langsung membersihkan state dan mencari peluang baru.
        """
        if time.time() < self._ban_until:
            return self.active_position

        try:
            positions = self.exchange.fetch_positions()
            open_positions = [
                p for p in positions 
                if p.get('contracts') and abs(float(p['contracts'])) > 0
            ]
            
            if open_positions:
                pos = open_positions[0]
                symbol = pos.get('symbol', '')
                contracts = abs(float(pos.get('contracts', 0)))
                side = 'buy' if float(pos.get('contracts', 0)) > 0 else 'sell'
                entry_price = float(pos.get('entryPrice', 0.0))
                notional = float(pos.get('notional', contracts * entry_price))
                
                # Pertahankan SL/TP target
                if self.active_position and self.active_position.get('symbol') == symbol:
                    sl_price = self.active_position.get('sl_price', entry_price * (0.995 if side == 'buy' else 1.005))
                    tp_price = self.active_position.get('tp_price', entry_price * (1.010 if side == 'buy' else 0.990))
                    opened_at = self.active_position.get('opened_at', time.time())
                else:
                    sl_price = entry_price * (1.0 - config.SL_PERCENT) if side == 'buy' else entry_price * (1.0 + config.SL_PERCENT)
                    tp_price = entry_price * (1.0 + config.TP_PERCENT) if side == 'buy' else entry_price * (1.0 - config.TP_PERCENT)
                    opened_at = time.time()
                
                self.active_position = {
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'qty': contracts,
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                    'opened_at': opened_at,
                    'notional': notional
                }
                return self.active_position
            else:
                if self.active_position is not None:
                    console.log(f"[bold yellow]Posisi {self.active_position.get('symbol')} telah selesai/tertutup di Binance.[/bold yellow]")
                    self.active_position = None
                return None
        except Exception as e:
            console.log(f"[dim]Sync position check: {e}[/dim]")
            return self.active_position

    def get_compounded_notional(self) -> float:
        """Menghitung ukuran order berikutnya (Compounding 100% saldo kas)."""
        bal = self.get_futures_balance()
        avail = bal["available"]
        if avail >= 1.0:
            return round(avail * config.LEVERAGE, 2)
        return round(config.DEFAULT_CAPITAL * config.LEVERAGE, 2)

    def set_margin_and_leverage(self, symbol: str):
        """Mengatur margin ke ISOLATED dan leverage 5x."""
        try:
            self.exchange.set_margin_mode('ISOLATED', symbol)
        except Exception:
            pass
            
        try:
            self.exchange.set_leverage(config.LEVERAGE, symbol)
        except Exception as e:
            console.log(f"[dim]Set leverage {symbol}: {e}[/dim]")

    def _fetch_top_symbols_rest(self) -> List[Dict[str, Any]]:
        """
        Mengambil Top 50 koin langsung via REST API Binance Futures (Sangat ringan <1MB).
        Menyaring token TradFi/Saham (SKHY, NVDA, dll) agar tidak memicu error -4411.
        """
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        resp = self.http_session.get(url, timeout=10)
        data = resp.json()
        
        filtered = []
        for item in data:
            sym = item.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            base = sym[:-4]
            if base in TRADFI_EXCLUSIONS:
                continue
            try:
                q_vol = float(item.get("quoteVolume", 0.0))
                filtered.append({
                    "raw_symbol": sym,
                    "ccxt_symbol": f"{base}/USDT:USDT",
                    "quoteVolume": q_vol
                })
            except Exception:
                continue
                
        filtered.sort(key=lambda x: x["quoteVolume"], reverse=True)
        return filtered[:config.TOP_COINS_LIMIT]

    def _fetch_klines_rest(self, raw_symbol: str, limit: int = 220) -> Optional[List[List[float]]]:
        """
        Mengambil candle 1m langsung dari Binance Futures REST API (Tanpa overhead CCXT).
        Format: [[time, open, high, low, close, volume], ...]
        """
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={raw_symbol}&interval={config.TIMEFRAME}&limit={limit}"
        resp = self.http_session.get(url, timeout=5)
        raw = resp.json()
        if not isinstance(raw, list) or len(raw) < config.EMA_TREND + 5:
            return None
            
        return [
            [float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
            for c in raw
        ]

    def scan_top_coins(self):
        """
        Memindai 50 koin paling likuid secara efisien menggunakan ThreadPoolExecutor.
        Penggunaan RAM stabil di ~35MB - 50MB (Jauh di bawah batas Render 512MB).
        """
        t_start = time.time()
        try:
            now = time.time()
            # 1. Perbarui daftar Top 50 koin setiap 30 menit
            if not self._cached_top_symbols or (now - self._last_top_symbols_refresh > 1800):
                self._cached_top_symbols = self._fetch_top_symbols_rest()
                self._last_top_symbols_refresh = now
                gc.collect()

            # 2. Ambil saldo akun
            bal = self.get_futures_balance()
            cap = bal['available'] if bal['available'] >= 1.0 else config.DEFAULT_CAPITAL
            
            # 3. Analisis pair secara paralel dengan 3 worker untuk kestabilan memori
            results = []
            def process_coin(rank: int, item: Dict[str, Any]):
                raw_sym = item["raw_symbol"]
                ccxt_sym = item["ccxt_symbol"]
                q_vol = item["quoteVolume"]
                try:
                    ohlcv = self._fetch_klines_rest(raw_sym, limit=config.CANDLE_LIMIT)
                    if not ohlcv:
                        return None
                        
                    sig = strategy.check_signal_from_ohlcv(ohlcv, available_capital=cap, leverage=config.LEVERAGE)
                    
                    closes = [c[4] for c in ohlcv]
                    highs = [c[2] for c in ohlcv]
                    lows = [c[3] for c in ohlcv]
                    
                    ema_trend = strategy.calculate_ema_series(closes, config.EMA_TREND)[-2]
                    rsi_val = strategy.calculate_rsi_series(closes, config.RSI_PERIOD)[-2]
                    atr_val = strategy.calculate_atr_series(highs, lows, closes, config.ATR_PERIOD)[-2]
                    latest_price = closes[-1]
                    is_bullish = closes[-2] > ema_trend
                    
                    return {
                        'rank': rank,
                        'symbol': ccxt_sym,
                        'raw_symbol': raw_sym,
                        'price': latest_price,
                        'vol_24h_m': round(q_vol / 1_000_000, 2),
                        'trend': 'BULLISH' if is_bullish else 'BEARISH',
                        'rsi': round(rsi_val, 2),
                        'atr': round(atr_val, 4),
                        'signal': sig
                    }
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_coin, i + 1, item) for i, item in enumerate(self._cached_top_symbols)]
                for f in as_completed(futures):
                    res = f.result()
                    if res:
                        results.append(res)
                        
            gc.collect()
            
            results.sort(key=lambda x: x['rank'])
            self.ranked_pairs = results
            self.bullish_count = sum(1 for r in results if r['trend'] == 'BULLISH')
            self.bearish_count = sum(1 for r in results if r['trend'] == 'BEARISH')
            
            signals = []
            for r in results:
                if r['signal'] is not None:
                    sig_data = r['signal'].copy()
                    sig_data['symbol'] = r['symbol']
                    sig_data['raw_symbol'] = r['raw_symbol']
                    sig_data['rank'] = r['rank']
                    sig_data['vol_24h_m'] = r['vol_24h_m']
                    signals.append(sig_data)
                    
            self.active_signals = sorted(signals, key=lambda x: x.get('score', 0), reverse=True)
            self.watchlist = sorted(results, key=lambda x: abs(x['rsi'] - 55.0))[:8]
            
            self.last_scan_duration_sec = round(time.time() - t_start, 2)
            self.last_scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            console.log(f"[red]Error dalam pemindaian koin: {e}[/red]")
        finally:
            gc.collect()

    def execute_limit_order(self, sig: Dict[str, Any]) -> bool:
        """Mengeksekusi Limit Order (Maker only) dengan perlindungan timeout 30 detik."""
        symbol = sig['symbol']
        side = "buy" if sig['side'] == "BUY" else "sell"
        target_price = sig['entry_price']
        
        # Perlindungan TradFi ekstra
        base = symbol.split('/')[0]
        if base in TRADFI_EXCLUSIONS:
            console.log(f"[yellow]Melewati order pada {symbol} (Aset TradFi/Saham).[/yellow]")
            return False

        try:
            self.set_margin_and_leverage(symbol)
            
            ob = self.exchange.fetch_order_book(symbol, limit=5)
            if side == "buy":
                best_price = ob['bids'][0][0] if ob['bids'] else target_price
            else:
                best_price = ob['asks'][0][0] if ob['asks'] else target_price
                
            price_prec = self.exchange.price_to_precision(symbol, best_price)
            price_float = float(price_prec)
            
            notional = sig['notional']
            raw_qty = notional / price_float
            qty_prec = self.exchange.amount_to_precision(symbol, raw_qty)
            qty_float = float(qty_prec)
            
            if qty_float <= 0:
                console.log(f"[red]Ukuran order terlalu kecil untuk {symbol}: {raw_qty}[/red]")
                return False
                
            console.log(f"[bold cyan]Dispatching Maker Limit Order: {side.upper()} {qty_float} {symbol} @ {price_float}[/bold cyan]")
            
            order = self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=qty_float,
                price=price_float,
                params={'postOnly': True}
            )
            
            order_id = order['id']
            self.active_order = {
                'id': order_id,
                'symbol': symbol,
                'side': side,
                'price': price_float,
                'qty': qty_float,
                'sl_price': sig['sl_price'],
                'tp_price': sig['tp_price'],
                'placed_at': time.time()
            }
            
            # Loop Pemantauan 30 Detik (Anti-FOMO Auto-Cancel)
            console.log(f"[yellow]Menunggu limit order terisi (maks 30 detik)...[/yellow]")
            t_start = time.time()
            while time.time() - t_start < config.LIMIT_TIMEOUT_SECONDS:
                time.sleep(2)
                try:
                    chk = self.exchange.fetch_order(order_id, symbol)
                    status = chk.get('status')
                    if status == 'closed':
                        console.log(f"[bold green]LIMIT ORDER TERISI PENUH! ({symbol} @ {price_float})[/bold green]")
                        self.active_position = {
                            'symbol': symbol,
                            'side': side,
                            'entry_price': price_float,
                            'qty': qty_float,
                            'sl_price': sig['sl_price'],
                            'tp_price': sig['tp_price'],
                            'opened_at': time.time(),
                            'notional': qty_float * price_float
                        }
                        self.active_order = None
                        return True
                    elif status in ('canceled', 'rejected'):
                        console.log(f"[yellow]Order dibatalkan/ditolak ({status}).[/yellow]")
                        self.active_order = None
                        return False
                except Exception as err:
                    console.log(f"[dim]Pengecekan order {order_id}: {err}[/dim]")
                    
            console.log(f"[bold yellow]Limit order tidak terisi dalam 30 detik. Auto-cancel {order_id} (Anti-FOMO)...[/bold yellow]")
            try:
                self.exchange.cancel_order(order_id, symbol)
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
        symbol = pos['symbol']
        side = pos['side']
        entry_price = pos['entry_price']
        qty = pos['qty']
        sl_price = pos['sl_price']
        tp_price = pos['tp_price']
        
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = float(ticker['last'])
            
            pnl_pct = ((current_price - entry_price) / entry_price) if side == 'buy' else ((entry_price - current_price) / entry_price)
            pnl_usd = pnl_pct * pos['notional']
            
            hit_tp = (current_price >= tp_price) if side == 'buy' else (current_price <= tp_price)
            hit_sl = (current_price <= sl_price) if side == 'buy' else (current_price >= sl_price)
            
            if hit_tp:
                console.log(f"[bold green]TAKE PROFIT TERCAPAI! (+{pnl_pct*100:.2f}%, PnL: +${pnl_usd:.2f}) pada {symbol}[/bold green]")
                close_side = "sell" if side == "buy" else "buy"
                self.exchange.create_order(symbol=symbol, type='market', side=close_side, amount=qty, params={'reduceOnly': True})
                
                self.trade_history.append({
                    'symbol': symbol,
                    'result': 'WIN',
                    'pnl_pct': pnl_pct * 100,
                    'pnl_usd': pnl_usd,
                    'closed_at': time.strftime("%Y-%m-%d %H:%M:%S")
                })
                self.total_trades += 1
                self.winning_trades += 1
                self.total_pnl_usd += pnl_usd
                self.active_position = None
                
            elif hit_sl:
                console.log(f"[bold red]STOP LOSS TERPICU! ({pnl_pct*100:.2f}%, PnL: ${pnl_usd:.2f}) pada {symbol}[/bold red]")
                close_side = "sell" if side == "buy" else "buy"
                self.exchange.create_order(symbol=symbol, type='market', side=close_side, amount=qty, params={'reduceOnly': True})
                
                self.trade_history.append({
                    'symbol': symbol,
                    'result': 'LOSS',
                    'pnl_pct': pnl_pct * 100,
                    'pnl_usd': pnl_usd,
                    'closed_at': time.strftime("%Y-%m-%d %H:%M:%S")
                })
                self.total_trades += 1
                self.total_pnl_usd += pnl_usd
                self.active_position = None
                
        except Exception as e:
            console.log(f"[red]Error memantau posisi aktif {symbol}: {e}[/red]")

    def run_scan_loop(self):
        """Loop pemindaian utama yang berjalan secara otonom di background."""
        console.log("[bold green]>>> Binance Scalper Autonomous Loop Dimulai <<<[/bold green]")
        self.is_running = True
        
        # Inisialisasi awal
        self._ensure_single_asset_mode()
        self.get_futures_balance(max_age_sec=0)
        self.sync_exchange_position()
        
        while self.is_running:
            try:
                # 0. Jika IP sedang dalam masa jeda rate limit, tunggu
                if time.time() < self._ban_until:
                    s_left = int(self._ban_until - time.time())
                    time.sleep(min(30, s_left + 1))
                    continue

                # 1. Selalu sinkronisasi posisi riil dari Binance setiap awal siklus
                self.sync_exchange_position()

                # 2. Jika ada posisi aktif, pantau harga secara intensif
                if self.active_position:
                    self.monitor_active_position()
                    time.sleep(3)
                    continue
                    
                # 3. Jalankan pemindaian koin Top volume (Zero memory leak)
                self.scan_top_coins()
                
                # 4. Cek saldo akun
                bal = self.get_futures_balance()
                avail_usdt = bal['available']
                
                # 5. Jika ada sinyal valid dan saldo tersedia cukup
                if self.active_signals and not self.active_order and not self.active_position:
                    best_signal = self.active_signals[0]
                    console.log(f"[bold green]Sinyal terbaik terdeteksi:[/bold green] {best_signal['side']} {best_signal['symbol']} (Skor: {best_signal.get('score', 0)})")
                    
                    if avail_usdt >= (config.MIN_NOTIONAL / config.LEVERAGE):
                        self.execute_limit_order(best_signal)
                    else:
                        console.log(f"[yellow]Saldo USDT Futures saat ini: ${avail_usdt:.2f}. Menunggu modal untuk eksekusi otomatis.[/yellow]")
                        
                time.sleep(config.SCAN_INTERVAL_SECONDS)
                
            except Exception as e:
                console.log(f"[red]Error di siklus bot scalper: {e}[/red]")
                time.sleep(10)

    def run(self):
        self.run_scan_loop()

import os
import time
import math
import asyncio
import threading
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import ccxt
import ccxt.async_support as ccxt_async
from rich.console import Console

from config import config
import strategy

console = Console()

class BinanceScalper:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.is_testnet = config.IS_TESTNET
        
        # CCXT Client Sinkron (untuk balance, order, dan posisi)
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
                'warnOnFetchOpenOrdersWithoutSymbol': False
            }
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
        
        # Balance cache
        self._cached_balance: Dict[str, float] = {"total_wallet": 0.0, "available": 0.0, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self.last_error: Optional[str] = None
        
        # Inisialisasi awal
        self._ensure_single_asset_mode()

    def _ensure_single_asset_mode(self):
        """Memastikan mode Multi-Assets dimatikan agar ISOLATED margin dapat digunakan."""
        try:
            res = self.exchange.fapiPrivateGetMultiAssetsMargin()
            if res.get('multiAssetsMargin') is True:
                console.log("[yellow]Mengubah akun ke Single-Asset Margin Mode untuk ISOLATED margin...[/yellow]")
                self.exchange.fapiPrivatePostMultiAssetsMargin({'multiAssetsMargin': 'false'})
                console.log("[green]Single-Asset Mode berhasil diaktifkan.[/green]")
        except Exception as e:
            console.log(f"[dim]Cek MultiAssetsMargin: {e}[/dim]")

    def get_futures_balance(self, max_age_sec: float = 5.0) -> Dict[str, float]:
        """Mengambil saldo wallet USDⓈ-M Futures dengan caching 5 detik."""
        now = time.time()
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
            return self._cached_balance
        except Exception as e:
            self.last_error = f"Balance error: {str(e)}"
            console.log(f"[red]Error mengambil balance Futures: {e}[/red]")
            return self._cached_balance

    def get_compounded_notional(self) -> float:
        """
        Menghitung ukuran order berikutnya (Compounding 100%).
        Jika saldo tersedia >= $1, gunakan 100% saldo * leverage.
        Jika saldo belum ada ($0), gunakan baseline konfigurasi ($10 * leverage = $50 notional).
        """
        bal = self.get_futures_balance()
        avail = bal["available"]
        if avail >= 1.0:
            return round(avail * config.LEVERAGE, 2)
        return round(config.DEFAULT_CAPITAL * config.LEVERAGE, 2)

    def set_margin_and_leverage(self, symbol: str):
        """Mengatur margin ke ISOLATED dan leverage sesuai konfigurasi."""
        try:
            self.exchange.set_margin_mode('ISOLATED', symbol)
        except Exception:
            pass
            
        try:
            self.exchange.set_leverage(config.LEVERAGE, symbol)
        except Exception as e:
            console.log(f"[dim]Set leverage {symbol}: {e}[/dim]")

    async def scan_top_200_async(self):
        """Memindai 200 koin volume teratas di Binance Futures secara asinkron."""
        t_start = time.time()
        client = ccxt_async.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
                'fetchCurrencies': False
            }
        })
        
        try:
            tickers = await client.fetch_tickers()
            usdt_tickers = {
                s: t for s, t in tickers.items()
                if s.endswith('/USDT:USDT') and t.get('quoteVolume') is not None
            }
            sorted_pairs = sorted(usdt_tickers.items(), key=lambda x: x[1]['quoteVolume'], reverse=True)[:config.TOP_COINS_LIMIT]
            
            # Ambil saldo satu kali sebelum looping
            bal = self.get_futures_balance()
            cap = bal['available'] if bal['available'] >= 1.0 else config.DEFAULT_CAPITAL
            
            sem = asyncio.Semaphore(20)
            async def analyze_pair(rank: int, symbol: str, ticker: Dict[str, Any]):
                async with sem:
                    try:
                        ohlcv = await client.fetch_ohlcv(symbol, timeframe=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
                        if not ohlcv or len(ohlcv) < config.EMA_TREND + 5:
                            return None
                        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                        df = strategy.prepare_indicators(df)
                        
                        sig = strategy.check_signal(df, available_capital=cap, leverage=config.LEVERAGE)
                        
                        c_curr = df.iloc[-2]
                        latest_price = float(df['close'].iloc[-1])
                        is_bullish = c_curr['close'] > c_curr['ema_trend']
                        rsi_val = float(c_curr['rsi'])
                        atr_val = float(c_curr['atr']) if not np.isnan(c_curr['atr']) else (latest_price * 0.002)
                        
                        result = {
                            'rank': rank,
                            'symbol': symbol,
                            'price': latest_price,
                            'vol_24h_m': round(ticker['quoteVolume'] / 1_000_000, 2),
                            'trend': 'BULLISH' if is_bullish else 'BEARISH',
                            'rsi': round(rsi_val, 2),
                            'atr': round(atr_val, 4),
                            'signal': sig
                        }
                        return result
                    except Exception:
                        return None
                    except Exception:
                        return None
                        
            tasks = [analyze_pair(i + 1, s, t) for i, (s, t) in enumerate(sorted_pairs)]
            results = await asyncio.gather(*tasks)
            valid = [r for r in results if r is not None]
            
            self.ranked_pairs = valid
            self.bullish_count = sum(1 for r in valid if r['trend'] == 'BULLISH')
            self.bearish_count = sum(1 for r in valid if r['trend'] == 'BEARISH')
            
            signals = []
            for r in valid:
                if r['signal'] is not None:
                    sig_data = r['signal'].copy()
                    sig_data['symbol'] = r['symbol']
                    sig_data['rank'] = r['rank']
                    sig_data['vol_24h_m'] = r['vol_24h_m']
                    signals.append(sig_data)
                    
            self.active_signals = sorted(signals, key=lambda x: x.get('score', 0), reverse=True)
            
            # Watchlist: koin yang mendekati momentum optimal (RSI mendekati 55)
            self.watchlist = sorted(valid, key=lambda x: abs(x['rsi'] - 55.0))[:8]
            
            self.last_scan_duration_sec = round(time.time() - t_start, 2)
            self.last_scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            console.log(f"[red]Error dalam pemindaian asinkron Top 200: {e}[/red]")
        finally:
            await client.close()

    def execute_limit_order(self, sig: Dict[str, Any]) -> bool:
        """
        Mengeksekusi Limit Order (Maker only) dengan perlindungan timeout 30 detik.
        """
        symbol = sig['symbol']
        side = "buy" if sig['side'] == "BUY" else "sell"
        target_price = sig['entry_price']
        
        try:
            # 1. Pastikan Margin ISOLATED dan Leverage
            self.set_margin_and_leverage(symbol)
            
            # 2. Ambil order book untuk harga terbaik Maker
            ob = self.exchange.fetch_order_book(symbol, limit=5)
            if side == "buy":
                # Limit buy pada best bid agar bertindak sebagai Maker
                best_price = ob['bids'][0][0] if ob['bids'] else target_price
            else:
                # Limit sell pada best ask agar bertindak sebagai Maker
                best_price = ob['asks'][0][0] if ob['asks'] else target_price
                
            price_prec = self.exchange.price_to_precision(symbol, best_price)
            price_float = float(price_prec)
            
            # 3. Hitung qty sesuai precision
            notional = sig['notional']
            raw_qty = notional / price_float
            qty_prec = self.exchange.amount_to_precision(symbol, raw_qty)
            qty_float = float(qty_prec)
            
            if qty_float <= 0:
                console.log(f"[red]Ukuran order terlalu kecil untuk {symbol}: {raw_qty}[/red]")
                return False
                
            console.log(f"[bold cyan]Dispatching Maker Limit Order: {side.upper()} {qty_float} {symbol} @ {price_float}[/bold cyan]")
            
            # 4. Kirim LIMIT order
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
            
            # 5. Loop Pemantauan 30 Detik (Anti-FOMO Auto-Cancel)
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
                    elif status == 'canceled' or status == 'rejected':
                        console.log(f"[yellow]Order dibatalkan/ditolak oleh sistem ({status}).[/yellow]")
                        self.active_order = None
                        return False
                except Exception as err:
                    console.log(f"[dim]Pengecekan order {order_id}: {err}[/dim]")
                    
            # Jika belum terisi setelah 30 detik -> AUTO-CANCEL
            console.log(f"[bold yellow]Limit order tidak terisi dalam 30 detik. Membatalkan order {order_id} (Anti-FOMO)...[/bold yellow]")
            try:
                self.exchange.cancel_order(order_id, symbol)
            except Exception as e:
                console.log(f"[dim]Gagal cancel order {order_id}: {e}[/dim]")
                
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
            
            # Cek TAKE PROFIT (+1.0%)
            hit_tp = (current_price >= tp_price) if side == 'buy' else (current_price <= tp_price)
            # Cek STOP LOSS (-0.5%)
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
        
        while self.is_running:
            try:
                # 1. Jika ada posisi aktif, pantau terlebih dahulu
                if self.active_position:
                    self.monitor_active_position()
                    time.sleep(3)
                    continue
                    
                # 2. Jalankan pemindaian Top 200 koin
                asyncio.run(self.scan_top_200_async())
                
                # 3. Cek saldo akun
                bal = self.get_futures_balance()
                avail_usdt = bal['available']
                
                # 4. Jika ada sinyal valid dan saldo tersedia >= syarat order
                if self.active_signals and not self.active_order and not self.active_position:
                    best_signal = self.active_signals[0]
                    console.log(f"[bold green]Sinyal terbaik terdeteksi:[/bold green] {best_signal['side']} {best_signal['symbol']} (Skor: {best_signal.get('score', 0)})")
                    
                    if avail_usdt >= (config.MIN_NOTIONAL / config.LEVERAGE):
                        self.execute_limit_order(best_signal)
                    else:
                        console.log(f"[yellow]Saldo USDT Futures saat ini: ${avail_usdt:.2f}. Menunggu penambahan saldo/transfer untuk eksekusi otomatis.[/yellow]")
                        
                time.sleep(config.SCAN_INTERVAL_SECONDS)
                
            except Exception as e:
                console.log(f"[red]Error di siklus bot scalper: {e}[/red]")
                time.sleep(10)

    def run(self):
        self.run_scan_loop()

import os
import sys
import time
import math
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import ccxt

from config import config
from strategy import prepare_indicators, check_signal

load_dotenv()
console = Console()

class AlpacaScalper:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID", "PK72AJFKXDUN662G24JW4PP7WS")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY", "HChT8VunCtNo2kvcttyYrCr7wQBTuuGoS1TxFuNpftep")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/v2").rstrip('/')
        
        # Current active trading state
        self.current_symbol = "BTC/USD"
        self.active_order_id = None
        self.order_placed_time = None
        
        # CCXT feed untuk data kline super cepat & real-time
        self.feed_exchange = ccxt.binance({'enableRateLimit': True})
        
        # Header Alpaca
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Watchlist & Ranking Data
        self.ranked_pairs = []
        self.last_ranking_refresh = 0

    def verify_account(self) -> dict:
        """Mengambil data akun resmi Alpaca."""
        url = f"{self.base_url}/account"
        res = requests.get(url, headers=self.headers, timeout=10)
        if res.status_code != 200:
            raise Exception(f"Gagal otentikasi ke Alpaca ({res.status_code}): {res.text}")
        return res.json()

    def get_alpaca_positions(self) -> list:
        """Mengecek posisi terbuka di Alpaca."""
        url = f"{self.base_url}/positions"
        res = requests.get(url, headers=self.headers, timeout=10)
        return res.json() if res.status_code == 200 else []

    def get_alpaca_orders(self) -> list:
        """Mengecek open order yang sedang antre di Alpaca."""
        url = f"{self.base_url}/orders?status=open"
        res = requests.get(url, headers=self.headers, timeout=10)
        return res.json() if res.status_code == 200 else []

    def cancel_order(self, order_id: str):
        """Membatalkan limit order."""
        url = f"{self.base_url}/orders/{order_id}"
        requests.delete(url, headers=self.headers, timeout=10)

    def get_best_bid_ask(self, symbol: str):
        """Mengambil harga pasar bid & ask terbaik dari Alpaca untuk koin tertentu."""
        try:
            url = f"https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols={symbol}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                quote = res.json().get('quotes', {}).get(symbol, {})
                return float(quote.get('bp', 0)), float(quote.get('ap', 0))
        except Exception:
            pass
        return None, None

    def refresh_top_rankings(self):
        """
        Mengambil semua koin kripto di Alpaca dan menyusun urutan ranking
        berdasarkan Volume Perdagangan 24 jam di pasar global (Binance feed).
        Mengecualikan stablecoin (USDT, USDC, USDG, PAXG).
        """
        now = time.time()
        if self.ranked_pairs and (now - self.last_ranking_refresh < 3600):
            return  # Refresh setiap 1 jam

        console.print("[cyan]Menyusun daftar ranking koin/token teratas dari bursa...[/cyan]")
        try:
            # 1. Ambil semua aset crypto aktif dari Alpaca
            url = f"{self.base_url}/assets?asset_class=crypto&status=active"
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return

            stablecoins = {'USDT/USD', 'USDC/USD', 'USDG/USD', 'PAXG/USD'}
            al_pairs = [
                a['symbol'] for a in res.json()
                if a.get('tradable') and a['symbol'].endswith('/USD') and a['symbol'] not in stablecoins
            ]

            # 2. Cek ketersediaan di Binance feed untuk kline cepat
            bi_markets = self.feed_exchange.load_markets()
            matched = []
            feed_symbols = []
            for al in al_pairs:
                bi_sym = al.replace('/USD', '/USDT')
                if bi_sym in bi_markets:
                    matched.append((al, bi_sym))
                    feed_symbols.append(bi_sym)

            # 3. Urutkan berdasarkan Volume 24 Jam (Ranking Tertinggi)
            tickers = self.feed_exchange.fetch_tickers(feed_symbols)
            sorted_matched = sorted(
                matched,
                key=lambda x: tickers.get(x[1], {}).get('quoteVolume', 0) if tickers.get(x[1]) else 0,
                reverse=True
            )

            self.ranked_pairs = sorted_matched
            self.last_ranking_refresh = now
            top_5 = [p[0] for p in self.ranked_pairs[:5]]
            console.print(f"[bold green]Ranking Disusun: {len(self.ranked_pairs)} koin teratas aktif dipantau![/bold green] Top 5: {', '.join(top_5)}")

        except Exception as e:
            console.print(f"[red]Gagal menyusun ranking: {e}[/red]")
            if not self.ranked_pairs:
                self.ranked_pairs = [('BTC/USD', 'BTC/USDT'), ('ETH/USD', 'ETH/USDT'), ('SOL/USD', 'SOL/USDT')]

    def fetch_market_candles(self, feed_symbol: str) -> pd.DataFrame:
        """Mengambil candle 1-menit untuk kalkulasi indikator."""
        ohlcv = self.feed_exchange.fetch_ohlcv(feed_symbol, timeframe=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return prepare_indicators(df)

    def calculate_order_qty(self, price: float, notional: float = 10.05) -> str:
        """Menghitung jumlah koin dengan presisi yang tepat untuk memenuhi minimal $10.00."""
        raw_qty = notional / price
        if price > 1000:
            return f"{math.ceil(raw_qty * 1e7) / 1e7:.7f}"
        elif price > 10:
            return f"{math.ceil(raw_qty * 1e4) / 1e4:.4f}"
        elif price > 1:
            return f"{math.ceil(raw_qty * 1e2) / 1e2:.2f}"
        else:
            return str(int(math.ceil(raw_qty)))

    def place_limit_buy(self, symbol: str, price: float, notional: float = 10.05) -> dict:
        """Memasang LIMIT BUY ORDER di Alpaca."""
        qty_str = self.calculate_order_qty(price, notional)
        payload = {
            "symbol": symbol,
            "qty": qty_str,
            "side": "buy",
            "type": "limit",
            "time_in_force": "gtc",
            "limit_price": str(round(price, 4) if price < 1 else round(price, 2))
        }
        url = f"{self.base_url}/orders"
        res = requests.post(url, headers=self.headers, json=payload, timeout=10)
        if res.status_code not in (200, 201):
            raise Exception(f"Order Gagal ({res.status_code}): {res.text}")
        return res.json()

    def place_limit_sell(self, symbol: str, qty: float, price: float) -> dict:
        """Memasang LIMIT SELL ORDER untuk Take Profit atau Stop Loss."""
        payload = {
            "symbol": symbol,
            "qty": str(qty),
            "side": "sell",
            "type": "limit",
            "time_in_force": "gtc",
            "limit_price": str(round(price, 4) if price < 1 else round(price, 2))
        }
        url = f"{self.base_url}/orders"
        res = requests.post(url, headers=self.headers, json=payload, timeout=10)
        return res.json() if res.status_code in (200, 201) else None

    def run(self):
        console.print("\n[bold cyan]Menghubungkan ke Alpaca Paper API...[/bold cyan]")
        try:
            account = self.verify_account()
        except Exception as e:
            console.print(f"[bold red]Gagal terhubung ke Alpaca: {e}[/bold red]")
            return

        acc_table = Table(title="Informasi Akun Alpaca Paper (Terverifikasi)")
        acc_table.add_column("Parameter", style="cyan")
        acc_table.add_column("Nilai", style="bold green")
        acc_table.add_row("Nomor Akun", account.get("account_number", "-"))
        acc_table.add_row("Status Akun", account.get("status", "-"))
        acc_table.add_row("Cash / Modal", f"${float(account.get('cash', 0)):.2f}")
        acc_table.add_row("Portfolio Value", f"${float(account.get('portfolio_value', 0)):.2f}")
        acc_table.add_row("Mode Scanner", "MULTI-COIN TOP RANKED SCANNER (30+ KOIN)")
        console.print(acc_table)

        self.refresh_top_rankings()

        console.print("\n[bold yellow]Memulai Siklus Analisis Multi-Asset Real-time... (CTRL+C untuk berhenti)[/bold yellow]\n")

        while True:
            try:
                self.refresh_top_rankings()

                # A. Cek Timeout Limit Order yang Menggantung
                if self.active_order_id and self.order_placed_time:
                    elapsed = time.time() - self.order_placed_time
                    if elapsed > config.LIMIT_TIMEOUT_SECONDS:
                        console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [yellow]Limit order {self.active_order_id[:8]} melewati 30s. Membatalkan dari Alpaca...[/yellow]")
                        self.cancel_order(self.active_order_id)
                        self.active_order_id = None
                        self.order_placed_time = None
                        console.print("[green]Order berhasil dibatalkan dari Alpaca.[/green]")

                # B. Cek Posisi Terbuka di Alpaca
                positions = self.get_alpaca_positions()
                if positions:
                    pos = positions[0]  # Fokus mengawal 1 posisi terisolasi $10
                    pos_sym = pos.get("symbol", "")
                    # Format ulang simbol jika tanpa slash (e.g. BTCUSD -> BTC/USD)
                    matched_alpaca_sym = next((p[0] for p in self.ranked_pairs if p[0].replace('/', '') == pos_sym), f"{pos_sym[:3]}/{pos_sym[3:]}")
                    
                    qty = float(pos.get("qty", 0))
                    entry_price = float(pos.get("avg_entry_price", 0))
                    
                    # Harga live real-time
                    best_bid, _ = self.get_best_bid_ask(matched_alpaca_sym)
                    current_price = best_bid if best_bid else float(pos.get("current_price", 0))
                    
                    pl_pct = ((current_price - entry_price) / entry_price) * 100
                    unrealized_pl = qty * (current_price - entry_price)

                    open_orders = self.get_alpaca_orders()
                    has_active_sell = any(o.get("side") == "sell" for o in open_orders)

                    # Target TP (+1.0%) & SL (-0.5%)
                    if pl_pct >= 1.0 and not has_active_sell:
                        console.print(f"[bold green]TARGET PROFIT TERCAPAI ({matched_alpaca_sym}: +{pl_pct:.2f}%)! Mengirim Limit Sell ke Alpaca @ ${current_price:,.2f}...[/bold green]")
                        self.place_limit_sell(matched_alpaca_sym, qty, current_price)
                    elif pl_pct <= -0.5 and not has_active_sell:
                        console.print(f"[bold red]STOP LOSS TERKENA ({matched_alpaca_sym}: {pl_pct:.2f}%)! Mengirim Limit Sell proteksi ke Alpaca @ ${current_price:,.2f}...[/bold red]")
                        self.place_limit_sell(matched_alpaca_sym, qty, current_price)
                    else:
                        console.print(
                            f"[{datetime.now().strftime('%H:%M:%S')}] [cyan]MENGAWAL POSISI AKTIF:[/cyan] "
                            f"{qty} {matched_alpaca_sym} @ ${entry_price:,.2f} | "
                            f"Harga Realtime: ${current_price:,.2f} | "
                            f"PnL: [{'green' if unrealized_pl >= 0 else 'red'}]${unrealized_pl:+.4f} ({pl_pct:+.2f}%)[/]"
                        )
                    
                    time.sleep(5)
                    continue

                # C. Cek Open Order Beli yang Sedang Antre
                open_orders = self.get_alpaca_orders()
                if open_orders:
                    o = open_orders[0]
                    self.active_order_id = o.get("id")
                    console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [yellow]Menunggu eksekusi Limit Buy: {o.get('symbol')} {o.get('qty')} @ ${float(o.get('limit_price', 0)):,.2f}...[/yellow]")
                    time.sleep(5)
                    continue
                else:
                    self.active_order_id = None

                # D. JIKA TIDAK ADA POSISI: SCAN SELURUH KOIN PERINGKAT TERATAS
                console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [dim]Scanning sinyal scalping di antara {len(self.ranked_pairs)} koin peringkat teratas...[/dim]")
                found_signal = False

                for rank, (al_sym, bi_sym) in enumerate(self.ranked_pairs, start=1):
                    try:
                        df = self.fetch_market_candles(bi_sym)
                        if len(df) < config.EMA_TREND + 5:
                            continue

                        c_prev = df.iloc[-3]
                        c_curr = df.iloc[-2]
                        latest_price = float(df['close'].iloc[-1])
                        
                        golden_cross = (c_prev['ema_fast'] <= c_prev['ema_slow']) and (c_curr['ema_fast'] > c_curr['ema_slow'])
                        is_bullish_trend = c_curr['close'] > c_curr['ema_trend']
                        rsi = float(c_curr['rsi'])

                        # Syarat Sinyal Valid
                        if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi <= config.RSI_LONG_MAX):
                            console.print(f"\n[bold green]>>> SINYAL VALID DITEMUKAN PADA RANK #{rank} ({al_sym})! <<<[/bold green]")
                            console.print(f"Harga: ${latest_price} | RSI: {rsi:.1f} | EMA Trend: {c_curr['ema_trend']:.2f}")

                            best_bid, _ = self.get_best_bid_ask(al_sym)
                            limit_p = best_bid if best_bid else latest_price

                            console.print(f"[cyan]Mengirim LIMIT BUY ORDER $10 ke Alpaca untuk {al_sym} @ ${limit_p:,.2f}...[/cyan]")
                            order = self.place_limit_buy(al_sym, price=limit_p, notional=10.05)
                            self.active_order_id = order.get("id")
                            self.order_placed_time = time.time()
                            self.current_symbol = al_sym
                            console.print(f"[bold green]LIMIT ORDER MASUK KE ALPACA![/bold green] ID: {self.active_order_id}\n")
                            found_signal = True
                            break

                    except Exception as err:
                        continue

                time.sleep(10)  # Polling antar scan siklus 10 detik

            except KeyboardInterrupt:
                console.print("\n[bold red]Bot dihentikan oleh pengguna (CTRL+C).[/bold red]")
                break
            except Exception as e:
                console.print(f"[red]Error loop: {e}[/red]")
                time.sleep(5)

if __name__ == "__main__":
    scalper = AlpacaScalper()
    scalper.run()

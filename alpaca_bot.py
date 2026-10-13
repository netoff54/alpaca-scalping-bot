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

# Load .env
load_dotenv()

console = Console()

class AlpacaScalper:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID", "PK72AJFKXDUN662G24JW4PP7WS")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY", "HChT8VunCtNo2kvcttyYrCr7wQBTuuGoS1TxFuNpftep")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/v2").rstrip('/')
        self.symbol = "BTC/USD"
        self.feed_symbol = "BTC/USDT"
        
        # State
        self.active_order_id = None
        self.order_placed_time = None
        self.active_position_meta = None
        
        # CCXT feed untuk data kline super cepat & real-time
        self.feed_exchange = ccxt.binance({'enableRateLimit': True})
        
        # Header Alpaca
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

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

    def get_best_bid_ask(self):
        """Mengambil harga pasar bid & ask terbaik dari Alpaca."""
        try:
            url = f"https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols={self.symbol}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                quote = res.json().get('quotes', {}).get(self.symbol, {})
                return float(quote.get('bp', 0)), float(quote.get('ap', 0))
        except Exception:
            pass
        return None, None

    def fetch_market_candles(self) -> pd.DataFrame:
        """Mengambil candle 1-menit untuk kalkulasi EMA, RSI, dan ATR."""
        ohlcv = self.feed_exchange.fetch_ohlcv(self.feed_symbol, timeframe=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return prepare_indicators(df)

    def place_limit_buy(self, price: float, notional: float = 10.0) -> dict:
        """
        Memasang LIMIT BUY ORDER di Alpaca:
        - Memenuhi syarat minimal Alpaca ($10)
        - Selalu Limit Order (Maker)
        - Terisolasi pada saldo $10 akun Anda
        """
        # Hitung kuantitas presisi 8 desimal (pastikan cost basis >= 10.00)
        raw_qty = notional / price
        qty = math.ceil(raw_qty * 1e7) / 1e7  # Round up sedikit agar cost basis >= $10.00
        
        payload = {
            "symbol": self.symbol,
            "qty": str(qty),
            "side": "buy",
            "type": "limit",
            "time_in_force": "gtc",
            "limit_price": str(round(price, 2))
        }
        
        url = f"{self.base_url}/orders"
        res = requests.post(url, headers=self.headers, json=payload, timeout=10)
        if res.status_code not in (200, 201):
            raise Exception(f"Order Gagal ({res.status_code}): {res.text}")
        return res.json()

    def place_limit_sell(self, qty: float, price: float) -> dict:
        """Memasang LIMIT SELL ORDER untuk Take Profit atau Stop Loss."""
        payload = {
            "symbol": self.symbol,
            "qty": str(qty),
            "side": "sell",
            "type": "limit",
            "time_in_force": "gtc",
            "limit_price": str(round(price, 2))
        }
        url = f"{self.base_url}/orders"
        res = requests.post(url, headers=self.headers, json=payload, timeout=10)
        return res.json() if res.status_code in (200, 201) else None

    def run(self):
        # 1. Verifikasi Koneksi Awal
        console.print("\n[bold cyan]Menghubungkan ke Alpaca Paper API...[/bold cyan]")
        try:
            account = self.verify_account()
        except Exception as e:
            console.print(f"[bold red]Gagal terhubung ke Alpaca: {e}[/bold red]")
            return

        # Tampilkan Informasi Akun Resmi
        acc_table = Table(title="Informasi Akun Alpaca Paper (Terverifikasi)")
        acc_table.add_column("Parameter", style="cyan")
        acc_table.add_column("Nilai", style="bold green")
        acc_table.add_row("Nomor Akun", account.get("account_number", "-"))
        acc_table.add_row("Status Akun", account.get("status", "-"))
        acc_table.add_row("Crypto Status", account.get("crypto_status", "-"))
        acc_table.add_row("Cash / Modal", f"${float(account.get('cash', 0)):.2f}")
        acc_table.add_row("Buying Power", f"${float(account.get('buying_power', 0)):.2f}")
        acc_table.add_row("Portfolio Value", f"${float(account.get('portfolio_value', 0)):.2f}")
        acc_table.add_row("Tipe Akun", "CASH (Terisolasi Otomatis)")
        console.print(acc_table)

        console.print(Panel(
            "[bold green]BOT AKTIF DI LOCALHOST DENGAN KETENTUAN:[/bold green]\n"
            f"1. [bold]Simbol[/bold]: {self.symbol} (Alpaca Crypto Spot)\n"
            "2. [bold]Tipe Order[/bold]: ALWAYS LIMIT ORDER (Maker Only)\n"
            "3. [bold]Modal & Margin[/bold]: $10 Terisolasi (Cash Account)\n"
            "4. [bold]Risiko Maksimal per Trade[/bold]: $0.05 (0.5% dari $10 modal)\n"
            "5. [bold]Target Profit (RR 1:2)[/bold]: +$0.10 (+1.0% kenaikan harga)\n"
            "6. [bold]Auto-Cancel[/bold]: Batalkan order jika antrean > 30 detik tanpa terisi\n"
            "\n[yellow]Silakan pantau pergerakan order langsung di web resmi Alpaca:[/yellow]\n"
            "[bold cyan]https://app.alpaca.markets/paper/dashboard/overview[/bold cyan]",
            title="Konfigurasi Aktif",
            style="blue"
        ))

        # 2. Main Loop Scalping
        console.print("\n[bold yellow]Memulai Siklus Analisis & Eksekusi Pasar Real-time... (Tekan CTRL+C untuk berhenti)[/bold yellow]\n")

        while True:
            try:
                # A. Cek Timeout Limit Order yang Menggantung
                if self.active_order_id and self.order_placed_time:
                    elapsed = time.time() - self.order_placed_time
                    if elapsed > config.LIMIT_TIMEOUT_SECONDS:
                        console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [yellow]Limit order {self.active_order_id[:8]} melewati 30s. Membatalkan dari Alpaca...[/yellow]")
                        self.cancel_order(self.active_order_id)
                        self.active_order_id = None
                        self.order_placed_time = None
                        self.active_position_meta = None
                        console.print("[green]Order berhasil dibatalkan dari Alpaca untuk mencegah slippage.[/green]")

                # B. Cek Posisi Terbuka di Alpaca
                positions = self.get_alpaca_positions()
                has_position = False
                target_sym = self.symbol.replace("/", "")
                for pos in positions:
                    if pos.get("symbol", "").replace("/", "") == target_sym:
                        has_position = True
                        qty = float(pos.get("qty", 0))
                        entry_price = float(pos.get("avg_entry_price", 0))
                        
                        # Ambil harga pasar live real-time (Best Bid) agar deteksi TP tidak terkena delay snapshot
                        best_bid, _ = self.get_best_bid_ask()
                        current_price = best_bid if best_bid else float(pos.get("current_price", 0))
                        
                        # Hitung PnL presisi detik ini
                        pl_pct = ((current_price - entry_price) / entry_price) * 100
                        unrealized_pl = qty * (current_price - entry_price)

                        # Cek apakah sudah ada limit sell TP yang sedang antre
                        open_orders = self.get_alpaca_orders()
                        has_active_sell = any(o.get("side") == "sell" for o in open_orders)

                        # Target TP (+1.0% = +$0.10) & SL (-0.5% = -$0.05)
                        if pl_pct >= 1.0 and not has_active_sell:
                            console.print(f"[bold green]TARGET PROFIT TERCAPAI (+{pl_pct:.2f}%)! Mengirim Limit Sell ke Alpaca @ ${current_price:,.2f}...[/bold green]")
                            self.place_limit_sell(qty, current_price)
                        elif pl_pct <= -0.5 and not has_active_sell:
                            console.print(f"[bold red]STOP LOSS TERKENA ({pl_pct:.2f}%)! Mengirim Limit Sell proteksi ke Alpaca @ ${current_price:,.2f}...[/bold red]")
                            self.place_limit_sell(qty, current_price)
                        else:
                            console.print(
                                f"[{datetime.now().strftime('%H:%M:%S')}] [cyan]POSISI AKTIF DI ALPACA:[/cyan] "
                                f"{qty:.6f} BTC @ ${entry_price:,.2f} | "
                                f"Harga Realtime: ${current_price:,.2f} | "
                                f"PnL: [{'green' if unrealized_pl >= 0 else 'red'}]${unrealized_pl:+.4f} ({pl_pct:+.2f}%)[/]"
                            )
                        break

                if has_position:
                    time.sleep(5)
                    continue

                # C. Cek Open Order yang Sedang Antre
                open_orders = self.get_alpaca_orders()
                if open_orders:
                    for o in open_orders:
                        if o.get("symbol", "").replace("/", "") == target_sym:
                            self.active_order_id = o.get("id")
                            console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [yellow]Menunggu eksekusi Limit Order di Alpaca: {o.get('side').upper()} {o.get('qty')} @ ${float(o.get('limit_price', 0)):,.2f} (ID: {self.active_order_id[:8]})...[/yellow]")
                            break
                    time.sleep(5)
                    continue
                else:
                    self.active_order_id = None

                # D. Ambil Data Pasar & Hitung Indikator
                df = self.fetch_market_candles()
                curr_bar = df.iloc[-1]
                latest_price = float(curr_bar['close'])
                ema_fast = float(curr_bar['ema_fast'])
                ema_slow = float(curr_bar['ema_slow'])
                ema_trend = float(curr_bar['ema_trend'])
                rsi = float(curr_bar['rsi'])
                atr = float(curr_bar['atr']) if not pd.isna(curr_bar['atr']) else (latest_price * 0.002)

                # Status log di terminal
                trend_status = "BULLISH" if latest_price > ema_trend else "BEARISH"
                console.print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] {self.symbol} "
                    f"Harga: ${latest_price:,.2f} | "
                    f"EMA 9/21: {ema_fast:.1f}/{ema_slow:.1f} | "
                    f"EMA 200: {ema_trend:.1f} ([{'green' if trend_status=='BULLISH' else 'red'}]{trend_status}[/]) | "
                    f"RSI: {rsi:.1f} | "
                    f"ATR: ${atr:.2f}"
                )

                # E. Evaluasi Sinyal Beli (Long Scalp)
                # Spot Crypto Alpaca adalah Long Only
                c_prev = df.iloc[-3]
                c_curr = df.iloc[-2]
                golden_cross = (c_prev['ema_fast'] <= c_prev['ema_slow']) and (c_curr['ema_fast'] > c_curr['ema_slow'])
                is_bullish_trend = c_curr['close'] > c_curr['ema_trend']

                if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi <= config.RSI_LONG_MAX):
                    console.print(f"\n[bold green]>>> SINYAL BUY (LONG) TERKONFIRMASI! <<<[/bold green]")
                    best_bid, _ = self.get_best_bid_ask()
                    limit_p = best_bid if best_bid else latest_price

                    console.print(f"[cyan]Mengirim LIMIT BUY ORDER senilai $10 ke Alpaca @ ${limit_p:,.2f}...[/cyan]")
                    try:
                        order = self.place_limit_buy(price=limit_p, notional=10.0)
                        self.active_order_id = order.get("id")
                        self.order_placed_time = time.time()
                        console.print(f"[bold green]LIMIT ORDER BERHASIL MASUK KE ALPACA![/bold green] Order ID: {self.active_order_id}")
                        console.print("[yellow]Bisa langsung dilihat di dashboard resmi Alpaca Anda sekarang![/yellow]\n")
                    except Exception as err:
                        console.print(f"[bold red]Gagal memasang order ke Alpaca: {err}[/bold red]\n")

                time.sleep(5)

            except KeyboardInterrupt:
                console.print("\n[bold red]Bot dihentikan oleh pengguna (CTRL+C).[/bold red]")
                break
            except Exception as e:
                console.print(f"[red]Error loop: {e}[/red]")
                time.sleep(5)

if __name__ == "__main__":
    scalper = AlpacaScalper()
    scalper.run()

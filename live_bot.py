import time
import os
import ccxt
import pandas as pd
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from config import config
from strategy import prepare_indicators, check_signal

console = Console()

class ScalpingBot:
    def __init__(self):
        self.exchange_id = config.EXCHANGE_ID
        self.symbol = config.SYMBOL
        self.timeframe = config.TIMEFRAME
        self.active_order_id = None
        self.order_placed_time = None
        self.active_position = None

        # Inisialisasi CCXT
        exchange_class = getattr(ccxt, self.exchange_id)
        self.exchange = exchange_class({
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Wajib future untuk perpetual & leverage
            }
        })

        if config.IS_TESTNET:
            self.exchange.set_sandbox_mode(True)
            console.print("[yellow]Mode Sandbox / Testnet: AKTIF[/yellow]")

    def setup_account(self):
        """Memastikan Margin Mode ISOLATED dan Leverage sesuai konfigurasi."""
        try:
            console.print(f"[cyan]Mengatur margin mode ke {config.MARGIN_MODE} untuk {self.symbol}...[/cyan]")
            # Atur Margin Mode ke ISOLATED
            try:
                self.exchange.set_margin_mode(config.MARGIN_MODE, self.symbol)
                console.print(f"[bold green]Margin Mode berhasil diset ke: {config.MARGIN_MODE}[/bold green]")
            except Exception as e:
                # Beberapa exchange error jika mode sudah 'ISOLATED' sebelumnya
                console.print(f"[yellow]Pemberitahuan Margin Mode: {e}[/yellow]")

            # Atur Leverage
            try:
                self.exchange.set_leverage(config.LEVERAGE, self.symbol)
                console.print(f"[bold green]Leverage berhasil diset ke: {config.LEVERAGE}x (Terisolasi)[/bold green]")
            except Exception as e:
                console.print(f"[yellow]Pemberitahuan Leverage: {e}[/yellow]")

        except Exception as e:
            console.print(f"[red]Gagal setup akun: {e}[/red]")

    def fetch_market_data(self) -> pd.DataFrame:
        """Mengambil data candle OHLCV terbaru."""
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=config.CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        return prepare_indicators(df)

    def get_best_bid_ask(self):
        """Mengambil harga bid dan ask terbaik untuk order maker."""
        orderbook = self.exchange.fetch_order_book(self.symbol, limit=5)
        best_bid = orderbook['bids'][0][0] if orderbook['bids'] else None
        best_ask = orderbook['asks'][0][0] if orderbook['asks'] else None
        return best_bid, best_ask

    def check_active_positions(self):
        """Memeriksa apakah ada posisi terbuka di bursa."""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                contracts = float(pos.get('contracts', 0) or 0)
                if contracts > 0:
                    return pos
            return None
        except Exception as e:
            console.print(f"[red]Error memeriksa posisi: {e}[/red]")
            return None

    def cancel_stale_limit_order(self):
        """Membatalkan limit order jika tidak terisi dalam batas waktu yang ditentukan."""
        if self.active_order_id and self.order_placed_time:
            elapsed = time.time() - self.order_placed_time
            if elapsed > config.LIMIT_TIMEOUT_SECONDS:
                console.print(f"[yellow]Limit order {self.active_order_id} melewati {config.LIMIT_TIMEOUT_SECONDS} detik. Membatalkan order...[/yellow]")
                try:
                    self.exchange.cancel_order(self.active_order_id, self.symbol)
                    console.print("[green]Limit order berhasil dibatalkan (mencegah slippage/stuck order).[/green]")
                except Exception as e:
                    console.print(f"[red]Gagal membatalkan order (mungkin sudah terisi): {e}[/red]")
                self.active_order_id = None
                self.order_placed_time = None

    def place_limit_order(self, signal: dict):
        """Memasang LIMIT ORDER terisolasi untuk eksekusi sebagai Maker."""
        side = signal['side'].lower()  # 'buy' atau 'sell'
        qty = signal['qty']
        best_bid, best_ask = self.get_best_bid_ask()

        # Untuk Buy: pasang di Best Bid agar maker. Untuk Sell: pasang di Best Ask.
        limit_price = best_bid if side == 'buy' else best_ask
        if not limit_price:
            limit_price = signal['entry_price']

        params = {
            'postOnly': config.POST_ONLY  # Wajib maker: menolak order jika langsung kena taker
        }

        console.print(Panel(
            f"[bold cyan]MEMASANG LIMIT ORDER ({config.MARGIN_MODE})[/bold cyan]\n"
            f"Simbol: {self.symbol}\n"
            f"Posisi: [bold]{signal['side']}[/bold]\n"
            f"Harga Limit: ${limit_price:,.2f}\n"
            f"Jumlah: {qty} ({signal['notional']} USD)\n"
            f"Margin Terisolasi: ${signal['margin_required']:.2f}\n"
            f"Toleransi Risiko (SL): ${signal['max_risk_usd']:.3f} (0.5% modal)\n"
            f"Target Profit (TP): ${signal['target_profit_usd']:.3f}",
            title="Order Dispatcher",
            style="green"
        ))

        try:
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='limit',
                side=side,
                amount=qty,
                price=limit_price,
                params=params
            )
            self.active_order_id = order['id']
            self.order_placed_time = time.time()
            console.print(f"[bold green]Limit order berhasil dipasang! ID: {self.active_order_id}[/bold green]")
        except Exception as e:
            console.print(f"[red]Gagal memasang limit order: {e}[/red]")

    def run(self):
        """Siklus utama bot scalping."""
        console.print("[bold green]Memulai Bot Scalping Otomatis...[/bold green]")
        self.setup_account()

        while True:
            try:
                # 1. Cek pembatalan order menggantung
                self.cancel_stale_limit_order()

                # 2. Cek posisi aktif
                current_position = self.check_active_positions()
                if current_position:
                    console.print(f"[cyan]Posisi sedang terbuka: {current_position.get('side')} {current_position.get('contracts')} kontrak. Menunggu TP/SL...[/cyan]")
                    time.sleep(5)
                    continue

                # 3. Ambil data & cari sinyal
                df = self.fetch_market_data()
                latest_bar = df.iloc[-1]
                latest_price = latest_bar['close']

                console.print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] {self.symbol} "
                    f"Harga: ${latest_price:,.2f} | "
                    f"EMA 9/21: {latest_bar['ema_fast']:.1f}/{latest_bar['ema_slow']:.1f} | "
                    f"EMA 200: {latest_bar['ema_trend']:.1f} | "
                    f"RSI: {latest_bar['rsi']:.1f}"
                )

                # Jika tidak ada limit order aktif, evaluasi sinyal baru
                if self.active_order_id is None:
                    signal = check_signal(df)
                    if signal:
                        console.print(f"[bold yellow]SINYAL VALID DITEMUKAN: {signal['side']}![/bold yellow]")
                        self.place_limit_order(signal)

                time.sleep(10)  # Polling interval 10 detik

            except KeyboardInterrupt:
                console.print("[bold red]Bot dihentikan oleh pengguna.[/bold red]")
                break
            except Exception as e:
                console.print(f"[red]Error pada loop utama: {e}[/red]")
                time.sleep(10)

if __name__ == "__main__":
    bot = ScalpingBot()
    bot.run()

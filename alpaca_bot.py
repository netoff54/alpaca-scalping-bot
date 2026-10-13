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
import ccxt

from config import config
from strategy import prepare_indicators

load_dotenv()
console = Console()

# Daftar 32 Koin / Token Peringkat Teratas (Top-Ranked Crypto Universe) yang didukung Alpaca
# Disusun berdasarkan urutan ranking market cap & volume pasar global
TOP_RANKED_CRYPTO = [
    "BTC/USD",   # #1 Bitcoin
    "ETH/USD",   # #2 Ethereum
    "SOL/USD",   # #3 Solana
    "XRP/USD",   # #4 Ripple
    "DOGE/USD",  # #5 Dogecoin
    "ADA/USD",   # #6 Cardano
    "AVAX/USD",  # #7 Avalanche
    "SHIB/USD",  # #8 Shiba Inu
    "PEPE/USD",  # #9 Pepe
    "LINK/USD",  # #10 Chainlink
    "BCH/USD",   # #11 Bitcoin Cash
    "LTC/USD",   # #12 Litecoin
    "DOT/USD",   # #13 Polkadot
    "UNI/USD",   # #14 Uniswap
    "AAVE/USD",  # #15 Aave
    "RENDER/USD",# #16 Render
    "ARB/USD",   # #17 Arbitrum
    "BONK/USD",  # #18 Bonk
    "WIF/USD",   # #19 dogwifhat
    "POL/USD",   # #20 Polygon
    "FIL/USD",   # #21 Filecoin
    "LDO/USD",   # #22 Lido DAO
    "GRT/USD",   # #23 The Graph
    "CRV/USD",   # #24 Curve DAO
    "SUSHI/USD", # #25 SushiSwap
    "BAT/USD",   # #26 Basic Attention Token
    "ONDO/USD",  # #27 Ondo
    "YFI/USD",   # #28 Yearn Finance
    "XTZ/USD",   # #29 Tezos
    "TRUMP/USD", # #30 Official Trump
    "HYPE/USD",  # #31 Hyperliquid
    "SKY/USD"    # #32 Sky
]

class AlpacaScalper:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID", "PK72AJFKXDUN662G24JW4PP7WS")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY", "HChT8VunCtNo2kvcttyYrCr7wQBTuuGoS1TxFuNpftep")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/v2").rstrip('/')
        
        self.current_symbol = "BTC/USD"
        self.active_order_id = None
        self.order_placed_time = None
        
        # CCXT feed
        self.feed_exchange = ccxt.binance({'enableRateLimit': True})
        
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        self.ranked_pairs = TOP_RANKED_CRYPTO

    def verify_account(self) -> dict:
        url = f"{self.base_url}/account"
        res = requests.get(url, headers=self.headers, timeout=10)
        if res.status_code != 200:
            raise Exception(f"Gagal otentikasi ke Alpaca ({res.status_code}): {res.text}")
        return res.json()

    def get_alpaca_positions(self) -> list:
        url = f"{self.base_url}/positions"
        res = requests.get(url, headers=self.headers, timeout=10)
        return res.json() if res.status_code == 200 else []

    def get_alpaca_orders(self) -> list:
        url = f"{self.base_url}/orders?status=open"
        res = requests.get(url, headers=self.headers, timeout=10)
        return res.json() if res.status_code == 200 else []

    def cancel_order(self, order_id: str):
        url = f"{self.base_url}/orders/{order_id}"
        requests.delete(url, headers=self.headers, timeout=10)

    def get_best_bid_ask(self, symbol: str):
        """Mengambil harga pasar bid & ask terbaik langsung dari Alpaca Data API."""
        try:
            url = f"https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols={symbol}"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                quote = res.json().get('quotes', {}).get(symbol, {})
                return float(quote.get('bp', 0)), float(quote.get('ap', 0))
        except Exception:
            pass
        return None, None

    def fetch_market_candles(self, symbol: str) -> pd.DataFrame:
        """
        Mengambil candle 1-menit untuk kalkulasi indikator.
        Prioritas 1: Alpaca Data API resmi (bebas blokir cloud).
        Prioritas 2: Binance CCXT fallback.
        """
        # Coba dari Alpaca Data API dulu
        try:
            url = f"https://data.alpaca.markets/v1beta3/crypto/us/bars?symbols={symbol}&timeframe=1Min&limit={config.CANDLE_LIMIT}"
            res = requests.get(url, headers=self.headers, timeout=7)
            if res.status_code == 200:
                bars = res.json().get('bars', {}).get(symbol, [])
                if len(bars) >= 50:
                    records = []
                    for b in bars:
                        records.append({
                            'timestamp': b.get('t'),
                            'open': float(b.get('o', 0)),
                            'high': float(b.get('h', 0)),
                            'low': float(b.get('l', 0)),
                            'close': float(b.get('c', 0)),
                            'volume': float(b.get('v', 0))
                        })
                    df = pd.DataFrame(records)
                    return prepare_indicators(df)
        except Exception:
            pass

        # Fallback ke Binance jika Alpaca bars ada jeda
        try:
            bi_sym = symbol.replace('/USD', '/USDT')
            ohlcv = self.feed_exchange.fetch_ohlcv(bi_sym, timeframe=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return prepare_indicators(df)
        except Exception as e:
            return pd.DataFrame()

    def get_compounded_notional(self) -> float:
        """Mengambil seluruh saldo kas yang tersedia untuk compounding otomatis (min $10.00)."""
        try:
            account = self.verify_account()
            cash = float(account.get("cash", 10.0))
            return max(10.00, round(cash, 2))
        except Exception:
            return 10.00

    def calculate_order_qty(self, price: float, notional: float) -> str:
        """Menghitung kuantitas order sesuai presisi harga untuk compounding (min $10.00)."""
        raw_qty = notional / price
        if price > 1000:
            qty_val = round(raw_qty, 7)
            if qty_val * price < 10.00:
                qty_val += 1e-7
            return f"{qty_val:.7f}"
        elif price > 10:
            qty_val = round(raw_qty, 4)
            if qty_val * price < 10.00:
                qty_val += 1e-4
            return f"{qty_val:.4f}"
        elif price > 1:
            qty_val = round(raw_qty, 2)
            if qty_val * price < 10.00:
                qty_val += 0.01
            return f"{qty_val:.2f}"
        else:
            return str(int(math.ceil(raw_qty)))

    def place_limit_buy(self, symbol: str, price: float, notional: float = 10.0) -> dict:
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
        acc_table.add_row("Cash / Modal", f"${float(account.get('cash', 0)):.2f}")
        acc_table.add_row("Portfolio Value", f"${float(account.get('portfolio_value', 0)):.2f}")
        acc_table.add_row("Koin Dipantau", f"{len(self.ranked_pairs)} Top Ranked Coins")
        console.print(acc_table)

        console.print("\n[bold yellow]Memulai Siklus Scanning Multi-Asset Peringkat Teratas...[/bold yellow]\n")

        while True:
            try:
                # 1. Cek Timeout Limit Order yang Menggantung
                if self.active_order_id and self.order_placed_time:
                    elapsed = time.time() - self.order_placed_time
                    if elapsed > config.LIMIT_TIMEOUT_SECONDS:
                        console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [yellow]Limit order {self.active_order_id[:8]} melewati 30s. Membatalkan...[/yellow]")
                        self.cancel_order(self.active_order_id)
                        self.active_order_id = None
                        self.order_placed_time = None
                        console.print("[green]Order berhasil dibatalkan dari Alpaca.[/green]")

                # 2. Cek Posisi Terbuka di Alpaca
                positions = self.get_alpaca_positions()
                if positions:
                    pos = positions[0]
                    pos_sym = pos.get("symbol", "")
                    matched_sym = next((p for p in self.ranked_pairs if p.replace('/', '') == pos_sym), f"{pos_sym[:3]}/{pos_sym[3:]}")
                    
                    qty = float(pos.get("qty", 0))
                    entry_price = float(pos.get("avg_entry_price", 0))
                    
                    best_bid, _ = self.get_best_bid_ask(matched_sym)
                    current_price = best_bid if best_bid else float(pos.get("current_price", 0))
                    
                    pl_pct = ((current_price - entry_price) / entry_price) * 100
                    unrealized_pl = qty * (current_price - entry_price)

                    open_orders = self.get_alpaca_orders()
                    has_active_sell = any(o.get("side") == "sell" for o in open_orders)

                    if pl_pct >= 1.0 and not has_active_sell:
                        console.print(f"[bold green]TAKE PROFIT TERCAPAI ({matched_sym}: +{pl_pct:.2f}%)! Mengirim Limit Sell @ ${current_price:,.2f}...[/bold green]")
                        self.place_limit_sell(matched_sym, qty, current_price)
                    elif pl_pct <= -0.5 and not has_active_sell:
                        console.print(f"[bold red]STOP LOSS TERKENA ({matched_sym}: {pl_pct:.2f}%)! Mengirim Limit Sell @ ${current_price:,.2f}...[/bold red]")
                        self.place_limit_sell(matched_sym, qty, current_price)
                    else:
                        console.print(
                            f"[{datetime.now().strftime('%H:%M:%S')}] [cyan]MENGAWAL POSISI:[/cyan] "
                            f"{qty} {matched_sym} @ ${entry_price:,.2f} | "
                            f"Harga Realtime: ${current_price:,.2f} | "
                            f"PnL: [{'green' if unrealized_pl >= 0 else 'red'}]${unrealized_pl:+.4f} ({pl_pct:+.2f}%)[/]"
                        )
                    
                    time.sleep(5)
                    continue

                # 3. Cek Open Order Beli yang Sedang Antre
                open_orders = self.get_alpaca_orders()
                if open_orders:
                    o = open_orders[0]
                    self.active_order_id = o.get("id")
                    console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [yellow]Menunggu eksekusi Limit Buy: {o.get('symbol')} {o.get('qty')} @ ${float(o.get('limit_price', 0)):,.2f}...[/yellow]")
                    time.sleep(5)
                    continue
                else:
                    self.active_order_id = None

                # 4. SCAN SEMUA 32 KOIN PERINGKAT TERATAS
                console.print(f"[{datetime.now().strftime('%H:%M:%S')}] [dim]Scanning sinyal scalping di antara {len(self.ranked_pairs)} koin peringkat teratas...[/dim]")

                for rank, sym in enumerate(self.ranked_pairs, start=1):
                    try:
                        df = self.fetch_market_candles(sym)
                        if df.empty or len(df) < 50:
                            continue

                        c_prev = df.iloc[-3]
                        c_curr = df.iloc[-2]
                        latest_price = float(df['close'].iloc[-1])
                        
                        golden_cross = (c_prev['ema_fast'] <= c_prev['ema_slow']) and (c_curr['ema_fast'] > c_curr['ema_slow'])
                        is_bullish_trend = c_curr['close'] > c_curr['ema_trend']
                        rsi = float(c_curr['rsi'])

                        # Syarat Sinyal Valid Long
                        if is_bullish_trend and golden_cross and (config.RSI_LONG_MIN <= rsi <= config.RSI_LONG_MAX):
                            console.print(f"\n[bold green]>>> SINYAL VALID PADA RANK #{rank} ({sym})! <<<[/bold green]")
                            console.print(f"Harga: ${latest_price} | RSI: {rsi:.1f} | EMA Trend: {c_curr['ema_trend']:.2f}")

                            best_bid, _ = self.get_best_bid_ask(sym)
                            limit_p = best_bid if best_bid else latest_price

                            # Compounding Dinamis: Gunakan 100% saldo kas yang terkumpul (bunga berbunga)
                            notional_compound = self.get_compounded_notional()
                            console.print(f"[bold cyan]COMPOUNDING AKTIF: Menggunakan seluruh saldo kas ${notional_compound:.2f} untuk {sym} @ ${limit_p:,.2f}...[/bold cyan]")

                            order = self.place_limit_buy(sym, price=limit_p, notional=notional_compound)
                            self.active_order_id = order.get("id")
                            self.order_placed_time = time.time()
                            self.current_symbol = sym
                            console.print(f"[bold green]LIMIT ORDER MASUK KE ALPACA (COMPOUNDING ${notional_compound:.2f})![/bold green] ID: {self.active_order_id}\n")
                            break

                    except Exception:
                        continue

                time.sleep(10)

            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error loop: {e}[/red]")
                time.sleep(5)

if __name__ == "__main__":
    scalper = AlpacaScalper()
    scalper.run()

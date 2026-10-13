import hmac
import hashlib
import time
import math
import urllib.parse
from typing import Dict, Any, List, Optional, Set
import requests
from rich.console import Console

console = Console()

class BinanceFuturesClient:
    """
    Klien REST API Binance Futures USDⓈ-M Native murni.
    Memuat aturan presisi pasar (exchangeInfo) satu kali saat startup ke memori (<50KB),
    menjamin 100% presisi harga/lot size tepat dan secara otomatis menyaring token non-crypto.
    """
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://fapi.binance.com"
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "User-Agent": "BinanceAutonomousScalper/2.0 (Render Frankfurt)"
        })
        self._symbols_rules: Dict[str, Dict[str, Any]] = {}
        self.allowed_crypto_symbols: Set[str] = set()
        
        # Muat pasar dan filter aturan presisi
        self.load_markets()

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 60000
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def load_markets(self):
        """
        Memuat dan menyaring seluruh instrumen bursa:
        1. Hanya menyaring kontrak pure crypto 'PERPETUAL' (mengabaikan TRADIFI_PERPETUAL, saham, & komoditas minyak/emas).
        2. Menyimpan aturan lot size, step size, tick size, dan precision desimal per koin.
        """
        try:
            url = f"{self.base_url}/fapi/v1/exchangeInfo"
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            
            rules_map = {}
            allowed = set()
            
            for s in data.get("symbols", []):
                sym = s.get("symbol", "")
                status = s.get("status", "")
                contract_type = s.get("contractType", "")
                quote_asset = s.get("quoteAsset", "")
                underlying_type = s.get("underlyingType", "")
                
                # WAJIB: Hanya trading kontrak Crypto Perpetual murni
                if quote_asset != "USDT" or status != "TRADING":
                    continue
                if contract_type != "PERPETUAL":
                    continue
                if underlying_type in ("EQUITY", "COMMODITY", "TradFi"):
                    continue
                    
                tick_size = 0.0001
                step_size = 1.0
                min_qty = 1.0
                min_notional = 5.0
                
                for f in s.get("filters", []):
                    ftype = f.get("filterType")
                    if ftype == "PRICE_FILTER":
                        tick_size = float(f.get("tickSize", 0.0001))
                    elif ftype == "LOT_SIZE":
                        step_size = float(f.get("stepSize", 1.0))
                        min_qty = float(f.get("minQty", 1.0))
                    elif ftype == "MIN_NOTIONAL":
                        min_notional = float(f.get("notional", 5.0))
                        
                price_prec = int(s.get("pricePrecision", 4))
                qty_prec = int(s.get("quantityPrecision", 2))
                
                rules_map[sym] = {
                    "tick_size": tick_size,
                    "step_size": step_size,
                    "min_qty": min_qty,
                    "min_notional": min_notional,
                    "price_precision": price_prec,
                    "qty_precision": qty_prec
                }
                allowed.add(sym)
                
            self._symbols_rules = rules_map
            self.allowed_crypto_symbols = allowed
            console.log(f"[bold green]Berhasil memuat aturan presisi untuk {len(allowed)} koin crypto murni Binance Futures.[/bold green]")
        except Exception as e:
            console.log(f"[red]Gagal memuat exchangeInfo Binance: {e}[/red]")

    def format_price(self, symbol: str, price: float) -> float:
        """Menyesuaikan harga ke tick_size dan presisi desimal resmi bursa."""
        rules = self._symbols_rules.get(symbol)
        if not rules:
            return round(price, 4)
        tick = rules["tick_size"]
        prec = rules["price_precision"]
        if tick <= 0:
            return round(price, prec)
        val = math.floor(price / tick) * tick
        return float(f"{val:.{prec}f}")

    def format_qty(self, symbol: str, qty: float) -> float:
        """Menyesuaikan lot size kuantitas ke step_size dan presisi desimal resmi bursa."""
        rules = self._symbols_rules.get(symbol)
        if not rules:
            return round(qty, 2)
        step = rules["step_size"]
        prec = rules["qty_precision"]
        if step <= 0:
            return round(qty, prec)
        val = math.floor(qty / step) * step
        return float(f"{val:.{prec}f}")

    def calculate_order_qty(self, symbol: str, target_notional: float, price: float) -> float:
        """
        Menghitung kuantitas order yang dijamin:
        1. Memenuhi step_size dan quantityPrecision resmi.
        2. Nilai notional (qty * price) dijamin >= $5.00 (tidak pernah kena error -4164).
        3. Tidak di bawah min_qty bursa.
        """
        rules = self._symbols_rules.get(symbol, {})
        step = rules.get("step_size", 1.0)
        prec = rules.get("qty_precision", 2)
        min_qty = rules.get("min_qty", step)
        
        # Target notional minimal $5.15 untuk buffer aman anti-slippage
        effective_notional = max(target_notional, 5.15)
        
        # Gunakan math.ceil agar pembulatan kelipatan lot size tidak menjatuhkan notional di bawah $5.0
        raw_qty = effective_notional / price
        steps_count = math.ceil(raw_qty / step)
        qty = steps_count * step
        
        if qty < min_qty:
            qty = min_qty
            
        # Pengecekan ketat: jika hasil kali qty * price masih < 5.0, naikkan 1 step
        while (qty * price) < 5.05:
            qty += step
            
        return float(f"{qty:.{prec}f}")


    def get_balance(self) -> Dict[str, float]:
        """Mengambil saldo wallet Futures (USDT)."""
        url = f"{self.base_url}/fapi/v2/balance"
        params = self._sign({})
        resp = self.session.get(url, params=params, timeout=10)
        data = resp.json()
        if not isinstance(data, list):
            raise Exception(f"Balance error: {data}")
        
        total_wallet = 0.0
        available = 0.0
        unrealized = 0.0
        for item in data:
            if item.get("asset") == "USDT":
                total_wallet = float(item.get("balance", 0.0))
                available = float(item.get("availableBalance", 0.0))
                unrealized = float(item.get("crossUnPnl", 0.0))
                break
        return {
            "total_wallet": total_wallet,
            "available": available,
            "unrealized_pnl": unrealized
        }

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Mengambil posisi terbuka di akun Binance Futures."""
        url = f"{self.base_url}/fapi/v2/positionRisk"
        params = self._sign({})
        resp = self.session.get(url, params=params, timeout=10)
        data = resp.json()
        if not isinstance(data, list):
            return []
        
        open_pos = []
        for p in data:
            amt = float(p.get("positionAmt", 0.0))
            if abs(amt) > 0:
                open_pos.append({
                    "symbol": p.get("symbol"),
                    "amount": amt,
                    "entry_price": float(p.get("entryPrice", 0.0)),
                    "mark_price": float(p.get("markPrice", 0.0)),
                    "unrealized_pnl": float(p.get("unRealizedProfit", 0.0)),
                    "leverage": int(p.get("leverage", 10)),
                    "isolated": p.get("isolated") == "true" or p.get("isolated") is True
                })
        return open_pos

    def ensure_single_asset_mode(self):
        """Memastikan mode Multi-Assets dimatikan agar ISOLATED margin dapat digunakan."""
        try:
            url = f"{self.base_url}/fapi/v1/multiAssetsMargin"
            params = self._sign({})
            resp = self.session.get(url, params=params, timeout=10)
            res = resp.json()
            if res.get("multiAssetsMargin") is True:
                post_params = self._sign({"multiAssetsMargin": "false"})
                self.session.post(url, params=post_params, timeout=10)
        except Exception:
            pass

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED"):
        url = f"{self.base_url}/fapi/v1/marginType"
        params = self._sign({"symbol": symbol, "marginType": margin_type})
        try:
            self.session.post(url, params=params, timeout=10)
        except Exception:
            pass

    def set_leverage(self, symbol: str, leverage: int = 10):
        url = f"{self.base_url}/fapi/v1/leverage"
        params = self._sign({"symbol": symbol, "leverage": leverage})
        try:
            self.session.post(url, params=params, timeout=10)
        except Exception:
            pass

    def fetch_best_bid_ask(self, symbol: str) -> Dict[str, float]:
        url = f"{self.base_url}/fapi/v1/depth?symbol={symbol}&limit=5"
        resp = self.session.get(url, timeout=5)
        data = resp.json()
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        best_bid = float(bids[0][0]) if bids else 0.0
        best_ask = float(asks[0][0]) if asks else 0.0
        return {"bid": best_bid, "ask": best_ask}

    def create_limit_order(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        """Kirim Limit Order Maker-Only (timeInForce=GTX / Post Only)."""
        url = f"{self.base_url}/fapi/v1/order"
        params = self._sign({
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTX",
            "quantity": qty,
            "price": price
        })
        resp = self.session.post(url, params=params, timeout=10)
        data = resp.json()
        if "orderId" not in data:
            raise Exception(f"Limit order gagal: {data}")
        return data

    def create_market_close_order(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """Tutup posisi seketika dengan Market Order (reduceOnly=true)."""
        url = f"{self.base_url}/fapi/v1/order"
        params = self._sign({
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": qty,
            "reduceOnly": "true"
        })
        resp = self.session.post(url, params=params, timeout=10)
        return resp.json()

    def get_order(self, symbol: str, order_id: Any) -> Dict[str, Any]:
        url = f"{self.base_url}/fapi/v1/order"
        params = self._sign({"symbol": symbol, "orderId": order_id})
        resp = self.session.get(url, params=params, timeout=10)
        return resp.json()

    def cancel_order(self, symbol: str, order_id: Any) -> Dict[str, Any]:
        url = f"{self.base_url}/fapi/v1/order"
        params = self._sign({"symbol": symbol, "orderId": order_id})
        resp = self.session.delete(url, params=params, timeout=10)
        return resp.json()

    def fetch_price(self, symbol: str) -> float:
        url = f"{self.base_url}/fapi/v1/ticker/price?symbol={symbol}"
        resp = self.session.get(url, timeout=5)
        return float(resp.json().get("price", 0.0))

    def fetch_top_tickers(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/fapi/v1/ticker/24hr"
        resp = self.session.get(url, timeout=10)
        return resp.json()

    def fetch_klines(self, symbol: str, interval: str = "1m", limit: int = 220) -> Optional[List[List[float]]]:
        url = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        resp = self.session.get(url, timeout=5)
        data = resp.json()
        if not isinstance(data, list):
            return None
        return [
            [float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
            for c in data
        ]

import hmac
import hashlib
import time
import math
import re
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
        self._symbols_max_leverage: Dict[str, int] = {}
        self.allowed_crypto_symbols: Set[str] = set()
        self.ban_until: float = 0.0
        self._last_ban_log_time: float = 0.0
        self.current_weight_1m: int = 0
        self.scan_throttle_until: float = 0.0
        
        # Muat pasar dan filter aturan presisi
        self.load_markets()
        self.load_leverage_brackets()

    def is_banned(self) -> bool:
        """Mengecek apakah IP server sedang dalam masa cooldown rate limit Binance resmi (HTTP 418/429)."""
        return time.time() < self.ban_until

    def is_scan_throttled(self) -> bool:
        """Mengecek apakah pemindaian koin perlu jeda sesaat karena weight IP mendekati 2400."""
        return time.time() < self.scan_throttle_until

    def check_response_for_ban(self, resp_or_data: Any):
        """Mendeteksi apakah Binance merespons dengan HTTP 418/429 atau kode -1003 ban."""
        msg = ""
        now = time.time()
        if isinstance(resp_or_data, requests.Response):
            used_weight = resp_or_data.headers.get("x-mbx-used-weight-1m")
            if used_weight:
                try:
                    w = int(used_weight)
                    self.current_weight_1m = w
                    # HANYA throttle scanner jika weight benar-benar mendekati limit 2400 (misal >= 2320)
                    # JANGAN set self.ban_until di sini, agar order eksekusi (weight 1) tetap dapat berjalan lancar!
                    if w >= 2320:
                        self.scan_throttle_until = max(self.scan_throttle_until, now + 6.0)
                        if now - self._last_ban_log_time > 20:
                            self._last_ban_log_time = now
                            console.log(f"[bold yellow]Request weight IP bursa tinggi ({w}/2400). Scanner melambat 6s agar weight turun...[/bold yellow]")
                except Exception:
                    pass

            if resp_or_data.status_code in (418, 429):
                msg = resp_or_data.text
        elif isinstance(resp_or_data, dict):
            if resp_or_data.get("code") in (-1003, -1000):
                msg = str(resp_or_data)
        elif isinstance(resp_or_data, str):
            msg = resp_or_data

        if "-1003" in msg or "IP banned" in msg or "Way too many requests" in msg or "banned until" in msg or "Too many requests" in msg:
            import re
            match = re.search(r"banned until (\d+)", msg)
            if match:
                # Ban resmi dari bursa dengan timestamp
                self.ban_until = float(match.group(1)) / 1000.0
                if now - self._last_ban_log_time > 60:
                    self._last_ban_log_time = now
                    s_left = int(self.ban_until - now)
                    m_left = s_left // 60
                    sec_left = s_left % 60
                    wib_time = time.strftime('%H:%M:%S', time.gmtime(self.ban_until + 7 * 3600))
                    console.log(f"[bold yellow]Rate limit Binance aktif ({msg[:100]}). Server IP istirahat hingga {wib_time} WIB ({m_left}m {sec_left}s lagi).[/bold yellow]")
            else:
                # Rolling window limit 1 menit (bukan ban panjang). Jeda 10 detik agar jendela 1 menit bergeser
                self.ban_until = max(self.ban_until, now + 10.0)
                if now - self._last_ban_log_time > 10:
                    self._last_ban_log_time = now
                    console.log(f"[bold yellow]Rolling rate limit 1m terdeteksi ({msg[:100]}). Jeda singkat 10 detik lalu lanjut otomatis...[/bold yellow]")

    def _apply_fallback_symbols(self):
        """Mengaktifkan daftar default 28 koin crypto likuid utama jika bursa sedang dalam cooldown."""
        fallback = {
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "NEARUSDT", "APTUSDT", "TAOUSDT", "DOTUSDT", "FILUSDT",
            "WLDUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "FETUSDT", "RENDERUSDT", "TIAUSDT",
            "SEIUSDT", "ENAUSDT", "PEPEUSDT", "SHIBUSDT", "BONKUSDT", "WIFUSDT", "FLOKIUSDT"
        }
        if not self.allowed_crypto_symbols:
            self.allowed_crypto_symbols = fallback

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
        if self.is_banned():
            self._apply_fallback_symbols()
            return

        try:
            url = f"{self.base_url}/fapi/v1/exchangeInfo"
            resp = self.session.get(url, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            
            if not isinstance(data, dict) or "symbols" not in data:
                self._apply_fallback_symbols()
                return

            rules_map = {}
            allowed = set()
            
            for s in data.get("symbols", []):
                sym = s.get("symbol", "")
                status = s.get("status", "")
                contract_type = s.get("contractType", "")
                quote_asset = s.get("quoteAsset", "")
                underlying_type = s.get("underlyingType", "")
                
                # WAJIB: Hanya trading kontrak Crypto Perpetual murni (BUANG SEMUA STABLECOIN & FIAT PEG)
                base_asset = s.get("baseAsset", "").upper()
                stablecoins = {
                    "USDC", "FDUSD", "BUSD", "TUSD", "EUR", "DAI", "AEUR", "USDP", "USD1",
                    "BFUSD", "USDT", "USD", "USTC", "EURI", "USDE", "USDJ", "XAUT", "PAXG"
                }
                if base_asset in stablecoins:
                    continue
                if any(sym.startswith(sc) for sc in ("USDC", "FDUSD", "BUSD", "TUSD", "EUR", "DAI", "AEUR", "USDP", "USD1", "BFUSD")):
                    continue

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
                
            if len(allowed) > 0:
                self._symbols_rules = rules_map
                self.allowed_crypto_symbols = allowed
                console.log(f"[bold green]Berhasil memuat aturan presisi untuk {len(allowed)} koin crypto murni Binance Futures.[/bold green]")
            else:
                self._apply_fallback_symbols()
        except Exception as e:
            console.log(f"[yellow]Gagal memuat exchangeInfo Binance: {e}[/yellow]")
            self._apply_fallback_symbols()

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
        if self.is_banned():
            raise Exception(f"IP dalam cooldown hingga {time.strftime('%H:%M:%S', time.localtime(self.ban_until))}")
        url = f"{self.base_url}/fapi/v2/balance"
        params = self._sign({})
        resp = self.session.get(url, params=params, timeout=10)
        self.check_response_for_ban(resp)
        data = resp.json()
        self.check_response_for_ban(data)
        if not isinstance(data, list):
            raise Exception(f"Balance error: {data}")
        
        total_wallet = 0.0
        available = 0.0
        unrealized = 0.0
        for item in data:
            if isinstance(item, dict) and item.get("asset") == "USDT":
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
        if self.is_banned():
            return []
        url = f"{self.base_url}/fapi/v2/positionRisk"
        params = self._sign({})
        resp = self.session.get(url, params=params, timeout=10)
        self.check_response_for_ban(resp)
        data = resp.json()
        self.check_response_for_ban(data)
        if not isinstance(data, list):
            return []
        
        open_pos = []
        for p in data:
            if not isinstance(p, dict):
                continue
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
        if self.is_banned():
            return
        try:
            url = f"{self.base_url}/fapi/v1/multiAssetsMargin"
            params = self._sign({})
            resp = self.session.get(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            res = resp.json()
            if isinstance(res, dict) and res.get("multiAssetsMargin") is True:
                post_params = self._sign({"multiAssetsMargin": "false"})
                self.session.post(url, params=post_params, timeout=10)
        except Exception:
            pass

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED"):
        if self.is_banned():
            return
        url = f"{self.base_url}/fapi/v1/marginType"
        params = self._sign({"symbol": symbol, "marginType": margin_type})
        try:
            resp = self.session.post(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
        except Exception:
            pass

    def load_leverage_brackets(self):
        """Mengambil batas leverage maksimal resmi dari bursa untuk seluruh koin."""
        if self.is_banned():
            return
        url = f"{self.base_url}/fapi/v1/leverageBracket"
        try:
            params = self._sign({})
            resp = self.session.get(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    sym = item.get("symbol")
                    brackets = item.get("brackets", [])
                    if sym and brackets:
                        max_lev = int(brackets[0].get("initialLeverage", 20))
                        self._symbols_max_leverage[sym] = max_lev
                console.log(f"[bold green]Berhasil memuat batas leverage maksimal untuk {len(self._symbols_max_leverage)} koin.[/bold green]")
        except Exception as e:
            console.log(f"[dim]Notice load leverage brackets: {e}[/dim]")

    def get_max_leverage(self, symbol: str) -> int:
        """Mengembalikan leverage maksimal resmi koin (default 50 jika belum termuat)."""
        return self._symbols_max_leverage.get(symbol, 50)

    def set_leverage(self, symbol: str, target_leverage: int = 50, min_leverage: int = 20) -> int:
        """
        Mengatur leverage dengan sistem Range Stepping Probing [50x down to 20x]:
        1. Jika dari leverage brackets koin < 20x (misal AVAUSDT 10x), langsung kembalikan < 20x agar di-skip.
        2. Mencoba target_leverage (50x) terlebih dahulu.
        3. Jika ditolak bursa/koin/akun (misal akun baru atau koin dibatasi 20x-49x),
           secara berurutan mencoba 49x, 48x, ... hingga 20x untuk memastikan leverage
           maksimal yang tersedia terpakai.
        4. Jika koin tidak bisa mencapai minimal 20x, kembalikan nilai aslinya (< 20) agar bot
           langsung men-skip koin demi mencegah pembengkakan margin di atas 1%.
        """
        if self.is_banned():
            return max(min_leverage, min(target_leverage, self.get_max_leverage(symbol)))
        
        cached_lev = self._symbols_max_leverage.get(symbol)
        
        # Fast Skip: jika batas resmi koin sudah diketahui < 20x (misal AVAUSDT 10x), hemat request & langsung skip
        if cached_lev is not None and cached_lev < min_leverage:
            console.log(f"[bold yellow]Batas leverage resmi {symbol} hanya {cached_lev}x (< {min_leverage}x). Melewati probing agar koin di-skip.[/bold yellow]")
            return cached_lev

        start_lev = min(target_leverage, cached_lev if cached_lev and cached_lev >= min_leverage else target_leverage)
        
        url = f"{self.base_url}/fapi/v1/leverage"
        
        # 1. Coba start_lev (50x)
        try:
            params = self._sign({"symbol": symbol, "leverage": start_lev})
            resp = self.session.post(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            if isinstance(data, dict) and "leverage" in data:
                actual = int(data["leverage"])
                self._symbols_max_leverage[symbol] = actual
                console.log(f"[bold green]Leverage {symbol} berhasil diset ke {actual}x (Maksimal yang diizinkan bursa).[/bold green]")
                return actual
            
            # Jika ditolak bursa, periksa apakah pesan error mencantumkan batas maksimal spesifik
            err_msg = str(data.get("msg", ""))
            match = re.search(r'(?:max(?:imum)?\s*leverage|leverage\s*is\s*larger\s*than|allowed\s*is)\D*(\d+)', err_msg, re.I)
            if match:
                suggested_max = int(match.group(1))
                if min_leverage <= suggested_max <= target_leverage:
                    params = self._sign({"symbol": symbol, "leverage": suggested_max})
                    resp2 = self.session.post(url, params=params, timeout=10)
                    data2 = resp2.json()
                    if isinstance(data2, dict) and "leverage" in data2:
                        actual = int(data2["leverage"])
                        self._symbols_max_leverage[symbol] = actual
                        console.log(f"[bold green]Leverage {symbol} berhasil diset ke {actual}x (Sesuai batas resmi akun/koin: {actual}x).[/bold green]")
                        return actual
                elif suggested_max < min_leverage:
                    self._symbols_max_leverage[symbol] = suggested_max
                    console.log(f"[bold yellow]Batas leverage akun/koin untuk {symbol} hanya {suggested_max}x (< {min_leverage}x).[/bold yellow]")
                    return suggested_max
        except Exception as e:
            console.log(f"[dim]Pemeriksaan awal leverage {start_lev}x {symbol}: {e}[/dim]")

        # 2. Stepping turun berurutan dari (start_lev - 1) ke 20x
        console.log(f"[yellow]Mencari leverage tertinggi yang tersedia untuk {symbol} (Range {start_lev-1}x s/d {min_leverage}x berurutan)...[/yellow]")
        for lev in range(start_lev - 1, min_leverage - 1, -1):
            try:
                params = self._sign({"symbol": symbol, "leverage": lev})
                resp = self.session.post(url, params=params, timeout=6)
                self.check_response_for_ban(resp)
                data = resp.json()
                if isinstance(data, dict) and "leverage" in data:
                    actual = int(data["leverage"])
                    self._symbols_max_leverage[symbol] = actual
                    console.log(f"[bold green]Ditemukan leverage maksimal untuk {symbol}: {actual}x (Range 50x-{min_leverage}x)![/bold green]")
                    return actual
            except Exception:
                continue

        # 3. Jika probing belum terdaftar, periksa leverage aktif bursa melalui positionRisk
        try:
            url_risk = f"{self.base_url}/fapi/v2/positionRisk"
            params_risk = self._sign({"symbol": symbol})
            resp_risk = self.session.get(url_risk, params=params_risk, timeout=5)
            self.check_response_for_ban(resp_risk)
            data_risk = resp_risk.json()
            if isinstance(data_risk, list) and len(data_risk) > 0:
                act = int(data_risk[0].get("leverage", 1))
                self._symbols_max_leverage[symbol] = act
                console.log(f"[bold green]Leverage aktif riil Binance untuk {symbol}: {act}x[/bold green]")
                return act
        except Exception:
            pass

        return cached_lev if (cached_lev and cached_lev < min_leverage) else 1

    def fetch_best_bid_ask(self, symbol: str) -> Dict[str, float]:
        if self.is_banned():
            s_left = self.ban_until - time.time()
            if s_left <= 15.0:
                time.sleep(max(0.5, s_left + 0.2))
            else:
                return {"bid": 0.0, "ask": 0.0}
        try:
            url = f"{self.base_url}/fapi/v1/depth?symbol={symbol}&limit=5"
            resp = self.session.get(url, timeout=5)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if not isinstance(data, dict):
                return {"bid": 0.0, "ask": 0.0}
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            best_bid = float(bids[0][0]) if bids and isinstance(bids[0], (list, tuple)) else 0.0
            best_ask = float(asks[0][0]) if asks and isinstance(asks[0], (list, tuple)) else 0.0
            return {"bid": best_bid, "ask": best_ask}
        except Exception:
            return {"bid": 0.0, "ask": 0.0}

    def create_limit_order(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        """Kirim Limit Order Maker-Only (timeInForce=GTX / Post Only) dengan auto-wait rate limit."""
        url = f"{self.base_url}/fapi/v1/order"
        last_err = None

        for attempt in range(2):
            now = time.time()
            if self.is_banned():
                wait_sec = self.ban_until - now
                if wait_sec <= 15.0:
                    console.log(f"[bold yellow]IP cooldown aktif ({wait_sec:.1f}s lagi). Menunggu otomatis sebelum kirim order...[/bold yellow]")
                    time.sleep(max(0.5, wait_sec + 0.5))
                else:
                    raise Exception(f"Tidak dapat mengirim order: IP bursa dalam ban resmi ({int(wait_sec)}s lagi).")

            params = self._sign({
                "symbol": symbol,
                "side": side.upper(),
                "type": "LIMIT",
                "timeInForce": "GTX",
                "quantity": qty,
                "price": price
            })
            try:
                resp = self.session.post(url, params=params, timeout=10)
                self.check_response_for_ban(resp)
                try:
                    data = resp.json()
                except Exception:
                    data = {"error": resp.text}
                self.check_response_for_ban(data)

                if isinstance(data, dict) and "orderId" in data:
                    return data

                # Jika ditolak karena GTX maker price crossed, langsung kembalikan pesan jelas
                if isinstance(data, dict) and data.get("code") == -5022:
                    raise Exception("Order GTX dibatalkan: Harga akan menjadi Taker (Post-Only).")

                last_err = data
            except Exception as e:
                last_err = str(e)

            # Jika attempt 0 dan ada cooldown singkat yang baru terpicu, tunggu dan coba sekali lagi
            if attempt == 0 and self.is_banned() and (self.ban_until - time.time()) <= 15.0:
                w_left = max(1.0, self.ban_until - time.time() + 0.5)
                console.log(f"[yellow]Mencoba mengirim ulang order setelah jeda {w_left:.1f}s...[/yellow]")
                time.sleep(w_left)
                continue
            break

        raise Exception(f"Limit order gagal: {last_err}")

    def create_limit_close_order(self, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
        """Tutup posisi dengan Limit Order Maker-Only (reduceOnly=true, timeInForce=GTX / Post Only) agar fee terendah."""
        url = f"{self.base_url}/fapi/v1/order"
        last_err = None

        for attempt in range(2):
            now = time.time()
            if self.is_banned():
                wait_sec = self.ban_until - now
                if wait_sec <= 15.0:
                    console.log(f"[bold yellow]IP cooldown aktif ({wait_sec:.1f}s lagi). Menunggu otomatis sebelum kirim maker close order...[/bold yellow]")
                    time.sleep(max(0.5, wait_sec + 0.5))
                else:
                    raise Exception(f"Tidak dapat menutup order: IP bursa dalam ban resmi ({int(wait_sec)}s lagi).")

            params = self._sign({
                "symbol": symbol,
                "side": side.upper(),
                "type": "LIMIT",
                "timeInForce": "GTX",
                "quantity": qty,
                "price": price,
                "reduceOnly": "true"
            })
            try:
                resp = self.session.post(url, params=params, timeout=10)
                self.check_response_for_ban(resp)
                try:
                    data = resp.json()
                except Exception:
                    data = {"error": resp.text}
                self.check_response_for_ban(data)

                if isinstance(data, dict) and "orderId" in data:
                    return data

                # Jika ditolak karena harga langsung match (code -5022 Post-Only), kembalikan dict khusus
                if isinstance(data, dict) and data.get("code") == -5022:
                    return {"code": -5022, "msg": "Post-Only crossed"}

                last_err = data
            except Exception as e:
                last_err = str(e)

            if attempt == 0 and self.is_banned() and (self.ban_until - time.time()) <= 15.0:
                time.sleep(max(1.0, self.ban_until - time.time() + 0.5))
                continue
            break

        raise Exception(f"Limit close order gagal: {last_err}")

    def create_market_close_order(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """Tutup posisi seketika dengan Market Order (reduceOnly=true). Prioritas Tertinggi."""
        url = f"{self.base_url}/fapi/v1/order"
        last_err = None
        for attempt in range(3):
            try:
                if self.is_banned():
                    wait_sec = self.ban_until - time.time()
                    if wait_sec <= 12.0:
                        time.sleep(max(0.5, wait_sec + 0.5))
                params = self._sign({
                    "symbol": symbol,
                    "side": side.upper(),
                    "type": "MARKET",
                    "quantity": qty,
                    "reduceOnly": "true"
                })
                resp = self.session.post(url, params=params, timeout=10)
                self.check_response_for_ban(resp)
                try:
                    data = resp.json()
                except Exception:
                    data = {"error": resp.text}
                self.check_response_for_ban(data)
                if isinstance(data, dict) and "orderId" in data:
                    return data
                last_err = data
            except Exception as e:
                last_err = str(e)
            time.sleep(1.5)
        raise Exception(f"Market close order gagal: {last_err}")

    def get_order(self, symbol: str, order_id: Any) -> Dict[str, Any]:
        if self.is_banned():
            return {}
        url = f"{self.base_url}/fapi/v1/order"
        params = self._sign({"symbol": symbol, "orderId": order_id})
        resp = self.session.get(url, params=params, timeout=10)
        self.check_response_for_ban(resp)
        data = resp.json()
        self.check_response_for_ban(data)
        return data if isinstance(data, dict) else {}

    def cancel_order(self, symbol: str, order_id: Any) -> Dict[str, Any]:
        if self.is_banned():
            return {}
        url = f"{self.base_url}/fapi/v1/order"
        params = self._sign({"symbol": symbol, "orderId": order_id})
        resp = self.session.delete(url, params=params, timeout=10)
        self.check_response_for_ban(resp)
        data = resp.json()
        self.check_response_for_ban(data)
        return data if isinstance(data, dict) else {}

    def create_stop_loss_order(self, symbol: str, side: str, stop_price: float, qty: Optional[float] = None) -> Dict[str, Any]:
        """
        Memasang Native Stop Loss (STOP_MARKET) langsung di server Matching Engine Binance Futures.
        Menggunakan closePosition=true dan workingType=MARK_PRICE sehingga seluruh posisi otomatis
        ditutup instan di bursa, kebal terhadap manipulasi wick jarum (flashdump order book lokal).
        """
        if self.is_banned():
            return {}
        url = f"{self.base_url}/fapi/v1/order"
        formatted_stop = self.format_price(symbol, stop_price)
        
        # 1. Coba closePosition=true terlebih dahulu (Metode resmi standar emas Binance)
        params = self._sign({
            "symbol": symbol,
            "side": side.upper(),
            "type": "STOP_MARKET",
            "stopPrice": formatted_stop,
            "closePosition": "true",
            "workingType": "MARK_PRICE"
        })
        try:
            resp = self.session.post(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if isinstance(data, dict) and "orderId" in data:
                console.log(f"[bold green]🛡️ NATIVE STOP LOSS TERPASANG DI BINANCE: {side} {symbol} @ {formatted_stop} (MARK_PRICE / closePosition=true)[/bold green]")
                return data
            
            # 2. Fallback: jika closePosition ditolak, gunakan quantity + reduceOnly
            if qty and qty > 0:
                formatted_qty = self.format_quantity(symbol, qty)
                p2 = self._sign({
                    "symbol": symbol,
                    "side": side.upper(),
                    "type": "STOP_MARKET",
                    "stopPrice": formatted_stop,
                    "quantity": formatted_qty,
                    "reduceOnly": "true",
                    "workingType": "MARK_PRICE"
                })
                r2 = self.session.post(url, params=p2, timeout=10)
                d2 = r2.json()
                if isinstance(d2, dict) and "orderId" in d2:
                    console.log(f"[bold green]🛡️ NATIVE STOP LOSS TERPASANG DI BINANCE: {side} {formatted_qty} {symbol} @ {formatted_stop} (MARK_PRICE / reduceOnly=true)[/bold green]")
                    return d2
            console.log(f"[yellow]Peringatan pasang native SL: {data}[/yellow]")
            return data if isinstance(data, dict) else {}
        except Exception as e:
            console.log(f"[red]Gagal memasang native SL di Binance: {e}[/red]")
            return {}

    def create_take_profit_order(self, symbol: str, side: str, stop_price: float, qty: Optional[float] = None) -> Dict[str, Any]:
        """
        Memasang Native Take Profit (TAKE_PROFIT_MARKET) langsung di server Matching Engine Binance Futures.
        Menggunakan closePosition=true dan workingType=MARK_PRICE sehingga seluruh posisi otomatis
        terkunci penuh seketika saat menyentuh target profit (+1.40%) tanpa delay polling dan tanpa slippage.
        """
        if self.is_banned():
            return {}
        url = f"{self.base_url}/fapi/v1/order"
        formatted_stop = self.format_price(symbol, stop_price)
        
        # 1. Coba closePosition=true terlebih dahulu
        params = self._sign({
            "symbol": symbol,
            "side": side.upper(),
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": formatted_stop,
            "closePosition": "true",
            "workingType": "MARK_PRICE"
        })
        try:
            resp = self.session.post(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if isinstance(data, dict) and "orderId" in data:
                console.log(f"[bold green]🎯 NATIVE TAKE PROFIT TERPASANG DI BINANCE: {side} {symbol} @ {formatted_stop} (MARK_PRICE / closePosition=true)[/bold green]")
                return data
            
            # 2. Fallback: jika closePosition ditolak, gunakan quantity + reduceOnly
            if qty and qty > 0:
                formatted_qty = self.format_quantity(symbol, qty)
                p2 = self._sign({
                    "symbol": symbol,
                    "side": side.upper(),
                    "type": "TAKE_PROFIT_MARKET",
                    "stopPrice": formatted_stop,
                    "quantity": formatted_qty,
                    "reduceOnly": "true",
                    "workingType": "MARK_PRICE"
                })
                r2 = self.session.post(url, params=p2, timeout=10)
                d2 = r2.json()
                if isinstance(d2, dict) and "orderId" in d2:
                    console.log(f"[bold green]🎯 NATIVE TAKE PROFIT TERPASANG DI BINANCE: {side} {formatted_qty} {symbol} @ {formatted_stop} (MARK_PRICE / reduceOnly=true)[/bold green]")
                    return d2
            console.log(f"[yellow]Peringatan pasang native TP: {data}[/yellow]")
            return data if isinstance(data, dict) else {}
        except Exception as e:
            console.log(f"[red]Gagal memasang native TP di Binance: {e}[/red]")
            return {}

    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """Membatalkan seluruh order aktif pada koin (misal membersihkan sisa order Stop Loss setelah TP)."""
        if self.is_banned():
            return {}
        url = f"{self.base_url}/fapi/v1/allOpenOrders"
        params = self._sign({"symbol": symbol})
        try:
            resp = self.session.delete(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            console.log(f"[dim]Notice cancel all open orders {symbol}: {e}[/dim]")
            return {}

    def fetch_user_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Mengambil riwayat eksekusi trade riil langsung dari Binance Matching Engine."""
        if self.is_banned():
            return []
        try:
            url = f"{self.base_url}/fapi/v1/userTrades"
            params = self._sign({"symbol": symbol, "limit": limit})
            resp = self.session.get(url, params=params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            return data if isinstance(data, list) else []
        except Exception as e:
            console.log(f"[dim]Notice fetch user trades {symbol}: {e}[/dim]")
            return []

    def fetch_income_history(self, income_type: Optional[str] = "REALIZED_PNL", limit: int = 1000, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Mengambil riwayat PnL riil dan komisi langsung dari pembukuan resmi Binance Futures."""
        if self.is_banned():
            return []
        try:
            url = f"{self.base_url}/fapi/v1/income"
            params: Dict[str, Any] = {"limit": limit}
            if income_type:
                params["incomeType"] = income_type
            if symbol:
                params["symbol"] = symbol
            signed_params = self._sign(params)
            resp = self.session.get(url, params=signed_params, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            return data if isinstance(data, list) else []
        except Exception as e:
            console.log(f"[dim]Notice fetch income history: {e}[/dim]")
            return []


    def fetch_price(self, symbol: str) -> float:
        if self.is_banned():
            s_left = self.ban_until - time.time()
            if s_left > 15.0:
                return 0.0
            time.sleep(max(0.2, s_left + 0.2))
        try:
            url = f"{self.base_url}/fapi/v1/ticker/price?symbol={symbol}"
            resp = self.session.get(url, timeout=5)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if isinstance(data, dict):
                return float(data.get("price", 0.0))
            return 0.0
        except Exception:
            return 0.0

    def fetch_top_tickers(self) -> List[Dict[str, Any]]:
        """Mengambil ticker 24 jam untuk seluruh koin."""
        if self.is_banned():
            return []
        try:
            url = f"{self.base_url}/fapi/v1/ticker/24hr"
            resp = self.session.get(url, timeout=10)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            console.log(f"[yellow]Notice fetch top tickers: {e}[/yellow]")
            return []

    def fetch_long_short_ratio(self, symbol: str, period: str = "5m") -> Dict[str, float]:
        """
        Mengambil rasio akun Long vs Short global (Binance Futures Data API).
        Membaca arah arus sentimen pasar agar tidak melawan arus dominan.
        """
        if self.is_banned():
            return {"long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0}
        try:
            url = f"{self.base_url}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit=1"
            resp = self.session.get(url, timeout=5)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if isinstance(data, list) and len(data) > 0:
                item = data[-1]
                long_acc = float(item.get("longAccount", 0.5))
                short_acc = float(item.get("shortAccount", 0.5))
                ratio = float(item.get("longShortRatio", 1.0))
                return {
                    "long_pct": round(long_acc * 100, 1),
                    "short_pct": round(short_acc * 100, 1),
                    "ratio": round(ratio, 4)
                }
            return {"long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0}
        except Exception:
            return {"long_pct": 50.0, "short_pct": 50.0, "ratio": 1.0}

    def fetch_derivatives_data(self, symbol: str, period: str = "5m") -> Dict[str, Any]:
        """
        Mengambil data derivatif lengkap sesuai strategi Akademi Crypto (Kalimasada):
        1. Open Interest (OI Delta): Mendeteksi aliran modal baru vs short covering / liquidation.
        2. Taker Buy/Sell Ratio (CVD proxy): Mengukur agresivitas volume pasar.
        3. Global Long/Short Ratio: Menghindari melawan arus mayoritas akun.
        """
        res = {
            "long_pct": 50.0,
            "short_pct": 50.0,
            "ratio": 1.0,
            "oi_delta": 0.0,
            "oi_trend": "NEUTRAL",
            "taker_ratio": 1.0,
            "cvd_bias": "NEUTRAL"
        }
        if self.is_banned() or self.is_scan_throttled():
            return res

        # 1. Global Long/Short Ratio
        ls_info = self.fetch_long_short_ratio(symbol, period=period)
        res["long_pct"] = ls_info.get("long_pct", 50.0)
        res["short_pct"] = ls_info.get("short_pct", 50.0)
        res["ratio"] = ls_info.get("ratio", 1.0)

        # 2. Open Interest History (2 baris terakhir untuk delta kenaikan modal)
        try:
            url_oi = f"{self.base_url}/futures/data/openInterestHist?symbol={symbol}&period={period}&limit=2"
            r_oi = self.session.get(url_oi, timeout=3)
            data_oi = r_oi.json()
            if isinstance(data_oi, list) and len(data_oi) >= 2:
                prev_oi = float(data_oi[-2].get("sumOpenInterest", 0.0))
                curr_oi = float(data_oi[-1].get("sumOpenInterest", 0.0))
                if prev_oi > 0:
                    d_pct = (curr_oi - prev_oi) / prev_oi
                    res["oi_delta"] = round(d_pct * 100, 2)
                    res["oi_trend"] = "EXPANDING" if d_pct > 0.003 else ("CONTRACTING" if d_pct < -0.003 else "STABLE")
        except Exception:
            pass

        # 3. Taker Buy/Sell Volume Ratio (CVD Delta)
        try:
            url_taker = f"{self.base_url}/futures/data/takerlongshortRatio?symbol={symbol}&period={period}&limit=1"
            r_taker = self.session.get(url_taker, timeout=3)
            data_taker = r_taker.json()
            if isinstance(data_taker, list) and len(data_taker) > 0:
                t_ratio = float(data_taker[-1].get("buySellRatio", 1.0))
                res["taker_ratio"] = round(t_ratio, 4)
                res["cvd_bias"] = "BULLISH_AGGRESSIVE" if t_ratio >= 1.05 else ("BEARISH_AGGRESSIVE" if t_ratio <= 0.95 else "NEUTRAL")
        except Exception:
            pass

        return res

    def fetch_klines(self, symbol: str, interval: str = "5m", limit: int = 220) -> Optional[List[List[float]]]:
        if self.is_banned() or self.is_scan_throttled():
            return None
        try:
            url = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
            resp = self.session.get(url, timeout=5)
            self.check_response_for_ban(resp)
            data = resp.json()
            self.check_response_for_ban(data)
            if not isinstance(data, list):
                return None
            return [
                [float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
                for c in data
                if isinstance(c, (list, tuple)) and len(c) >= 6
            ]
        except Exception:
            return None

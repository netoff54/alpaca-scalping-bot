import json
import time
import threading
from typing import Dict, Optional, List
from rich.console import Console

console = Console()

class BinanceWebSocketManager:
    """
    Manajer WebSocket Streaming Binance Futures Native USDⓈ-M.
    Mendengarkan push stream live harga ticker seluruh instrumen bursa (!miniTicker@arr)
    sehingga bot memperoleh harga real-time tick-by-tick tanpa memakan kuota REST bursa (Weight = 0).
    Dilengkapi automatic reconnect, keep-alive heartbeat, and multi-endpoint failover.
    """
    def __init__(self, is_banned_fn=None):
        self.is_banned_fn = is_banned_fn
        self.endpoints = [
            "wss://fstream.binance.com/market/ws/!miniTicker@arr",
            "wss://fstream1.binance.com/market/ws/!miniTicker@arr",
            "wss://fstream2.binance.com/market/ws/!miniTicker@arr",
            "wss://fstream3.binance.com/market/ws/!miniTicker@arr"
        ]
        self._current_endpoint_idx = 0
        self.prices: Dict[str, float] = {}
        self.volumes_24h: Dict[str, float] = {}
        self.last_update_time: float = 0.0
        self.is_connected: bool = False
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.total_messages_received: int = 0
        self.reconnect_count: int = 0

    def start(self):
        """Memulai background listener thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BinanceWS-Stream")
        self._thread.start()
        console.log("[bold green]📡 Binance WebSocket Streaming Manager diinisialisasi (Weight = 0)...[/bold green]")

    def stop(self):
        """Menghentikan WebSocket stream."""
        self._running = False

    def is_alive(self) -> bool:
        """Mengecek apakah koneksi WebSocket aktif dan menerima data dalam 15 detik terakhir."""
        return self.is_connected and (time.time() - self.last_update_time < 15.0)

    def get_price(self, symbol: str) -> float:
        """Mengambil harga real-time terkini dari memori (0 request REST ke bursa)."""
        sym = symbol.upper()
        with self._lock:
            return self.prices.get(sym, 0.0)

    def get_24h_volume(self, symbol: str) -> float:
        """Mengambil quote volume 24 jam real-time terkini dari stream WebSocket."""
        sym = symbol.upper()
        with self._lock:
            return self.volumes_24h.get(sym, 0.0)

    def _run_loop(self):
        try:
            import websockets.sync.client
        except ImportError:
            console.log("[bold red]Modul 'websockets' belum terpasang. Jalankan pip install websockets.[/bold red]")
            return

        backoff = 1.0

        while self._running:
            endpoint = self.endpoints[self._current_endpoint_idx]
            try:
                console.log(f"[cyan]📡 Menghubungkan WebSocket Binance Futures: {endpoint}...[/cyan]")
                with websockets.sync.client.connect(
                    endpoint,
                    open_timeout=15,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5
                ) as ws:
                    self.is_connected = True
                    backoff = 1.0
                    console.log("[bold green]✅ WebSocket Binance Futures TERHUBUNG! Menerima stream live ticker 0-weight bursa.[/bold green]")

                    while self._running:
                        try:
                            msg = ws.recv(timeout=15)
                            if not msg:
                                continue
                            data = json.loads(msg)
                            now = time.time()

                            # Handle !miniTicker@arr (array seluruh koin setiap 1 detik)
                            if isinstance(data, list):
                                updated_prices = {}
                                updated_vols = {}
                                for item in data:
                                    if isinstance(item, dict):
                                        s = item.get("s")
                                        c = item.get("c")
                                        q = item.get("q")
                                        if s and c:
                                            try:
                                                updated_prices[s] = float(c)
                                                if q:
                                                    updated_vols[s] = float(q)
                                            except (ValueError, TypeError):
                                                pass
                                if updated_prices:
                                    with self._lock:
                                        self.prices.update(updated_prices)
                                        if updated_vols:
                                            self.volumes_24h.update(updated_vols)
                                        self.last_update_time = now
                                        self.total_messages_received += 1

                            # Handle individual ticker
                            elif isinstance(data, dict):
                                s = data.get("s")
                                c = data.get("c") or data.get("p")
                                q = data.get("q")
                                if s and c:
                                    with self._lock:
                                        self.prices[s] = float(c)
                                        if q:
                                            self.volumes_24h[s] = float(q)
                                        self.last_update_time = now
                                        self.total_messages_received += 1

                        except TimeoutError:
                            # Jika tidak ada pesan selama 25 detik, reconnect
                            if time.time() - self.last_update_time > 25.0:
                                console.log("[yellow]WebSocket timeout 25s tanpa data, mereconnect...[/yellow]")
                                break
                        except Exception as e_recv:
                            console.log(f"[dim]WebSocket recv notice: {e_recv}[/dim]")
                            break

            except Exception as e_conn:
                self.is_connected = False
                self.reconnect_count += 1
                console.log(f"[yellow]Koneksi WebSocket terputus ({e_conn}). Merotasi gateway failover dalam {backoff:.1f}s...[/yellow]")
                self._current_endpoint_idx = (self._current_endpoint_idx + 1) % len(self.endpoints)
                time.sleep(backoff)
                backoff = min(15.0, backoff * 1.5)
            finally:
                self.is_connected = False

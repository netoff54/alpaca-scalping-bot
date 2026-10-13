import os
import requests
from typing import Dict, Any, List, Optional
from config import config

class AlpacaClient:
    """Client ringan untuk Alpaca Paper Trading API v2 menggunakan requests."""
    def __init__(self, key_id: Optional[str] = None, secret_key: Optional[str] = None, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("ALPACA_BASE_URL") or "https://paper-api.alpaca.markets/v2").rstrip('/')
        # Data URL untuk crypto
        self.data_url = "https://data.alpaca.markets/v1beta3/crypto"
        self.key_id = key_id or os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY", "")

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.key_id and self.secret_key)

    def get_account(self) -> Dict[str, Any]:
        """Mengambil informasi akun Alpaca (equity, cash, buying power)."""
        url = f"{self.base_url}/account"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_positions(self) -> List[Dict[str, Any]]:
        """Mengambil posisi terbuka di Alpaca."""
        url = f"{self.base_url}/positions"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Mengambil daftar limit order yang masih pending."""
        url = f"{self.base_url}/orders"
        params = {"status": "open"}
        if symbol:
            params["symbols"] = symbol
        response = requests.get(url, headers=self.headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def create_limit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        limit_price: float,
        time_in_force: str = "gtc"
    ) -> Dict[str, Any]:
        """
        Membuat LIMIT ORDER di Alpaca.
        Selalu menggunakan tipe Limit Order untuk menjamin eksekusi Maker dan menghindari slippage.
        """
        url = f"{self.base_url}/orders"
        # Format harga dan jumlah sesuai presisi
        payload = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side.lower(),
            "type": "limit",
            "time_in_force": time_in_force,
            "limit_price": str(round(limit_price, 2))
        }

        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        if response.status_code not in (200, 201):
            raise Exception(f"Alpaca Order Error ({response.status_code}): {response.text}")
        return response.json()

    def cancel_order(self, order_id: str) -> bool:
        """Membatalkan order berdasarkan order ID (untuk order timeout)."""
        url = f"{self.base_url}/orders/{order_id}"
        response = requests.delete(url, headers=self.headers, timeout=10)
        return response.status_code in (200, 204)

    def close_all_positions(self) -> List[Dict[str, Any]]:
        """Menutup semua posisi darurat."""
        url = f"{self.base_url}/positions"
        response = requests.delete(url, headers=self.headers, timeout=10)
        return response.json()

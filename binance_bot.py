import os
import time
import math
import threading
import gc
from typing import Dict, Any, List, Optional, Set, Tuple
from rich.console import Console

from config import config
import strategy
from binance_client import BinanceFuturesClient
from database import db

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
        
        # Klien REST API Binance Futures Native (Zero CCXT overhead)
        self.client = BinanceFuturesClient(self.api_key, self.api_secret)
        
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
        
        # Cache Semesta 500 koin crypto murni & Sistem Rotasi 1 Koin Per Siklus
        self._cached_universe_symbols: List[Dict[str, Any]] = []
        self._last_universe_refresh: float = 0.0
        self._current_rotation_index: int = 0
        self.current_rotation_info: str = "Rotasi 1/500 (Menyiapkan Analisis)"
        self.current_coin_analysis: Dict[str, Any] = {}
        self._coins_analysis_history: Dict[str, Dict[str, Any]] = {}
        self._last_wallet_db_snapshot: float = 0.0
        
        # Balance cache & Rate limit cooldown
        self._cached_balance: Dict[str, float] = {"total_wallet": 0.0, "available": 0.0, "unrealized_pnl": 0.0}
        self._last_balance_time: float = 0.0
        self._last_sync_position_time: float = 0.0
        self._configured_symbols: Set[str] = set()
        self._last_reversal_check_time: float = 0.0
        self.last_error: Optional[str] = None
        self._symbol_order_cooldown: Dict[str, float] = {}
        
        # Muat riwayat transaksi kumulatif dari Neon Tech agar tidak reset saat restart/redeploy
        self.load_history_from_db()

    def load_history_from_db(self):
        """Memuat riwayat transaksi kumulatif dari Neon Tech agar statistik tidak reset dari 0 saat restart/redeploy."""
        try:
            summary = db.get_trade_summary()
            self.total_trades = summary.get("total_trades", 0)
            self.winning_trades = summary.get("winning_trades", 0)
            self.total_pnl_usd = summary.get("total_pnl_usd", 0.0)
            self.trade_history = db.get_recent_trades(50)
            console.log(f"[bold green]Riwayat database Neon Tech dimuat: {self.total_trades} trade kumulatif ({self.winning_trades} win, Total PnL: +${self.total_pnl_usd:.4f} USDT)[/bold green]")
        except Exception as e:
            console.log(f"[dim]DB load history notice: {e}[/dim]")

    @property
    def _ban_until(self) -> float:
        return self.client.ban_until

    @_ban_until.setter
    def _ban_until(self, val: float):
        self.client.ban_until = val

    def get_futures_balance(self, max_age_sec: float = 60.0) -> Dict[str, float]:
        """Mengambil saldo wallet USDⓈ-M Futures dengan caching 60 detik."""
        now = time.time()
        if self.client.is_banned():
            return self._cached_balance

        if now - self._last_balance_time < max_age_sec and self._cached_balance["total_wallet"] > 0:
            return self._cached_balance

        try:
            bal = self.client.get_balance()
            self._cached_balance = bal
            self._last_balance_time = now
            self.last_error = None
            return self._cached_balance
        except Exception as e:
            err_msg = str(e)
            self.last_error = f"Balance status: {err_msg}"
            self._last_balance_time = now + 15
            return self._cached_balance

    def sync_exchange_position(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Sinkronisasi otomatis dengan posisi terbuka langsung dari Binance.
        Dibatasi minimal 20 detik agar tidak membebani signed authenticated endpoint.
        """
        now = time.time()
        if self.client.is_banned():
            return self.active_position

        # Throttling 20 detik jika posisi sudah tercatat
        if not force and (now - self._last_sync_position_time < 20.0) and self.active_position is not None:
            return self.active_position

        try:
            self._last_sync_position_time = now
            open_pos = self.client.get_open_positions()
            if self.client.is_banned():
                return self.active_position

            if open_pos:
                pos = open_pos[0]
                symbol = pos.get("symbol", "")
                contracts = abs(pos.get("amount", 0.0))
                side = "buy" if pos.get("amount", 0.0) > 0 else "sell"
                entry_price = pos.get("entry_price", 0.0)
                notional = contracts * entry_price
                
                # Pertahankan SL/TP target dan status BEP
                if self.active_position and self.active_position.get("symbol") == symbol:
                    sl_price = self.active_position.get("sl_price", entry_price * (1.0 - config.SL_PERCENT if side == "buy" else 1.0 + config.SL_PERCENT))
                    tp_price = self.active_position.get("tp_price", entry_price * (1.0 + config.TP_PERCENT if side == "buy" else 1.0 - config.TP_PERCENT))
                    bep_trigger_price = self.active_position.get("bep_trigger_price", entry_price * (1.0 + config.BEP_PROFIT_TRIGGER if side == "buy" else 1.0 - config.BEP_PROFIT_TRIGGER))
                    bep_activated = self.active_position.get("bep_activated", False)
                    opened_at = self.active_position.get("opened_at", time.time())
                    pos_leverage = self.active_position.get("leverage", int(pos.get("leverage", config.LEVERAGE)))
                else:
                    sl_price = entry_price * (1.0 - config.SL_PERCENT) if side == "buy" else entry_price * (1.0 + config.SL_PERCENT)
                    tp_price = entry_price * (1.0 + config.TP_PERCENT) if side == "buy" else entry_price * (1.0 - config.TP_PERCENT)
                    bep_trigger_price = entry_price * (1.0 + config.BEP_PROFIT_TRIGGER) if side == "buy" else entry_price * (1.0 - config.BEP_PROFIT_TRIGGER)
                    bep_activated = False
                    opened_at = time.time()
                    pos_leverage = int(pos.get("leverage", config.LEVERAGE))
                
                self.active_position = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "qty": contracts,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "bep_trigger_price": bep_trigger_price,
                    "bep_activated": bep_activated,
                    "opened_at": opened_at,
                    "notional": notional,
                    "leverage": pos_leverage
                }
                return self.active_position
            else:
                # Pastikan tidak dalam cooldown sebelum menyatakan posisi telah tertutup
                if not self.client.is_banned() and self.active_position is not None:
                    closed_pos = self.active_position
                    sym = closed_pos.get("symbol")
                    console.log(f"[bold yellow]Posisi {sym} telah selesai/tertutup di Binance (Eksekusi Native Stop Loss / BEP Bursa).[/bold yellow]")
                    self.client.cancel_all_open_orders(sym)
                    
                    entry_p = float(closed_pos.get("entry_price", 0.0))
                    exit_hint = float(closed_pos.get("sl_price", entry_p))
                    self._record_closed_position(closed_pos, exit_price_hint=exit_hint, result_hint="WIN")
                    return None
                return None
        except Exception as e:
            console.log(f"[dim]Sync position check: {e}[/dim]")
            return self.active_position

    def _record_closed_position(self, closed_pos: Dict[str, Any], exit_price_hint: float, result_hint: str = "WIN") -> Dict[str, Any]:
        """
        Merekam trade yang selesai dengan data riil langsung dari Binance API:
        1. Mengambil harga eksekusi riil dari userTrades (menghilangkan selisih slippage).
        2. Mengambil realized PnL riil dan ID trade resmi dari income history.
        3. Menjamin leverage dan margin_used tercatat akurat (maks 20x untuk akun baru).
        4. Menyimpan ke database Neon dan memperbarui agregat portofolio.
        """
        sym = closed_pos.get("symbol", "")
        entry_p = float(closed_pos.get("entry_price", 0.0))
        c_side = closed_pos.get("side", "buy").lower()
        c_notional = float(closed_pos.get("notional", 0.0))
        c_qty = float(closed_pos.get("qty", 0.0))
        # Ambil leverage riil (rentang 20x s/d 50x)
        c_lev = int(closed_pos.get("leverage") or self.client.get_max_leverage(sym))
        c_lev = max(config.LEVERAGE_MIN, min(c_lev, config.LEVERAGE_MAX))

        real_exit_price = exit_price_hint
        real_pnl_usd = None
        real_commission = 0.0
        binance_trade_id = None

        # 1. Coba ambil data riil eksekusi bursa
        try:
            incomes = self.client.fetch_income_history(income_type="REALIZED_PNL", limit=5, symbol=sym)
            if incomes:
                latest_inc = incomes[-1]
                real_pnl_usd = float(latest_inc.get("income", 0.0))
                binance_trade_id = str(latest_inc.get("tradeId", ""))
        except Exception as e_inc:
            console.log(f"[dim]Notice fetch income PnL: {e_inc}[/dim]")

        try:
            user_trades = self.client.fetch_user_trades(sym, limit=5)
            if user_trades:
                closing_trades = [t for t in user_trades if t.get("side", "").lower() != c_side]
                target_t = closing_trades[-1] if closing_trades else user_trades[-1]
                real_exit_price = float(target_t.get("price", exit_price_hint))
                real_commission = sum(float(t.get("commission", 0.0)) for t in closing_trades) if closing_trades else float(target_t.get("commission", 0.0))
                if not binance_trade_id and target_t.get("id"):
                    binance_trade_id = str(target_t.get("id"))
        except Exception as e_ut:
            console.log(f"[dim]Notice fetch user trades: {e_ut}[/dim]")

        # 2. Fallback jika Binance API dalam jeda cooldown
        if real_pnl_usd is None:
            pct = ((real_exit_price - entry_p) / entry_p) if c_side == "buy" else ((entry_p - real_exit_price) / entry_p)
            real_pnl_usd = pct * c_notional
            real_pnl_pct = pct * 100
        else:
            real_pnl_pct = (real_pnl_usd / c_notional * 100) if c_notional > 0 else 0.0

        res = "WIN" if real_pnl_usd >= 0.0 else "LOSS"
        margin_used = round((c_notional / c_lev) if c_lev > 0 else (c_notional / 20.0), 4)

        trade_record = {
            "symbol": sym,
            "side": c_side.upper(),
            "entry_price": entry_p,
            "exit_price": real_exit_price,
            "qty": c_qty,
            "notional": c_notional,
            "margin_used": margin_used,
            "leverage": c_lev,
            "commission": round(real_commission, 6),
            "binance_trade_id": binance_trade_id,
            "pnl_usd": round(real_pnl_usd, 4),
            "pnl_pct": round(real_pnl_pct, 2),
            "result": res,
            "closed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            self.trade_history.append(trade_record)
            db.record_trade(trade_record)
            self.total_trades += 1
            if real_pnl_usd >= 0.0:
                self.winning_trades += 1
            self.total_pnl_usd += real_pnl_usd
            console.log(f"[bold green]✅ Trade {sym} berhasil tercatat 100% akurat dari bursa: PnL ${real_pnl_usd:+.4f} ({real_pnl_pct:+.2f}%), Exit: {real_exit_price}, Lev: {c_lev}x[/bold green]")
        except Exception as e_rec:
            console.log(f"[red]Error mencatat trade ke database: {e_rec}[/red]")

        self.active_position = None
        return trade_record

    def sync_historical_database_with_binance(self) -> Dict[str, Any]:
        """Menyelaraskan seluruh riwayat database dengan rekaman resmi bursa Binance."""
        if self.client.is_banned():
            return {"status": "skipped", "reason": "rate_limited"}
        try:
            console.log("[cyan]Memulai sinkronisasi seluruh riwayat database dengan data riil Binance...[/cyan]")
            incomes = self.client.fetch_income_history(income_type="REALIZED_PNL", limit=1000)
            res = db.sync_all_historical_trades_with_binance(incomes)
            if res.get("status") == "success":
                self.total_trades = res["total_trades"]
                self.winning_trades = res["winning_trades"]
                self.total_pnl_usd = res["total_pnl_usd"]
                console.log(f"[bold green]Sinkronisasi riwayat database sukses: {res.get('matched_trades', 0)} trade dicocokkan, Total PnL: ${res.get('total_pnl_usd', 0.0):+.4f}[/bold green]")
            return res
        except Exception as e:
            console.log(f"[red]Error sinkronisasi database dengan Binance: {e}[/red]")
            return {"status": "error", "error": str(e)}

    def get_compounded_notional(self) -> float:
        """
        Menghitung ukuran notional posisi berdasarkan aturan margin bertingkat:
        - Saldo < $100: gunakan margin tepat $1.00 (Maksimal ketat $1.00)
        - Saldo >= $100: gunakan 1.0% margin fleksibel dari total saldo (Compounding)
        """
        bal = self.get_futures_balance()
        avail = bal["available"]
        base_wallet = avail if avail >= 1.0 else config.DEFAULT_CAPITAL
        
        if base_wallet < config.BALANCE_THRESHOLD_SCALING:
            target_margin = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $1.00
        else:
            target_margin = base_wallet * config.RISK_PORTFOLIO_PERCENT  # 1.0% fleksibel

        raw_notional = target_margin * config.LEVERAGE
        notional = raw_notional
        if base_wallet < config.BALANCE_THRESHOLD_SCALING:
            notional = min(notional, config.MAX_ORDER_NOTIONAL)
        return round(notional, 2)

    def _get_fallback_symbols(self) -> List[Dict[str, Any]]:
        """Daftar koin likuid teratas bawaan jika API publik bursa sedang dalam cooldown."""
        top_fallback = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "NEARUSDT", "APTUSDT", "TAOUSDT", "DOTUSDT", "FILUSDT",
            "WLDUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "FETUSDT", "RENDERUSDT", "TIAUSDT",
            "SEIUSDT", "ENAUSDT", "PEPEUSDT", "SHIBUSDT", "BONKUSDT", "WIFUSDT", "FLOKIUSDT"
        ]
        return [{"symbol": s, "quoteVolume": 1000000000.0} for s in top_fallback]

    def _fetch_universe_symbols(self) -> List[Dict[str, Any]]:
        """
        Mengambil Semesta 200 Koin Crypto Murni (Non-Stablecoin) Langsung dari Binance Futures:
        1. Buang semua stablecoin (USDC, FDUSD, BUSD, TUSD, EUR, DAI, AEUR, USDP, USD1, BFUSD, USDT, USTC, dll).
        2. Hanya koin yang terdaftar di self.client.allowed_crypto_symbols.
        3. Filter koin dengan volume 24 jam >= config.MIN_24H_VOLUME_USD ($3M).
        4. Saring koin yang minimum order-nya terlalu besar untuk modal mikro ($11 USDT).
        5. Urutkan berdasarkan quoteVolume tertinggi dan ambil tepat 200 koin crypto murni.
        """
        if self.client.is_banned():
            return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()

        try:
            data = self.client.fetch_top_tickers()
            if not isinstance(data, list):
                return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()

            stablecoin_symbols = {
                "USDCUSDT", "FDUSDUSDT", "BUSDUSDT", "TUSDUSDT", "EURUSDT", "DAIUSDT", "AEURUSDT",
                "USDPUSDT", "USD1USDT", "BFUSDUSDT", "USDTUSDT", "USTCUSDT", "EURIUSDT", "USDEUSDT",
                "USDJUSDT", "XAUTUSDT", "PAXGUSDT"
            }

            filtered = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                sym = item.get("symbol", "")
                if sym not in self.client.allowed_crypto_symbols or sym in stablecoin_symbols:
                    continue
                if any(sym.startswith(sc) for sc in ("USDC", "FDUSD", "BUSD", "TUSD", "EUR", "DAI", "AEUR", "USDP", "USD1", "BFUSD")):
                    continue
                try:
                    q_vol = float(item.get("quoteVolume", 0.0))
                    last_price = float(item.get("lastPrice", 0.0))
                    if q_vol < config.MIN_24H_VOLUME_USD or last_price <= 0:
                        continue

                    # Filter koin dengan ukuran lot minimum terlalu besar untuk akun modal mikro ($11 USDT)
                    rules = self.client._symbols_rules.get(sym, {})
                    min_q = rules.get("min_qty", 0.0)
                    if (min_q * last_price) > config.MAX_ORDER_NOTIONAL:
                        continue

                    # Filter koin dengan leverage maksimal < 20x (misal AVAUSDT 10x) agar semesta 500 koin hanya berisi koin likuid & seragam
                    max_sym_lev = self.client.get_max_leverage(sym)
                    if max_sym_lev < config.LEVERAGE_MIN:
                        continue

                    # Filter jika koin tidak bisa mencapai minimum order ($5.00) dengan margin yang diizinkan
                    bal_avail = self._cached_balance.get("available", 0.0)
                    active_margin = config.FIXED_MARGIN_LOW_BALANCE if bal_avail < config.BALANCE_THRESHOLD_SCALING else (bal_avail * config.RISK_PORTFOLIO_PERCENT)
                    if (active_margin * max_sym_lev) < config.MIN_NOTIONAL:
                        continue

                    filtered.append({
                        "symbol": sym,
                        "quoteVolume": q_vol
                    })
                except Exception:
                    continue

            # Urutkan berdasarkan volume 24 jam tertinggi
            filtered.sort(key=lambda x: x["quoteVolume"], reverse=True)
            res = filtered[:config.SCAN_UNIVERSE_LIMIT]
            if res:
                console.log(f"[bold green]Berhasil memuat {len(res)} koin crypto murni (non-stablecoin) ke dalam semesta rotasi.[/bold green]")
                return res
            return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()
        except Exception as e:
            console.log(f"[yellow]Notice fetch universe tickers: {e}[/yellow]")
            return self._cached_universe_symbols if self._cached_universe_symbols else self._get_fallback_symbols()

    def scan_top_coins(self):
        """
        Memindai semesta koin (hingga 500 koin) dengan sistem rotasi 1 koin per siklus:
        - 1 koin dianalisis secara komprehensif & mendalam (Multi-Timeframe 15m + 5m)
        - Pemetaan Area Likuidasi (Liquidation Pools Long & Short)
        - Deteksi Reaksi Price Action & Liquidity Sweep Reclaim
        - Struktur Pasar (HH/HL vs LH/LL) & S&R Teruji >= 2 kali
        - Retest EMA 13 & 21 5m, Volume Expansion, Open Interest, & CVD Taker Delta
        - Sebanyak 500 rotasi berturut-turut untuk menyisir seluruh koin tanpa screening singkat.
        """
        if self.client.is_banned() or self.client.is_scan_throttled():
            return
        t_start = time.time()
        try:
            now = time.time()
            if not self._cached_universe_symbols or (now - self._last_universe_refresh > 900):
                self._cached_universe_symbols = self._fetch_universe_symbols()
                self._last_universe_refresh = now
                gc.collect()

            universe = self._cached_universe_symbols
            if not universe:
                return

            total_univ = len(universe)
            rot_idx = self._current_rotation_index % total_univ
            item = universe[rot_idx]
            sym = item["symbol"]
            q_vol = item["quoteVolume"]
            rank = rot_idx + 1

            self.current_rotation_info = f"Rotasi {rank}/{total_univ} (Analisis Menyeluruh: {sym})"

            bal = self.get_futures_balance()
            cap = bal["available"] if bal["available"] >= 1.0 else config.DEFAULT_CAPITAL

            # 1. Fetch Multi-Timeframe: 15m untuk Struktur & Area Likuidasi, 5m untuk Eksekusi Scalp
            ohlcv_15m = self.client.fetch_klines(sym, interval=config.STRUCTURE_TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.08)
            ohlcv_5m = self.client.fetch_klines(sym, interval=config.TIMEFRAME, limit=config.CANDLE_LIMIT)
            time.sleep(0.08)
            deriv_data = self.client.fetch_derivatives_data(sym, period="5m")

            if not ohlcv_5m or len(ohlcv_5m) < 25:
                self._current_rotation_index = (self._current_rotation_index + 1) % total_univ
                return

            # 2. Analisis Menyeluruh Sesuai Master Blueprint Akademi Crypto
            max_sym_lev = self.client.get_max_leverage(sym)
            analysis = strategy.analyze_coin_comprehensive(
                symbol=sym,
                ohlcv_htf=ohlcv_15m,
                ohlcv_ltf=ohlcv_5m,
                derivatives_data=deriv_data,
                available_capital=cap,
                leverage=config.LEVERAGE,
                max_symbol_leverage=max_sym_lev
            )
            analysis["rank"] = rank
            analysis["vol_24h_m"] = round(q_vol / 1_000_000, 2)

            self.current_coin_analysis = analysis
            self._coins_analysis_history[sym] = analysis

            # Perbarui ranked pairs dari histori koin yang telah dianalisis (50 koin aktif terakhir)
            self.ranked_pairs = list(self._coins_analysis_history.values())[-50:]
            self.bullish_count = sum(1 for r in self.ranked_pairs if r.get("trend_bias") == "BULLISH")
            self.bearish_count = sum(1 for r in self.ranked_pairs if r.get("trend_bias") == "BEARISH")

            # Perbarui Watchlist berdasarkan skor kualitas & kedekatan dengan pool likuidasi
            sorted_by_score = sorted(
                self._coins_analysis_history.values(),
                key=lambda x: (x.get("score", 0), -x.get("liquidation_pools", {}).get("nearest_pool_distance_pct", 99.0)),
                reverse=True
            )
            self.watchlist = sorted_by_score[:8]

            # 3. Evaluasi Sinyal Eksekusi
            sig = analysis.get("signal")
            if sig is not None and sig.get("score", 0) >= config.MIN_SETUP_SCORE:
                console.log(f"[bold green]🎯 SETUP DITEMUKAN PADA {sym}! {sig['setup_name']} (Skor: {sig['score']})[/bold green]")
                existing_syms = [s["symbol"] for s in self.active_signals]
                if sym not in existing_syms:
                    sig_entry = sig.copy()
                    sig_entry["rank"] = rank
                    sig_entry["vol_24h_m"] = round(q_vol / 1_000_000, 2)
                    self.active_signals.insert(0, sig_entry)
                    self.active_signals = self.active_signals[:8]
                    db.record_signals([sig_entry])

                # Eksekusi jika tidak ada posisi atau order aktif
                if not self.active_position and not self.active_order and not self.client.is_banned():
                    self.execute_limit_order(sig)

            self.last_scan_duration_sec = round(time.time() - t_start, 2)
            self.last_scan_time = time.strftime("%Y-%m-%d %H:%M:%S")

            # Maju ke rotasi berikutnya
            self._current_rotation_index = (self._current_rotation_index + 1) % total_univ
            
            # Snapshot saldo ke Neon Tech secara berkala (setiap 1 jam agar hemat kuota compute)
            if now - self._last_wallet_db_snapshot > 3600:
                db.record_wallet_snapshot(
                    total_wallet=bal["total_wallet"],
                    available=bal["available"],
                    unpnl=bal["unrealized_pnl"],
                    trade_size=self.get_compounded_notional(),
                    margin_pct=config.RISK_PORTFOLIO_PERCENT * 100
                )
                self._last_wallet_db_snapshot = now
            
        except Exception as e:
            console.log(f"[red]Error dalam pemindaian koin: {e}[/red]")
        finally:
            gc.collect()

    def execute_limit_order(self, sig: Dict[str, Any]) -> bool:
        """Mengeksekusi Limit Order (Maker only / timeInForce=GTX) dengan timeout 30 detik."""
        symbol = sig["symbol"]
        side = "BUY" if sig["side"] == "BUY" else "SELL"
        target_price = sig["entry_price"]

        now = time.time()
        cooldown_until = self._symbol_order_cooldown.get(symbol, 0.0)
        if now < cooldown_until:
            rem = int(cooldown_until - now)
            console.log(f"[yellow]Koin {symbol} dalam jeda cooldown ({rem}s lagi setelah auto-cancel). Melewati agar tidak spam berulang.[/yellow]")
            return False
        
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        if base in TRADFI_EXCLUSIONS:
            console.log(f"[yellow]Melewati order pada {symbol} (Aset TradFi).[/yellow]")
            return False

        try:
            # 1. Pastikan ISOLATED margin dan atur leverage dalam rentang 50x turun ke 20x
            self.client.set_margin_type(symbol, "ISOLATED")
            actual_leverage = self.client.set_leverage(
                symbol,
                target_leverage=config.LEVERAGE_MAX,
                min_leverage=config.LEVERAGE_MIN
            )
            self._configured_symbols.add(symbol)
            
            # Saring koin dengan leverage di bawah 20x agar seluruh trade seragam & tidak timpang
            if actual_leverage < config.LEVERAGE_MIN:
                console.log(
                    f"[bold yellow]🛡️ Filter Leverage Rendah: {symbol} hanya mendukung {actual_leverage}x (< {config.LEVERAGE_MIN}x). "
                    f"Melewati koin agar seluruh trade tetap seimbang, seragam, dan likuid.[/bold yellow]"
                )
                self.active_order = None
                self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                self._symbol_order_cooldown[symbol] = time.time() + 600
                return False

            # Hitung target margin sesuai portofolio terkini
            bal = self.get_futures_balance()
            avail = bal["available"] if bal["available"] >= 1.0 else config.DEFAULT_CAPITAL
            if avail < config.BALANCE_THRESHOLD_SCALING:
                target_margin = config.FIXED_MARGIN_LOW_BALANCE  # Tepat $1.00 jika saldo < $100
                max_margin_cap = config.MAX_MARGIN_LOW_BALANCE   # Batas maksimal ketat $1.00 jika saldo < $100
            else:
                target_margin = avail * config.RISK_PORTFOLIO_PERCENT  # 1.0% fleksibel compounding jika saldo >= $100
                max_margin_cap = target_margin * 1.08  # Toleransi 8% untuk presisi lot size

            target_notional = target_margin * actual_leverage

            # CEK KETAT: Jika nilai notional di bawah batas minimum Binance ($5.00),
            # JANGAN buka posisi dan LEWATI koin sesuai instruksi pengguna!
            if target_notional < config.MIN_NOTIONAL:
                console.log(
                    f"[bold yellow]🛡️ Minimal order tidak tercapai: {symbol} pada leverage {actual_leverage}x "
                    f"dengan margin ${target_margin:.2f} menghasilkan notional ${target_notional:.2f} "
                    f"(di bawah batas minimum ${config.MIN_NOTIONAL:.2f}). Melewati koin sesuai instruksi.[/bold yellow]"
                )
                self.active_order = None
                self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                self._symbol_order_cooldown[symbol] = time.time() + 600
                return False

            # 2. Ambil best bid/ask untuk harga Maker
            depth = self.client.fetch_best_bid_ask(symbol)
            if side == "BUY":
                best_price = depth["bid"] if depth.get("bid", 0.0) > 0 else target_price
            else:
                best_price = depth["ask"] if depth.get("ask", 0.0) > 0 else target_price
                
            formatted_price = self.client.format_price(symbol, best_price)
            if formatted_price <= 0:
                formatted_price = self.client.format_price(symbol, target_price)
            
            # 3. Hitung qty dengan presisi tepat
            formatted_qty = self.client.calculate_order_qty(symbol, target_notional, formatted_price)
            
            if formatted_qty <= 0:
                console.log(f"[red]Ukuran order terlalu kecil untuk {symbol}[/red]")
                return False
                
            effective_notional = formatted_qty * formatted_price
            margin_used = effective_notional / actual_leverage

            # Jika margin_used sedikit melebihi cap akibat pembulatan lot size (math.ceil),
            # coba turunkan 1 step lot size jika notional tetap >= MIN_NOTIONAL ($5.00)
            rules = self.client._symbols_rules.get(symbol, {})
            step = rules.get("step_size", 0.0)
            if margin_used > (max_margin_cap + 0.005) and step > 0:
                reduced_qty = self.client.format_qty(symbol, formatted_qty - step)
                if (reduced_qty * formatted_price) >= config.MIN_NOTIONAL:
                    formatted_qty = reduced_qty
                    effective_notional = formatted_qty * formatted_price
                    margin_used = effective_notional / actual_leverage

            # Filter ketat batas maksimal margin per posisi
            # Saldo < $100: Maksimal ketat $1.00 (tidak boleh lebih dari $1.00)
            # Saldo >= $100: Fleksibel 1.0% dari saldo (maks target_margin * 1.08)
            if margin_used > (max_margin_cap + 0.005):
                console.log(
                    f"[bold yellow]🛡️ Filter Margin Ketat: Margin terhitung ${margin_used:.2f} melebihi batas maksimal "
                    f"${max_margin_cap:.2f} untuk {symbol}. Melewati koin agar modal tetap aman.[/bold yellow]"
                )
                return False

            max_allowed_notional = config.MAX_ORDER_NOTIONAL if avail < config.BALANCE_THRESHOLD_SCALING else max(config.MAX_ORDER_NOTIONAL, target_notional * 1.5)
            if effective_notional > max_allowed_notional:
                console.log(f"[bold yellow]🛡️ Filter Ukuran Akun: Minimum order {symbol} bernilai ${effective_notional:.2f} (Margin: ${margin_used:.2f}). Melewati agar margin tetap aman (Maks Notional: ${max_allowed_notional:.2f}).[/bold yellow]")
                return False

            if effective_notional < config.MIN_NOTIONAL:
                console.log(f"[bold yellow]🛡️ Notional terhitung ${effective_notional:.2f} < ${config.MIN_NOTIONAL:.2f}. Melewati {symbol} agar margin tetap sesuai aturan.[/bold yellow]")
                return False

            console.log(f"[bold cyan]Dispatching Maker Limit Order (Risk: ${sig.get('risk_usd', 0.05):.3f}, Leverage: {actual_leverage}x): {side} {formatted_qty} {symbol} @ {formatted_price} (Notional: ${effective_notional:.2f}, Margin: ${margin_used:.2f})[/bold cyan]")
            
            order = self.client.create_limit_order(
                symbol=symbol,
                side=side,
                qty=formatted_qty,
                price=formatted_price
            )
            
            order_id = order.get("orderId")
            self.active_order = {
                "id": order_id,
                "symbol": symbol,
                "side": side.lower(),
                "price": formatted_price,
                "qty": formatted_qty,
                "sl_price": sig["sl_price"],
                "tp_price": sig["tp_price"],
                "bep_trigger_price": sig.get("bep_trigger_price", 0.0),
                "leverage": actual_leverage,
                "risk_usd": sig.get("risk_usd", 0.05),
                "reward_usd": sig.get("reward_usd", 0.10),
                "placed_at": time.time()
            }
            
            # 4. Loop Pemantauan 30 Detik (Anti-FOMO Auto-Cancel)
            console.log(f"[yellow]Menunggu limit order terisi (maks 30 detik)...[/yellow]")
            t_start = time.time()
            while time.time() - t_start < config.LIMIT_TIMEOUT_SECONDS:
                time.sleep(2)
                try:
                    chk = self.client.get_order(symbol, order_id)
                    status = chk.get("status")
                    if status == "FILLED":
                        console.log(f"[bold green]LIMIT ORDER TERISI PENUH! ({symbol} @ {formatted_price})[/bold green]")
                        
                        # 1. Pasang Native Stop Loss (STOP_MARKET) langsung di Matching Engine Binance
                        sl_side = "SELL" if side.lower() == "buy" else "BUY"
                        native_sl = self.client.create_stop_loss_order(
                            symbol=symbol,
                            side=sl_side,
                            stop_price=sig["sl_price"],
                            qty=formatted_qty
                        )
                        native_sl_id = native_sl.get("orderId") if isinstance(native_sl, dict) else None

                        self.active_position = {
                            "symbol": symbol,
                            "side": side.lower(),
                            "entry_price": formatted_price,
                            "qty": formatted_qty,
                            "sl_price": sig["sl_price"],
                            "tp_price": sig["tp_price"],
                            "bep_trigger_price": sig.get("bep_trigger_price", 0.0),
                            "bep_activated": False,
                            "native_sl_order_id": native_sl_id,
                            "leverage": actual_leverage,
                            "risk_usd": sig.get("risk_usd", 0.05),
                            "reward_usd": sig.get("reward_usd", 0.10),
                            "opened_at": time.time(),
                            "notional": formatted_qty * formatted_price
                        }
                        self.active_order = None
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                        return True
                    elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                        console.log(f"[yellow]Order dibatalkan/ditolak ({status}).[/yellow]")
                        self.active_order = None
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
                        self._symbol_order_cooldown[symbol] = time.time() + 300
                        return False
                except Exception as err:
                    console.log(f"[dim]Pengecekan order {order_id}: {err}[/dim]")
                    
            console.log(f"[bold yellow]Limit order tidak terisi dalam 30 detik. Auto-cancel {order_id} (Anti-FOMO)...[/bold yellow]")
            try:
                self.client.cancel_order(symbol, order_id)
            except Exception as e:
                console.log(f"[dim]Gagal cancel order: {e}[/dim]")
                
            self.active_order = None
            self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
            self._symbol_order_cooldown[symbol] = time.time() + 300  # Cooldown 5 menit agar tidak spam berulang
            return False
            
        except Exception as e:
            console.log(f"[red]Gagal dispatch limit order: {e}[/red]")
            self.active_order = None
            self.active_signals = [s for s in self.active_signals if s.get("symbol") != symbol]
            self._symbol_order_cooldown[symbol] = time.time() + 180
            return False

    def execute_maker_close(self, symbol: str, side: str, qty: float, target_price: float, is_emergency: bool = False) -> Tuple[bool, float]:
        """
        Menutup posisi menggunakan Maker Limit Order (timeInForce=GTX / Post Only) agar fee terendah (0.02%).
        - Jika is_emergency=True (Stop Loss atau BEP terpicu): pantau maksimal 1.5s agar tidak terkena slippage.
        - Jika Take Profit normal (is_emergency=False): pantau hingga 6s di antrean teratas.
        Fallback otomatis ke market order untuk menjamin kepastian penutupan posisi seketika.
        Mengembalikan (sukses: bool, actual_exit_price: float).
        """
        try:
            depth = self.client.fetch_best_bid_ask(symbol)
            rules = self.client._symbols_rules.get(symbol, {})
            tick = rules.get("tick_size", 0.0001)

            if side == "SELL":
                best_ask = depth.get("ask", 0.0)
                limit_price = max(best_ask, target_price) if best_ask > 0 else target_price
            else:
                best_bid = depth.get("bid", 0.0)
                limit_price = min(best_bid, target_price) if best_bid > 0 else target_price

            formatted_price = self.client.format_price(symbol, limit_price)
            console.log(f"[bold cyan]Mengirim Maker Limit Close: {side} {qty} {symbol} @ {formatted_price} (Post-Only GTX)...[/bold cyan]")

            res = self.client.create_limit_close_order(symbol, side, qty, formatted_price)
            
            # Jika ditolak karena crossed (-5022 Post-Only):
            if isinstance(res, dict) and res.get("code") == -5022:
                if is_emergency:
                    console.log(f"[yellow]Limit close crossed saat emergency/BEP. Langsung eksekusi market close instan...[/yellow]")
                    m_res = self.client.create_market_close_order(symbol, side, qty)
                    fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
                    return True, (fill_p if fill_p > 0 else target_price)
                else:
                    if side == "SELL":
                        formatted_price = self.client.format_price(symbol, formatted_price + tick)
                    else:
                        formatted_price = self.client.format_price(symbol, formatted_price - tick)
                    res = self.client.create_limit_close_order(symbol, side, qty, formatted_price)

            order_id = res.get("orderId") if isinstance(res, dict) else None
            if not order_id:
                console.log(f"[yellow]Limit close gagal, beralih ke market close darurat...[/yellow]")
                m_res = self.client.create_market_close_order(symbol, side, qty)
                fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
                return True, (fill_p if fill_p > 0 else target_price)

            # Batas waktu tunggu: 1.5 detik jika emergency (SL/BEP) agar harga tidak longsor, 6 detik jika Take Profit normal
            max_wait = 1.5 if is_emergency else 6.0
            t0 = time.time()
            while time.time() - t0 < max_wait:
                time.sleep(0.7)
                chk = self.client.get_order(symbol, order_id)
                status = chk.get("status")
                if status == "FILLED":
                    fill_p = float(chk.get("avgPrice", 0.0)) or formatted_price
                    console.log(f"[bold green]MAKER LIMIT CLOSE TERISI PENUH! ({symbol} @ {fill_p}, Fee Terendah Maker)[/bold green]")
                    return True, fill_p
                elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                    break

            # Jika belum terisi setelah batas waktu, batalkan dan tuntaskan seketika dengan market order
            console.log(f"[yellow]Maker limit close belum terisi setelah {max_wait}s. Menuntaskan dengan market order agar profit terkunci aman...[/yellow]")
            try:
                self.client.cancel_order(symbol, order_id)
            except Exception:
                pass
            m_res = self.client.create_market_close_order(symbol, side, qty)
            fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
            return True, (fill_p if fill_p > 0 else target_price)

        except Exception as e:
            console.log(f"[yellow]Notice maker close: {e}, fallback ke market close...[/yellow]")
            try:
                m_res = self.client.create_market_close_order(symbol, side, qty)
                fill_p = float(m_res.get("avgPrice", 0.0)) if isinstance(m_res, dict) else 0.0
                return True, (fill_p if fill_p > 0 else target_price)
            except Exception as e2:
                console.log(f"[red]Gagal menutup posisi: {e2}[/red]")
                return False, target_price

    def monitor_active_position(self):
        """
        Memantau posisi aktif dengan manajemen risiko ketat Akademi Crypto (Kalimasada):
        1. Target Take Profit penuh: +1.4% (Risk to Reward 1:2).
        2. Stop Loss awal: -0.7% (Resiko terukur 1R).
        3. Proteksi Break-Even (BEP): Begitu profit mencapai 1R (+0.7%), SL otomatis digeser
           ke Break-Even (+0.15% di atas Entry) sehingga menutup 100% seluruh fee bursa (0.07%)
           + buffer slippage flashdump (0.03%) & mengunci untung bersih, memberi ruang napas ke TP.
        """
        if not self.active_position:
            return
            
        pos = self.active_position
        symbol = pos["symbol"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        qty = pos["qty"]
        pos_leverage = pos.get("leverage", config.LEVERAGE)
        
        try:
            current_price = self.client.fetch_price(symbol)
            if current_price <= 0:
                return
                
            pnl_pct = ((current_price - entry_price) / entry_price) if side == "buy" else ((entry_price - current_price) / entry_price)
            pnl_usd = pnl_pct * pos["notional"]

            # --- 1. Proteksi Geser SL ke Break-Even (BEP) saat mencapai 1R (+0.7%) ---
            bep_trigger = pos.get("bep_trigger_price", 0.0)
            bep_activated = pos.get("bep_activated", False)
            if not bep_activated:
                hit_bep = (current_price >= bep_trigger) if side == "buy" else (current_price <= bep_trigger) if bep_trigger > 0 else (pnl_pct >= config.BEP_PROFIT_TRIGGER)
                if hit_bep:
                    bep_lock = getattr(config, "BEP_LOCK_PROFIT", 0.0015) # +0.15% di atas entry
                    raw_bep = entry_price * (1.0 + bep_lock) if side == "buy" else entry_price * (1.0 - bep_lock)
                    formatted_bep = self.client.format_price(symbol, raw_bep)
                    
                    rules = self.client._symbols_rules.get(symbol, {})
                    tick = rules.get("tick_size", 0.0001)
                    if side == "buy":
                        formatted_bep = max(formatted_bep, entry_price + 2 * tick)
                    else:
                        formatted_bep = min(formatted_bep, entry_price - 2 * tick)
                        
                    pos["sl_price"] = formatted_bep
                    pos["bep_activated"] = True
                    console.log(f"[bold cyan]🛡️ BREAK-EVEN DIAKTIFKAN pada {symbol}: Profit mencapai 1R (+0.7%), menggeser Native SL ke {formatted_bep} (Terkunci Untung Bersih +0.15% Menutup Seluruh Fee Bursa)[/bold cyan]")
                    
                    # Batalkan Stop Loss lama di Binance & Pasang Native STOP_MARKET baru di harga BEP
                    try:
                        old_sl_id = pos.get("native_sl_order_id")
                        if old_sl_id:
                            try:
                                self.client.cancel_order(symbol, old_sl_id)
                            except Exception:
                                self.client.cancel_all_open_orders(symbol)
                        else:
                            self.client.cancel_all_open_orders(symbol)

                        sl_side = "SELL" if side == "buy" else "BUY"
                        new_sl = self.client.create_stop_loss_order(
                            symbol=symbol,
                            side=sl_side,
                            stop_price=formatted_bep,
                            qty=qty
                        )
                        if isinstance(new_sl, dict) and new_sl.get("orderId"):
                            pos["native_sl_order_id"] = new_sl.get("orderId")
                            console.log(f"[bold green]🛡️ NATIVE BREAK-EVEN STOP LOSS BERHASIL DIPASANG DI BINANCE pada {symbol} @ {formatted_bep}[/bold green]")
                    except Exception as e_bep:
                        console.log(f"[red]Gagal memasang Native BEP SL di Binance: {e_bep}[/red]")

            # Perbarui nilai SL/TP terkini
            sl_price = pos["sl_price"]
            tp_price = pos["tp_price"]

            hit_tp = (current_price >= tp_price) if side == "buy" else (current_price <= tp_price)
            hit_sl = (current_price <= sl_price) if side == "buy" else (current_price >= sl_price)
            
            console.log(f"[dim]Pemantauan 2.5s: {symbol} @ {current_price} | PnL: {pnl_pct*100:+.2f}% (${pnl_usd:+.2f}) | TP: {tp_price:.4f} | SL: {sl_price:.4f} | BEP: {'AKTIF' if pos.get('bep_activated') else 'MENUNGGU 1R'}[/dim]")
            
            if hit_tp:
                # Periksa apakah posisi sudah ditutup oleh Native SL / BEP di Binance sebelum execute close
                pos_check = self.sync_exchange_position(force=True)
                if not pos_check:
                    console.log(f"[bold green]Posisi {symbol} telah berhasil ditutup instan di Binance matching engine.[/bold green]")
                    return

                console.log(f"[bold green]🎯 TAKE PROFIT TERCAPAI (RR 1:2 / +1.4%)! (+{pnl_pct*100:.2f}%, PnL: +${pnl_usd:.2f}) pada {symbol}[/bold green]")
                # Batalkan Native SL yang masih terpasang di Binance agar tidak tereksekusi ganda
                try:
                    self.client.cancel_all_open_orders(symbol)
                except Exception as e_c:
                    console.log(f"[dim]Cancel native SL saat TP: {e_c}[/dim]")

                close_side = "SELL" if side == "buy" else "BUY"
                success, actual_exit = self.execute_maker_close(symbol=symbol, side=close_side, qty=qty, target_price=current_price, is_emergency=False)
                
                final_exit = actual_exit if actual_exit > 0 else current_price
                self._record_closed_position(pos, exit_price_hint=final_exit, result_hint="WIN")
                
            elif hit_sl:
                # Periksa apakah posisi sudah ditutup oleh Native Stop Loss di Binance
                pos_check = self.sync_exchange_position(force=True)
                if not pos_check:
                    console.log(f"[bold green]Posisi {symbol} telah berhasil ditutup instan oleh Native SL/BEP di Binance matching engine.[/bold green]")
                    return

                # Jika masih terbuka karena anomali bursa, eksekusi darurat seketika
                is_be_or_profit = pos.get("bep_activated", False) or (pnl_usd >= 0.0)
                tag = "🛡️ BREAK-EVEN EXIT (Bebas Risiko Terkunci)" if is_be_or_profit else "🛑 STOP LOSS TERPICU (-0.7%)"
                color = "green" if is_be_or_profit else "red"
                
                console.log(f"[bold {color}]{tag}! ({pnl_pct*100:+.2f}%, PnL: ${pnl_usd:+.2f}) pada {symbol}[/bold {color}]")
                try:
                    self.client.cancel_all_open_orders(symbol)
                except Exception:
                    pass

                close_side = "SELL" if side == "buy" else "BUY"
                success, actual_exit = self.execute_maker_close(symbol=symbol, side=close_side, qty=qty, target_price=current_price, is_emergency=True)
                
                final_exit = actual_exit if actual_exit > 0 else current_price
                self._record_closed_position(pos, exit_price_hint=final_exit, result_hint="WIN" if is_be_or_profit else "LOSS")
                
        except Exception as e:
            console.log(f"[red]Error memantau posisi aktif {symbol}: {e}[/red]")

    def run_scan_loop(self):
        """Loop pemindaian utama yang berjalan secara otonom di background."""
        console.log("[bold green]>>> Binance Scalper Autonomous Loop Dimulai (Native Engine + Neon Tech) <<<[/bold green]")
        self.is_running = True
        
        # 1. Inisialisasi Database Neon Tech (Schema: binance_scalper)
        db.init_db()
        
        # 2. Inisialisasi Bursa
        self.client.ensure_single_asset_mode()
        self.client.load_leverage_brackets()
        self.get_futures_balance(max_age_sec=0)
        self.sync_exchange_position()
        
        while self.is_running:
            try:
                if self.client.is_banned():
                    s_left = int(self.client.ban_until - time.time())
                    if s_left > 0:
                        m_left = s_left // 60
                        sec_left = s_left % 60
                        now_log = time.time()
                        if now_log - self.client._last_ban_log_time > 60:
                            self.client._last_ban_log_time = now_log
                            console.log(f"[yellow]IP Cooldown Binance aktif ({m_left}m {sec_left}s lagi). Menunggu otomatis tanpa request ke bursa...[/yellow]")
                        if self.active_position:
                            time.sleep(min(2.5, max(1, s_left)))
                        else:
                            time.sleep(min(30, max(5, s_left + 1)))
                        continue

                # Muat ulang aturan pasar jika sebelumnya gagal akibat cooldown
                if len(self.client._symbols_rules) == 0:
                    self.client.load_markets()

                # 1. Selalu sinkronisasi posisi riil dari Binance
                self.sync_exchange_position()

                # 2. Jika ada posisi aktif, pantau harga setiap 2.5 detik
                if self.active_position:
                    self.monitor_active_position()
                    time.sleep(2.5)  # Cek harga posisi aktif setiap 2.5 detik sesuai permintaan
                    continue
                    
                # 3. Jalankan pemindaian koin Top volume
                self.scan_top_coins()
                
                # 4. Cek saldo akun
                bal = self.get_futures_balance()
                avail_usdt = bal["available"]
                
                # 5. Jika ada sinyal valid dan saldo tersedia cukup
                if self.active_signals and not self.active_order and not self.active_position:
                    best_signal = self.active_signals[0]
                    sym = best_signal.get("symbol", "")
                    if time.time() < self._symbol_order_cooldown.get(sym, 0.0):
                        # Jika koin teratas masih dalam cooldown setelah auto-cancel, buang dari active_signals
                        self.active_signals = [s for s in self.active_signals if s.get("symbol") != sym]
                    else:
                        console.log(f"[bold green]Sinyal terbaik terdeteksi:[/bold green] {best_signal['side']} {best_signal['symbol']} (Skor: {best_signal.get('score', 0)})")
                        min_req = config.FIXED_MARGIN_LOW_BALANCE if avail_usdt < config.BALANCE_THRESHOLD_SCALING else (avail_usdt * config.RISK_PORTFOLIO_PERCENT)
                        if avail_usdt >= min_req:
                            self.execute_limit_order(best_signal)
                        else:
                            console.log(f"[yellow]Saldo USDT Futures (${avail_usdt:.2f}) di bawah minimum (${min_req:.2f}). Menunggu modal.[/yellow]")
                        
                if self.active_position:
                    time.sleep(2.5)  # Langsung monitor 2.5s jika posisi baru saja terisi
                else:
                    time.sleep(config.SCAN_INTERVAL_SECONDS)
                
            except Exception as e:
                console.log(f"[red]Error di siklus bot scalper: {e}[/red]")
                time.sleep(10)

    def run(self):
        self.run_scan_loop()

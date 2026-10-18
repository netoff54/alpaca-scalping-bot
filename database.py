import os
import time
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from rich.console import Console

console = Console()

DATABASE_URL = os.getenv("DATABASE_URL", "")

class NeonDatabase:
    """
    Manajer database PostgreSQL Neon Tech terisolasi untuk Binance Scalper Bot.
    Menggunakan schema khusus 'binance_scalper' agar 100% terpisah dari database Bitget.
    """
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url or os.getenv("DATABASE_URL", "")
        self._is_connected = False

    def get_connection(self):
        """Membuat koneksi ke PostgreSQL Neon Tech dengan SSL require."""
        if not self.db_url:
            raise ValueError("DATABASE_URL belum dikonfigurasi di environment variable.")
        return psycopg2.connect(self.db_url, sslmode="require", connect_timeout=10)

    def init_db(self):
        """Inisialisasi schema dan tabel terisolasi 'binance_scalper'."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Buat schema khusus agar tidak bertabrakan dengan Bitget
                    cur.execute("CREATE SCHEMA IF NOT EXISTS binance_scalper;")
                    
                    # 2. Tabel riwayat trade Binance Futures
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS binance_scalper.trades (
                            id SERIAL PRIMARY KEY,
                            symbol VARCHAR(30) NOT NULL,
                            side VARCHAR(10) NOT NULL,
                            entry_price NUMERIC(18, 8) NOT NULL,
                            exit_price NUMERIC(18, 8),
                            qty NUMERIC(18, 8) NOT NULL,
                            notional NUMERIC(18, 4),
                            margin_used NUMERIC(18, 4),
                            pnl_usd NUMERIC(18, 4),
                            pnl_pct NUMERIC(8, 2),
                            result VARCHAR(10),
                            opened_at TIMESTAMP,
                            closed_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # 3. Tabel riwayat sinyal scalping yang terdeteksi
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS binance_scalper.signals (
                            id SERIAL PRIMARY KEY,
                            symbol VARCHAR(30) NOT NULL,
                            side VARCHAR(10) NOT NULL,
                            entry_price NUMERIC(18, 8) NOT NULL,
                            sl_price NUMERIC(18, 8) NOT NULL,
                            tp_price NUMERIC(18, 8) NOT NULL,
                            rsi NUMERIC(8, 2),
                            atr NUMERIC(18, 8),
                            score NUMERIC(8, 2),
                            vol_24h_m NUMERIC(18, 2),
                            rank INT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # 4. Tabel pemantauan pertumbuhan modal (Wallet Compounding Tracking)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS binance_scalper.wallet_history (
                            id SERIAL PRIMARY KEY,
                            total_wallet NUMERIC(18, 4) NOT NULL,
                            available_balance NUMERIC(18, 4) NOT NULL,
                            unrealized_pnl NUMERIC(18, 4),
                            compounded_trade_size NUMERIC(18, 4),
                            margin_allocation_pct NUMERIC(6, 2),
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                conn.commit()
            self._is_connected = True
            console.log("[bold green]Database Neon Tech (schema: binance_scalper) berhasil diinisialisasi terpisah dari Bitget.[/bold green]")
        except Exception as e:
            console.log(f"[yellow]Peringatan koneksi Neon Tech: {e} (Bot tetap berjalan normal)[/yellow]")

    def record_trade(self, trade_data: Dict[str, Any]):
        """Menyimpan hasil trade ke Neon Tech."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO binance_scalper.trades (
                            symbol, side, entry_price, exit_price, qty, notional, margin_used,
                            pnl_usd, pnl_pct, result, closed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """, (
                        trade_data.get("symbol"),
                        trade_data.get("side", "BUY"),
                        trade_data.get("entry_price", 0.0),
                        trade_data.get("exit_price", 0.0),
                        trade_data.get("qty", 0.0),
                        trade_data.get("notional", 0.0),
                        trade_data.get("margin_used", 0.0),
                        trade_data.get("pnl_usd", 0.0),
                        trade_data.get("pnl_pct", 0.0),
                        trade_data.get("result", "WIN")
                    ))
                conn.commit()
        except Exception as e:
            console.log(f"[dim]DB record trade: {e}[/dim]")

    def record_signals(self, signals: List[Dict[str, Any]]):
        """Menyimpan 5 sinyal teratas ke database untuk audit performa."""
        if not signals:
            return
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for sig in signals[:5]:
                        cur.execute("""
                            INSERT INTO binance_scalper.signals (
                                symbol, side, entry_price, sl_price, tp_price,
                                rsi, atr, score, vol_24h_m, rank
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """, (
                            sig.get("symbol"),
                            sig.get("side"),
                            sig.get("entry_price"),
                            sig.get("sl_price"),
                            sig.get("tp_price"),
                            sig.get("rsi"),
                            sig.get("atr"),
                            sig.get("score"),
                            sig.get("vol_24h_m"),
                            sig.get("rank")
                        ))
                conn.commit()
        except Exception as e:
            console.log(f"[dim]DB record signals: {e}[/dim]")

    def record_wallet_snapshot(self, total_wallet: float, available: float, unpnl: float, trade_size: float, margin_pct: float = 0.5):
        """Merekam riwayat saldo untuk grafik compounding portofolio."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO binance_scalper.wallet_history (
                            total_wallet, available_balance, unrealized_pnl,
                            compounded_trade_size, margin_allocation_pct
                        ) VALUES (%s, %s, %s, %s, %s);
                    """, (total_wallet, available, unpnl, trade_size, margin_pct))
                conn.commit()
        except Exception as e:
            console.log(f"[dim]DB record wallet: {e}[/dim]")

    def get_trade_summary(self) -> Dict[str, Any]:
        """Mengambil ringkasan statistik trading langsung dari database Neon."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_trades,
                            COUNT(*) FILTER (WHERE result = 'WIN') as winning_trades,
                            COALESCE(SUM(pnl_usd), 0) as total_pnl_usd
                        FROM binance_scalper.trades;
                    """)
                    row = cur.fetchone()
                    if row:
                        return {
                            "total_trades": int(row.get("total_trades") or 0),
                            "winning_trades": int(row.get("winning_trades") or 0),
                            "total_pnl_usd": float(row.get("total_pnl_usd") or 0.0)
                        }
        except Exception as e:
            console.log(f"[dim]DB summary error: {e}[/dim]")
        return {"total_trades": 0, "winning_trades": 0, "total_pnl_usd": 0.0}

    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Mengambil riwayat trade terakhir dari Neon Tech agar memori bot tidak reset saat restart/redeploy."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id, symbol, side, entry_price, exit_price, qty, notional,
                               margin_used, pnl_usd, pnl_pct, result, closed_at, created_at
                        FROM binance_scalper.trades
                        ORDER BY id DESC LIMIT %s;
                    """, (limit,))
                    rows = cur.fetchall()
                    return [dict(r) for r in rows] if rows else []
        except Exception as e:
            console.log(f"[dim]DB get recent trades: {e}[/dim]")
        return []

    def cleanup_old_signals(self):
        """Membersihkan log sinyal lama agar menghemat kuota dan storage Neon Tech."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE TABLE binance_scalper.signals;")
                conn.commit()
            console.log("[green]Log sinyal lama Neon Tech berhasil dibersihkan untuk menghemat kuota.[/green]")
        except Exception as e:
            console.log(f"[dim]DB cleanup signals: {e}[/dim]")

db = NeonDatabase()

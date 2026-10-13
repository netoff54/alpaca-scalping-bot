import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
from rich.console import Console
from rich.table import Table
from config import config
from strategy import prepare_indicators, check_signal

console = Console()

def fetch_historical_candles(symbol: str = "BTC/USDT", timeframe: str = "1m", limit: int = 1000) -> pd.DataFrame:
    """Mengambil data candle nyata dari Binance publik tanpa butuh API Key."""
    console.print(f"[cyan]Mengambil {limit} candle {timeframe} untuk {symbol} dari Binance...[/cyan]")
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def run_simulation(df: pd.DataFrame):
    """
    Simulasi Paper Trading Realistis:
    - Modal Awal: $10.00
    - Margin: ISOLATED ($1 per posisi dengan leverage 5x = notional $5)
    - Order: LIMIT ORDER (hanya terisi jika harga pasar menyentuh limit price)
    - Fee: Maker fee 0.02%
    - Risiko per trade: Maksimal $0.05 (0.5% dari $10)
    """
    df = prepare_indicators(df)
    
    balance = config.TOTAL_CAPITAL
    initial_balance = balance
    trades = []
    active_limit_order = None
    active_position = None
    
    min_bars = config.EMA_TREND + 10
    
    for i in range(min_bars, len(df)):
        sub_df = df.iloc[:i+1]
        current_candle = df.iloc[i]
        
        # 1. Cek Posisi Aktif (Kena TP atau SL)
        if active_position is not None:
            side = active_position['side']
            tp = active_position['tp_price']
            sl = active_position['sl_price']
            notional = active_position['notional']
            entry_p = active_position['entry_price']
            
            closed = False
            pnl_gross = 0.0
            exit_reason = ""
            exit_price = 0.0
            
            if side == "BUY":
                # Kena TP jika High menembus TP
                if current_candle['high'] >= tp:
                    exit_price = tp
                    pnl_gross = notional * ((tp - entry_p) / entry_p)
                    exit_reason = "TAKE PROFIT (WIN)"
                    closed = True
                # Kena SL jika Low menembus SL
                elif current_candle['low'] <= sl:
                    exit_price = sl
                    pnl_gross = notional * ((sl - entry_p) / entry_p)
                    exit_reason = "STOP LOSS (LOSS)"
                    closed = True
            elif side == "SELL":
                # Kena TP jika Low menembus TP
                if current_candle['low'] <= tp:
                    exit_price = tp
                    pnl_gross = notional * ((entry_p - tp) / entry_p)
                    exit_reason = "TAKE PROFIT (WIN)"
                    closed = True
                # Kena SL jika High menembus SL
                elif current_candle['high'] >= sl:
                    exit_price = sl
                    pnl_gross = notional * ((entry_p - sl) / entry_p)
                    exit_reason = "STOP LOSS (LOSS)"
                    closed = True
                    
            if closed:
                # Fee maker bolak-balik (Entry + Exit)
                fee = notional * (config.MAKER_FEE_RATE * 2)
                pnl_net = pnl_gross - fee
                balance += pnl_net
                
                trades.append({
                    "time": current_candle['datetime'],
                    "side": side,
                    "entry": entry_p,
                    "exit": exit_price,
                    "reason": exit_reason,
                    "pnl_gross": pnl_gross,
                    "fee": fee,
                    "pnl_net": pnl_net,
                    "balance": balance
                })
                active_position = None
            continue  # Lanjut ke bar berikutnya selama mengelola posisi
            
        # 2. Cek Eksekusi Limit Order yang Menggantung
        if active_limit_order is not None:
            order_side = active_limit_order['side']
            limit_p = active_limit_order['entry_price']
            
            # Cek apakah harga menyentuh limit price pada candle ini
            filled = False
            if order_side == "BUY" and current_candle['low'] <= limit_p:
                filled = True
            elif order_side == "SELL" and current_candle['high'] >= limit_p:
                filled = True
                
            if filled:
                active_position = active_limit_order
                active_limit_order = None
            else:
                # Limit order timeout: batalkan jika lewat dari 2 candle (mencegah hanging order)
                active_limit_order['age_bars'] += 1
                if active_limit_order['age_bars'] >= 2:
                    active_limit_order = None
            continue
            
        # 3. Cari Sinyal Baru Jika Tidak Ada Order / Posisi
        signal = check_signal(sub_df)
        if signal:
            signal['age_bars'] = 0
            active_limit_order = signal

    # --- Render Hasil Simulasi ---
    console.print("\n[bold yellow]====================================================[/bold yellow]")
    console.print("[bold green]       HASIL SIMULASI BOT SCALPING ($10 MODAL)       [/bold green]")
    console.print("[bold yellow]====================================================[/bold yellow]\n")

    if not trades:
        console.print("[red]Tidak ada trade yang tereksekusi dalam periode ini.[/red]")
        return

    table = Table(title="Daftar Transaksi Terisolasi (Limit Order)")
    table.add_column("Waktu", style="cyan")
    table.add_column("Posisi", style="magenta")
    table.add_column("Entry", justify="right")
    table.add_column("Exit", justify="right")
    table.add_column("Alasan", justify="center")
    table.add_column("Net PnL ($)", justify="right")
    table.add_column("Saldo ($)", justify="right", style="bold")

    total_wins = 0
    total_losses = 0
    total_fees = 0.0

    for t in trades:
        is_win = "WIN" in t['reason']
        if is_win:
            total_wins += 1
            pnl_style = "green"
        else:
            total_losses += 1
            pnl_style = "red"
            
        total_fees += t['fee']

        table.add_row(
            str(t['time']),
            t['side'],
            f"${t['entry']:,.2f}",
            f"${t['exit']:,.2f}",
            f"[{pnl_style}]{t['reason']}[/{pnl_style}]",
            f"[{pnl_style}]{t['pnl_net']:+.4f}[/{pnl_style}]",
            f"${t['balance']:.4f}"
        )

    console.print(table)

    total_trades = len(trades)
    win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0
    net_profit = balance - initial_balance
    return_pct = (net_profit / initial_balance) * 100

    summary_table = Table(title="Ringkasan Performa Bot")
    summary_table.add_column("Metrik", style="bold")
    summary_table.add_column("Nilai", justify="right")

    summary_table.add_row("Modal Awal", f"${initial_balance:.2f}")
    summary_table.add_row("Saldo Akhir", f"${balance:.4f}")
    summary_table.add_row("Net Profit / Loss", f"[{'green' if net_profit >= 0 else 'red'}]${net_profit:+.4f} ({return_pct:+.2f}%)[/]")
    summary_table.add_row("Total Transaksi", str(total_trades))
    summary_table.add_row("Menang / Kalah", f"{total_wins} / {total_losses}")
    summary_table.add_row("Win Rate", f"{win_rate:.1f}%")
    summary_table.add_row("Total Fee Terbayar", f"${total_fees:.4f}")
    summary_table.add_row("Tipe Margin", "[green]ISOLATED[/green]")
    summary_table.add_row("Tipe Order", "[green]LIMIT ORDER (Maker)[/green]")

    console.print(summary_table)

if __name__ == "__main__":
    df_data = fetch_historical_candles(symbol="BTC/USDT", timeframe="1m", limit=1000)
    run_simulation(df_data)

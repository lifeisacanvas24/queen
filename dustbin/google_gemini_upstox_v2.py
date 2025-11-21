import argparse
import datetime
import json
import time
import math
from concurrent.futures import ThreadPoolExecutor

import polars as pl
import requests
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

# --- USER CONFIGURATION ---
ACCESS_TOKEN = "YOUR_UPSTOX_ACCESS_TOKEN_HERE"  # <--- PASTE TOKEN HERE
INSTRUMENT_FILE = "all_symbols.json"
MAX_WORKERS = 10  # Adjust based on rate limits

# --- API CONFIG ---
BASE_URL = "https://api.upstox.com/v3"
HEADERS = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Accept': 'application/json'
}

# --- CLI ARGUMENTS ---
parser = argparse.ArgumentParser(description="Upstox Market Scanner (Intraday/Swing/BTST)")
parser.add_argument("--mode", choices=["intraday", "swing", "btst"], required=True, help="Select scanning mode")
args = parser.parse_args()

# --- UTILS ---
def get_time_config(mode):
    """Returns API config based on mode."""
    today = datetime.date.today()

    if mode == "intraday":
        # Fetch last 3 days of 15-minute candles for indicators
        start = today - datetime.timedelta(days=5)
        interval = "15minute"
        endpoint = "intraday"
        history_days = None # Intraday endpoint doesn't use simple dates in path usually, but Upstox v3 does
    elif mode == "btst":
        # Fetch last 10 days of 30-minute candles
        start = today - datetime.timedelta(days=10)
        interval = "30minute"
        endpoint = "intraday"
        history_days = None
    else: # swing
        # Fetch 200 days daily
        start = today - datetime.timedelta(days=300) # Buffer for weekends
        interval = "day"
        endpoint = "historical-candle"
        history_days = 300

    return str(today), str(start), interval, endpoint

# --- 100% POLARS TECHNICAL ANALYSIS ---
def calculate_indicators(df: pl.DataFrame, mode: str) -> pl.DataFrame:
    """Calculates RSI, ATR, EMAs, and VWAP (for Intraday)."""

    # 1. EMAs
    df = df.with_columns([
        pl.col("close").ewm_mean(span=20, adjust=False).alias("EMA_20"),
        pl.col("close").ewm_mean(span=50, adjust=False).alias("EMA_50"),
        pl.col("close").ewm_mean(span=200, adjust=False).alias("EMA_200")
    ])

    # 2. RSI (Wilder's)
    n_rsi = 14
    alpha = 1.0 / n_rsi
    df = df.with_columns((pl.col("close") - pl.col("close").shift(1)).alias("diff"))
    df = df.with_columns([
        pl.when(pl.col("diff") > 0).then(pl.col("diff")).otherwise(0.0).alias("gain"),
        pl.when(pl.col("diff") < 0).then(pl.col("diff").abs()).otherwise(0.0).alias("loss"),
    ])
    df = df.with_columns([
        pl.col("gain").ewm_mean(alpha=alpha, adjust=False).alias("avg_gain"),
        pl.col("loss").ewm_mean(alpha=alpha, adjust=False).alias("avg_loss"),
    ])
    df = df.with_columns(
        (100.0 - (100.0 / (1.0 + (pl.col("avg_gain") / pl.col("avg_loss"))))).alias("RSI")
    )

    # 3. ATR (Wilder's)
    df = df.with_columns([pl.col("close").shift(1).alias("prev_close")])
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - pl.col("prev_close")).abs(),
        (pl.col("low") - pl.col("prev_close")).abs()
    )
    df = df.with_columns(tr.alias("TR"))
    df = df.with_columns(pl.col("TR").ewm_mean(alpha=alpha, adjust=False).alias("ATR"))

    # 4. VWAP (Only relevant for Intraday/BTST on short timeframes)
    if mode in ["intraday", "btst"]:
        # Cumulative VWAP for the loaded dataset
        df = df.with_columns([
            (pl.col("close") * pl.col("volume")).cumsum().alias("cum_pv"),
            pl.col("volume").cumsum().alias("cum_vol")
        ])
        df = df.with_columns((pl.col("cum_pv") / pl.col("cum_vol")).alias("VWAP"))
    else:
        df = df.with_columns(pl.lit(0.0).alias("VWAP"))

    return df

def fetch_data(instrument_key, mode):
    """Fetches data from Upstox."""
    end_date, start_date, interval, endpoint = get_time_config(mode)

    # Construct URL based on Upstox docs
    if endpoint == "intraday":
         url = f"{BASE_URL}/historical-candle/intraday/{instrument_key}/{interval}"
    else:
         url = f"{BASE_URL}/historical-candle/{instrument_key}/{interval}/{end_date}/{start_date}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'candles' in data['data'] and data['data']['candles']:
                cols = ["timestamp", "open", "high", "low", "close", "volume", "oi"]
                df = pl.DataFrame(data['data']['candles'], schema=cols, orient="row")

                # Upstox returns Descending (Newest first). Sort Ascending for Calc
                df = df.sort("timestamp", descending=False)

                # Cast Types
                df = df.with_columns([
                    pl.col("open").cast(pl.Float64), pl.col("high").cast(pl.Float64),
                    pl.col("low").cast(pl.Float64), pl.col("close").cast(pl.Float64),
                    pl.col("volume").cast(pl.Float64)
                ])
                return df
    except Exception:
        pass
    return None

# --- STRATEGY LOGIC ---

def run_strategy(df, mode, symbol):
    """Applies specific logic based on mode."""
    if df.height < 50: return None

    curr = df.row(-1, named=True)
    close = curr['close']
    atr = curr['ATR'] if curr['ATR'] else close * 0.01
    rsi = curr['RSI']

    verdict = "AVOID"
    entry = 0.0
    sl = 0.0
    setup = ""

    # --- 1. INTRADAY MODE ---
    if mode == "intraday":
        vwap = curr['VWAP']
        ema_50 = curr['EMA_50']

        # Buy Logic: Above VWAP, Above EMA50, Good RSI
        if close > vwap and close > ema_50 and 55 < rsi < 70:
            verdict = "BUY (Intraday)"
            entry = close
            sl = min(curr['low'], vwap) - (atr * 0.5)
            setup = "Momentum: >VWAP & RSI"

        # Short Logic: Below VWAP, Below EMA50, Weak RSI
        elif close < vwap and close < ema_50 and rsi < 45:
            verdict = "SHORT (Intraday)"
            entry = close
            sl = max(curr['high'], vwap) + (atr * 0.5)
            setup = "Breakdown: <VWAP"

    # --- 2. SWING MODE ---
    elif mode == "swing":
        ema_20 = curr['EMA_20']
        ema_50 = curr['EMA_50']
        ema_200 = curr['EMA_200']

        # Strong Uptrend
        if close > ema_50 and close > ema_200:
            # High Momentum Breakout
            if rsi > 60 and rsi < 75:
                verdict = "★ STRONG BUY"
                entry = close
                sl = close - (1.5 * atr)
                setup = "Trend Breakout"
            # Pullback Opportunity
            elif rsi > 50 and abs(close - ema_20) / close < 0.02:
                verdict = "ADD ON DIPS"
                entry = ema_20 # Limit Order
                sl = ema_20 - (1.5 * atr)
                setup = "Rebound off 20EMA"

        # Downtrend
        elif close < ema_50 and close < ema_200 and rsi < 40:
            verdict = "SHORT (Swing)"
            entry = close
            sl = close + (1.5 * atr)
            setup = "Trend Breakdown"

    # --- 3. BTST MODE ---
    elif mode == "btst":
        # Condition: Closing near High of Day, Vol Spike, Bullish Trend
        day_high = df.select(pl.col("high")).max().item()
        vol_avg = df.select(pl.col("volume").mean()).item()

        if close >= (day_high * 0.985) and curr['volume'] > (vol_avg * 1.5) and rsi > 60:
             verdict = "BUY (BTST)"
             entry = close
             sl = close - atr
             setup = "Day High Close + Vol"

    if "AVOID" in verdict: return None

    # Calculate Targets
    direction = 1 if "BUY" in verdict or "ADD" in verdict else -1
    t1 = entry + (direction * atr * 1.0)
    t2 = entry + (direction * atr * 2.0)
    t3 = entry + (direction * atr * 3.0)

    return {
        "Symbol": symbol,
        "Verdict": verdict,
        "Setup": setup,
        "CMP": round(close, 2),
        "Entry": round(entry, 2),
        "SL": round(sl, 2),
        "T1": round(t1, 2),
        "T2": round(t2, 2),
        "T3": round(t3, 2),
        "RSI": round(rsi, 1)
    }

def worker(row):
    """Thread worker."""
    symbol = row['symbol']
    key = row['isin']

    df = fetch_data(key, args.mode)
    if df is None: return None

    df = calculate_indicators(df, args.mode)
    return run_strategy(df, args.mode, symbol)

def main():
    console = Console()
    mode_colors = {"intraday": "cyan", "swing": "magenta", "btst": "yellow"}

    console.print(f"[bold {mode_colors[args.mode]}]🚀 STARTING SCANNER | MODE: {args.mode.upper()}[/]")

    # Load Universe
    try:
        with open(INSTRUMENT_FILE, 'r') as f:
            data = json.load(f)
            universe = data['data'] if 'data' in data else data
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    results = []
    console.print(f"📊 Scanning [bold]{len(universe)}[/bold] symbols...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(worker, row) for row in universe]

        for i, future in enumerate(futures):
            res = future.result()
            if res:
                results.append(res)
                print("!", end="", flush=True) # Dot for hit
            else:
                print(".", end="", flush=True) # Dot for miss

            if i % 50 == 0: time.sleep(0.5) # Rate Limit

    print("\n")

    if not results:
        console.print("[red]No signals found for this mode.[/red]")
        return

    # --- SAVE OUTPUTS ---
    # 1. JSON
    with open(f"results_{args.mode}.json", "w") as f:
        json.dump(results, f, indent=4)

    # 2. CSV
    pl.DataFrame(results).write_csv(f"results_{args.mode}.csv")
    console.print(f"✅ Saved results to [bold]results_{args.mode}.json/.csv[/bold]")

    # --- RICH TABLE ---
    table = Table(title=f"🎯 {args.mode.upper()} VERDICTS", box=box.ROUNDED)

    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Verdict", style="bold")
    table.add_column("Setup", style="dim")
    table.add_column("Entry", justify="right", style="bold green")
    table.add_column("Stop Loss", justify="right", style="red")
    table.add_column("T1", justify="right", style="blue")
    table.add_column("T2", justify="right", style="blue")
    table.add_column("T3", justify="right", style="blue")

    for r in results:
        color = "green" if "BUY" in r['Verdict'] else "yellow" if "ADD" in r['Verdict'] else "red"

        table.add_row(
            r['Symbol'],
            f"[{color}]{r['Verdict']}[/]",
            r['Setup'],
            str(r['Entry']),
            str(r['SL']),
            str(r['T1']),
            str(r['T2']),
            str(r['T3'])
        )

    # Scrollable Output
    with console.pager():
        console.print(table)

if __name__ == "__main__":
    main()

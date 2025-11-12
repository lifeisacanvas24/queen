"""
──────────────────────────────────────────────────────────────────────────────
👑 Queen Cockpit v7.2 — Morning Intelligence System
──────────────────────────────────────────────────────────────────────────────
Author:  Aravind Kumar x GPT-5
Purpose: Autonomous intraday intelligence engine with pre-market analytics

🌄 PRE-MARKET MODULE OVERVIEW
──────────────────────────────────────────────────────────────────────────────

Your cockpit now includes a fully integrated *Morning Intelligence System*,
which auto-runs once per day between 09:00–09:15 IST and gives you:

    1️⃣ Morning Recap
        → Summarizes today’s high-confidence signals from runtime/high_signals.json
        → Displays symbol, RSI, bias, and action

    2️⃣ Multi-Day Trend Analyzer
        → Reads your archived signal files (archive/high_signals_YYYY-MM-DD.json)
        → Shows the last 5 trading days’ average signal strength trend

    3️⃣ Weekly Strength Gauge
        → Calculates a 7-day rolling average of overall sentiment
        → Displays an ASCII bar like [██████░░░░] 6.0/10

    4️⃣ Auto Archival & Reset
        → Archives yesterday’s signals before market open
        → Clears runtime/high_signals.json for the new session
        → Marks completion via runtime/morning_done.txt (so it won’t re-run twice)

──────────────────────────────────────────────────────────────────────────────
🔧 HOW TO USE
──────────────────────────────────────────────────────────────────────────────

AUTO-MODE (Recommended)
────────────────────────
✅ Already wired inside __main__:
    if _time(9, 0) <= _now_ist < _time(9, 15):
        morning_briefing()

This runs your full pre-market dashboard automatically — exactly once per day.

MANUAL-MODE (On-Demand Review)
───────────────────────────────
You can manually trigger any of the following anytime:

    morning_summary()        # Show today’s top signals
    analyze_archive_trend()  # Show 5-day average score trendline
    weekly_strength_gauge()  # Show 7-day rolling sentiment bar
    morning_briefing()       # Full pre-market dashboard (runs all of the above)

──────────────────────────────────────────────────────────────────────────────
📂 FILES & DIRECTORIES
──────────────────────────────────────────────────────────────────────────────
runtime/high_signals.json      → Current day’s signal log
runtime/morning_done.txt       → One-time run flag for today
archive/high_signals_YYYY-MM-DD.json  → Archived past sessions for backtesting

──────────────────────────────────────────────────────────────────────────────
🕓 AUTO-RUN CONDITIONS
──────────────────────────────────────────────────────────────────────────────
• Runs only if time ∈ [09:00, 09:15)
• Runs only if it hasn’t been completed yet for today
• Skips gracefully if already marked complete

──────────────────────────────────────────────────────────────────────────────
💡 Example Console Output
──────────────────────────────────────────────────────────────────────────────
🌄 Morning Briefing — Pre-Market Dashboard
📦 Archived high_signals_2025-11-04.json
🧹 Cleared current high_signals.json for new session

🌅 Morning Recap
FORCEMOT → RSI 62 | Bias: Long | Action: ⚡ Breakout Confirmed
NETWEB   → RSI 58 | Bias: Neutral | Action: 🚀 Watchlist Setup

📈 5-Day Signal Strength Trend
2025-10-31 → Avg Score: 6.5
2025-11-01 → Avg Score: 6.9
2025-11-03 → Avg Score: 7.2
2025-11-04 → Avg Score: 7.7
2025-11-05 → Avg Score: 8.0

📊 7-Day Rolling Strength Gauge
Strength [███████░░░] 7.1/10 → 💪 Moderately Bullish

✅ Morning briefing marked complete for 2025-11-05
──────────────────────────────────────────────────────────────────────────────
"""

import os, sys
import json
import math
from datetime import datetime, date, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import time as _time
from datetime import datetime, timedelta, time as _time, timezone as _tz
from zoneinfo import ZoneInfo
import json, time
from pathlib import Path
from rich.live import Live
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

import polars as pl
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.console import Group
from rich import box
from urllib.parse import quote
from urllib.parse import quote

console = Console()

# ─────────────────────────────── PATHS & CONSTANTS ─────────────────────────────
ROOT = (
    Path.home()
    / "Library/Mobile Documents/com~apple~CloudDocs/projects/git-repos/gsheetapps/queen"
)
DATA_DIR = ROOT / "data"
RUNTIME_DIR = DATA_DIR / "runtime"
STATE_DIR = RUNTIME_DIR / "state"
LOG_DIR = RUNTIME_DIR / "logs"
STATIC_DIR = DATA_DIR / "static"

HOLIDAY_FILE = STATIC_DIR / "nse_holidays.json"
UC_LC_CACHE_FILE = STATE_DIR / "nse_bands_cache.json"
OHL_CACHE_FILE = RUNTIME_DIR / "ohl_cache.json"
ALERT_LOG_FILE = RUNTIME_DIR / "alerts_log.json"

for d in [DATA_DIR, RUNTIME_DIR, STATE_DIR, LOG_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

REFRESH_MINUTES = 5  # default refresh cycle


# ─────────────────────────────── GLOBAL STATE ────────────────────────────────
CACHE_HITS = 0
CACHE_REFRESHES = 0
ACTIVE_SERVICE_DAY = None
LAST_CMP = {}
POSITIONS = {}  # optional, can be extended later


# ─────────────────────────────── UTILITY HELPERS ─────────────────────────────
def log_event(msg: str):
    """Append a line to runtime log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fpath = LOG_DIR / f"events_{date.today()}.log"
    with fpath.open("a") as f:
        f.write(f"[{datetime.now(tz).strftime('%H:%M:%S')}] {msg}\n")


def wait_until_next_boundary(minutes: int):
    """Sleep until the next N-minute boundary."""
    import time as _t

    now = datetime.now(tz)
    delta = minutes - (now.minute % minutes)
    next_boundary = (now + timedelta(minutes=delta)).replace(second=0, microsecond=0)
    sleep_time = max(5, (next_boundary - now).total_seconds())
    console.print(f"[dim]⏳ Sleeping {sleep_time/60:.1f} min until next refresh…[/dim]")
    _t.sleep(sleep_time)


# ─────────────────────────────── HOLIDAY UTILITIES ────────────────────────────
def load_nse_holidays():
    """Load NSE holiday list from JSON file or fallback."""
    try:
        with open(HOLIDAY_FILE, "r") as f:
            data = json.load(f)
        # expected format: [{ "date": "2025-03-08", "holiday": "Mahashivratri" }, ...]
        return {str(d["date"]): d.get("holiday", "") for d in data if "date" in d}
    except Exception:
        console.print(
            "[yellow]⚠️  Could not load NSE holiday file — using fallback[/yellow]"
        )
        return {
            "2025-01-26": "Republic Day",
            "2025-03-14": "Holi",
            "2025-04-14": "Ambedkar Jayanti",
            "2025-05-01": "Maharashtra Day",
            "2025-08-15": "Independence Day",
            "2025-10-02": "Gandhi Jayanti",
            "2025-10-24": "Diwali",
            "2025-12-25": "Christmas",
        }


HOLIDAYS = load_nse_holidays()


def is_trading_day(d: date) -> bool:
    ds = d.strftime("%Y-%m-%d")
    return d.weekday() < 5 and ds not in HOLIDAYS


def last_trading_day(target: date | None = None) -> str:
    """Return the most recent valid trading day (YYYY-MM-DD)."""
    if target is None:
        target = date.today()
    d = target
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


# ─────────────────────────────── SYMBOL MAP ────────────────────────────────
TICKERS = {
    "FORCEMOT": "NSE_EQ|INE451A01017",
    "SMLISUZU": "NSE_EQ|INE294B01019",
    "NETWEB": "NSE_EQ|INE0NT901020",
}

# ─────────────────────────────── TEST MESSAGE ───────────────────────────────
console.print(
    Panel.fit(
        "🧩 [bold cyan]Queen Cockpit v7[/bold cyan] foundation loaded\n"
        f"Root: {ROOT}\n"
        f"Holidays loaded: {len(HOLIDAYS)} entries\n"
        f"Tickers: {', '.join(TICKERS.keys())}",
        border_style="bright_black",
    )
)

# ──────────────────────────────────────────────────────────────────────────────
#  ⚡ Queen Cockpit v7 – True Analytics Mode
#  Part 2 of 3: Indicator Engine + Data Fetch Layer
# ──────────────────────────────────────────────────────────────────────────────


SUPER_TREND_PERIOD = 10
SUPER_TREND_MULTIPLIER = 3

# ───────────────────────── v7.1 ANALYTICS CORE ─────────────────────────


def supertrend(
    df: pl.DataFrame,
    period: int = SUPER_TREND_PERIOD,
    multiplier: float = SUPER_TREND_MULTIPLIER,
) -> pl.DataFrame:
    """
    Compute Supertrend indicator using ATR-based bands.
    Returns df with added columns: 'supertrend', 'supertrend_dir'.
    """
    if df.height < period + 1:
        return df.with_columns(
            [
                pl.lit(np.nan).alias("supertrend"),
                pl.lit("Neutral").alias("supertrend_dir"),
            ]
        )

    # ATR Calculation (RMA of True Range)
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr = (
        pl.concat_list(
            [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()]
        )
        .arr.max()
        .alias("TR")
    )

    atr = tr.cast(pl.Float64).ewm_mean(com=period - 1, adjust=False).alias("ATR")

    hl2 = (high + low) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    df = df.with_columns(
        [upper_band.alias("upper_band"), lower_band.alias("lower_band"), atr]
    )

    # Supertrend direction loop (vectorized approximation)
    st_dir = ["Neutral"]
    st_val = [hl2[0]]
    for i in range(1, len(df)):
        prev_dir = st_dir[-1]
        prev_st = st_val[-1]
        if close[i] > df["upper_band"][i - 1]:
            cur_dir = "Bullish"
        elif close[i] < df["lower_band"][i - 1]:
            cur_dir = "Bearish"
        else:
            cur_dir = prev_dir

        cur_st = df["lower_band"][i] if cur_dir == "Bullish" else df["upper_band"][i]
        st_dir.append(cur_dir)
        st_val.append(cur_st)

    df = df.with_columns(
        [pl.Series("supertrend", st_val), pl.Series("supertrend_dir", st_dir)]
    )
    return df


def indicators(df: pl.DataFrame) -> dict:
    """
    Compute full analytics suite:
      RSI(14), EMA(20/50/200), VWAP, ATR, OBV, CPR,
      Supertrend, VWAP bands, RSI–EMA crossover.
    Returns dictionary of computed indicators.
    """
    if df.height < 20:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI (14)
    delta = close.diff()
    gain = delta.clip_min(0)
    loss = (-delta).clip_min(0)
    avg_gain = gain.ewm_mean(com=14 - 1, adjust=False)
    avg_loss = loss.ewm_mean(com=14 - 1, adjust=False)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # EMAs
    ema20 = close.ewm_mean(span=20)
    ema50 = close.ewm_mean(span=50)
    ema200 = close.ewm_mean(span=200)

    # EMA bias
    if ema20[-1] > ema50[-1] > ema200[-1]:
        ema_bias = "Bullish"
    elif ema20[-1] < ema50[-1] < ema200[-1]:
        ema_bias = "Bearish"
    else:
        ema_bias = "Neutral"

    # VWAP + Bands
    typical_price = (high + low + close) / 3
    cum_vol = volume.cumsum()
    cum_vp = (typical_price * volume).cumsum()
    vwap = cum_vp / cum_vol
    atr_series = (
        pl.concat_list(
            [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()]
        )
        .arr.max()
        .ewm_mean(com=14 - 1, adjust=False)
    )
    vwap_upper = vwap + atr_series * 1.0
    vwap_lower = vwap - atr_series * 1.0

    # OBV
    obv = [0]
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv.append(obv[-1] + volume[i])
        elif close[i] < close[i - 1]:
            obv.append(obv[-1] - volume[i])
        else:
            obv.append(obv[-1])
    obv_trend = "Rising" if obv[-1] > np.percentile(obv, 70) else "Falling"

    # CPR (Central Pivot Range)
    pivot = (high[-2] + low[-2] + close[-2]) / 3
    bc = (high[-2] + low[-2]) / 2
    tc = (pivot - bc) + pivot
    cpr_val = (bc + tc) / 2

    # Supertrend
    st_df = supertrend(df)
    supertrend_dir = st_df["supertrend_dir"][-1]
    supertrend_val = st_df["supertrend"][-1]

    # RSI–EMA crossover signal
    ema_rsi = rsi.ewm_mean(span=14)
    if rsi[-1] > ema_rsi[-1]:
        rsi_cross = "Bullish"
    elif rsi[-1] < ema_rsi[-1]:
        rsi_cross = "Bearish"
    else:
        rsi_cross = "Neutral"

    return {
        "RSI": float(rsi[-1]),
        "EMA20": float(ema20[-1]),
        "EMA50": float(ema50[-1]),
        "EMA200": float(ema200[-1]),
        "EMA_BIAS": ema_bias,
        "VWAP": float(vwap[-1]),
        "VWAP_UPPER": float(vwap_upper[-1]),
        "VWAP_LOWER": float(vwap_lower[-1]),
        "ATR": float(atr_series[-1]),
        "OBV": obv_trend,
        "CPR": float(cpr_val),
        "SUPERTREND": float(supertrend_val),
        "SUPERTREND_BIAS": supertrend_dir,
        "RSI_CROSS": rsi_cross,
    }


# ─────────────────────────────── DATA FETCH: INTRADAY ─────────────────────────


from urllib.parse import quote


def fetch_intraday(key: str) -> pl.DataFrame | None:
    """
    Fetch authenticated Upstox intraday candles (v3) with flexible parsing.
    Automatically URL-encodes instrument key and adapts to variable-length candle arrays.
    """
    token = os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_TOKEN")
    if not token:
        console.print(
            "[red]❌ Missing Upstox token — export $UPSTOX_ACCESS_TOKEN[/red]"
        )
        return None

    interval = str(REFRESH_MINUTES)
    if interval not in {"1", "3", "5", "10", "15"}:
        interval = "5"

    encoded_key = quote(key, safe="")
    url = f"https://api.upstox.com/v3/historical-candle/intraday/{encoded_key}/minutes/{interval}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "User-Agent": f"QueenCockpit/{interval}min",
    }

    console.print(f"[blue]🔗 Fetching intraday for {key}[/blue]")
    console.print(f"[dim]{url}[/dim]")

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            raise ValueError(f"HTTP {r.status_code}: {r.text[:120]}")

        candles = r.json().get("data", {}).get("candles", [])
        if not candles:
            console.print(f"[yellow]⚠️ No intraday candles for {key}[/yellow]")
            return None

        # ✅ Flexible unpacking (Upstox can return 6–8 columns)
        df = pl.DataFrame(
            [
                (
                    rec[0],
                    float(rec[1]),
                    float(rec[2]),
                    float(rec[3]),
                    float(rec[4]),
                    float(rec[5]),
                )
                for rec in candles
                if len(rec) >= 6
            ],
            schema=["time", "open", "high", "low", "close", "volume"],
        ).sort("time")

        if len(df) == 0:
            console.print(f"[yellow]⚠️ No valid intraday rows for {key}[/yellow]")
            return None

        console.print(
            f"[dim]{key}: {len(df)} candles | Last {df['time'][-1]} | Close ₹{df['close'][-1]:.2f}[/dim]"
        )
        return df

    except Exception as e:
        console.print(f"[red]⚠️ Intraday fetch failed for {key}: {e}[/red]")
        return None


# ─────────────────────────────── DATA FETCH: DAILY OHL ────────────────────────


def fetch_daily_ohl(key: str) -> dict | None:
    """
    Smart, holiday-aware, cached, and auto-cleaned OHL fetch.
    Falls back to intraday OHL post-market if daily unavailable.
    Includes flexible candle parsing and encoded instrument keys.
    """
    global CACHE_HITS, CACHE_REFRESHES, ACTIVE_SERVICE_DAY
    now = datetime.now(tz)
    today = now.date()

    # Load cache
    try:
        cache = (
            json.loads(OHL_CACHE_FILE.read_text()) if OHL_CACHE_FILE.exists() else {}
        )
    except Exception:
        cache = {}

    # Clean old entries (10-day retention)
    cutoff = today - timedelta(days=10)
    cache = {
        k: v
        for k, v in cache.items()
        if "timestamp" in v and datetime.fromisoformat(v["timestamp"]).date() > cutoff
    }

    trading_day = (
        today if is_trading_day(today) else date.fromisoformat(last_trading_day(today))
    )
    ACTIVE_SERVICE_DAY = trading_day.isoformat()
    key_name = f"{key}|{trading_day}"
    entry = cache.get(key_name)

    def write_cache(k, data):
        cache[k] = {"ohl": data, "timestamp": now.isoformat()}
        OHL_CACHE_FILE.write_text(json.dumps(cache, indent=2))

    # Reuse cache if fresh
    if entry and (now - datetime.fromisoformat(entry["timestamp"])) < timedelta(
        hours=24
    ):
        CACHE_HITS += 1
        return entry["ohl"]

    token = os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_TOKEN")
    if not token:
        console.print("[red]❌ Missing Upstox token for OHL fetch[/red]")
        return None

    encoded_key = quote(key, safe="")
    url = (
        f"https://api.upstox.com/v3/historical-candle/{encoded_key}/days/1/"
        f"{trading_day}/{trading_day}"
    )
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    console.print(f"[blue]🔗 Fetching daily OHL for {key}[/blue]")
    console.print(f"[dim]{url}[/dim]")

    try:
        r = requests.get(url, headers=headers, timeout=10)

        # Handle invalid key case
        if r.status_code == 400 and "Invalid Instrument key" in r.text:
            console.print(
                f"[red]❌ Skipping {key} — invalid instrument key (check TICKERS map)[/red]"
            )
            return entry["ohl"] if entry else None

        candles = r.json().get("data", {}).get("candles", [])
        if not candles:
            console.print(
                f"[yellow]⚠️ No daily candle for {key} ({trading_day}) — using intraday fallback[/yellow]"
            )
            df = fetch_intraday(key)
            if df is None or df.is_empty():
                return entry["ohl"] if entry else None

            ohl = {
                "open": float(df["open"][0]),
                "high": float(df["high"].max()),
                "low": float(df["low"].min()),
                "prev_close": float(df["close"][-1]),
            }
        else:
            # ✅ Safe unpacking for variable-length candle arrays
            rec = candles[-1][:6]  # first 6 values only
            _, o, h, l, c, *_ = rec
            ohl = {
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "prev_close": float(c),
            }

        write_cache(key_name, ohl)
        CACHE_REFRESHES += 1
        console.print(
            f"[dim]{key}: OHL fetched | H {ohl['high']} L {ohl['low']} C {ohl['prev_close']}[/dim]"
        )
        return ohl

    except Exception as e:
        console.print(f"[red]Daily OHL fetch failed for {key}: {e}[/red]")
        return entry["ohl"] if entry else None


def run_forecast_mode(next_session_date: date):
    """
    Analyze recent market context and generate a tactical plan for the next trading session.
    v7.2b — Offline-aware forecast:
    Uses daily candles (cached or recent) if intraday data unavailable.
    """
    console.rule(
        f"[bold cyan]🎯 NEXT SESSION STRATEGIC PLAN ({next_session_date:%a %d %b %Y})[/bold cyan]"
    )
    forecast_data = {}

    lookback_days = 5
    today = date.today()
    token = os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_TOKEN")

    for sym, key in TICKERS.items():
        try:
            encoded_key = quote(key, safe="")
            console.print(f"[dim]🔍 Preparing forecast for [bold]{sym}[/bold][/dim]")

            # ------------------ Step 1: Try Intraday ------------------
            df = fetch_intraday(key)
            if df is None or df.is_empty():
                console.print(
                    f"[yellow]⚠️ No intraday data for {sym} — using daily candles fallback[/yellow]"
                )

                # ------------------ Step 2: Daily fallback ------------------
                if not token:
                    console.print("[red]❌ Missing Upstox token for forecast[/red]")
                    continue

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }

                # ✅ Build a proper 5-trading-day range
                days = []
                d = today - timedelta(days=1)
                while len(days) < lookback_days:
                    if is_trading_day(d):
                        days.append(d)
                    d -= timedelta(days=1)

                start_date = min(days)
                end_date = max(days)

                # Upstox requires from_date ≤ to_date (both valid trading days)
                url = (
                    f"https://api.upstox.com/v3/historical-candle/{encoded_key}/days/1/"
                    f"{start_date}/{end_date}"
                )

                console.print(
                    f"[dim]📅 Using {start_date} → {end_date} ({len(days)} sessions)[/dim]"
                )
                console.print(f"[blue]{url}[/blue]")

                console.print(f"[dim]🌐 Fetching daily history for {sym}[/dim]")
                console.print(f"[blue]{url}[/blue]")

                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code != 200:
                        raise ValueError(f"HTTP {r.status_code}: {r.text[:120]}")
                    candles = r.json().get("data", {}).get("candles", [])
                    if not candles:
                        console.print(f"[red]❌ No daily candles for {sym}[/red]")
                        continue

                    df = pl.DataFrame(
                        [
                            (ts, float(o), float(h), float(l), float(c), float(v))
                            for ts, o, h, l, c, v in candles
                        ],
                        schema=["time", "open", "high", "low", "close", "volume"],
                    ).sort("time")
                except Exception as e:
                    console.print(f"[red]❌ Daily fallback failed for {sym}: {e}[/red]")
                    continue

            # ------------------ Step 3: Indicators ------------------
            ind = indicators(df)
            if not ind or "EMA_BIAS" not in ind:
                console.print(
                    f"[yellow]⚠️ Skipping {sym} — incomplete indicator data[/yellow]"
                )
                continue

            cmp_ = float(df["close"][-1])
            ema_bias = ind["EMA_BIAS"]
            rsi = ind["RSI"]
            supertrend = ind.get("SUPERTREND_BIAS", "Neutral")
            vwap_zone = (
                "Above VWAP"
                if cmp_ > ind["VWAP"]
                else "Below VWAP"
                if cmp_ < ind["VWAP"]
                else "Neutral"
            )

            # ------------------ Step 4: Tactical Logic ------------------
            score = 0
            score += 3 if ema_bias == "Bullish" else 0
            score += 2 if supertrend == "Bullish" else 0
            score += 2 if rsi > 55 else 0
            score += 1 if cmp_ > ind["VWAP"] else 0
            score += 2 if cmp_ > ind["EMA50"] else 0
            score = min(score, 10)

            if score >= 8:
                plan = "📈 Bullish breakout forming"
            elif score >= 5:
                plan = "⚖️ Consolidation / Momentum setup"
            else:
                plan = "🔻 Weak momentum / Pullback"

            forecast_data[sym] = {
                "cmp": cmp_,
                "bias": ema_bias,
                "supertrend": supertrend,
                "rsi": round(rsi, 1),
                "vwap_zone": vwap_zone,
                "plan": plan,
                "score": score,
            }

            console.print(
                f"[cyan]{sym}[/cyan]: {plan} | Score {score}/10 | Bias: {ema_bias}, RSI: {rsi:.1f}, VWAP Zone: {vwap_zone}"
            )

        except Exception as e:
            console.print(f"[red]❌ Forecast failed for {sym}: {e}[/red]")
            continue

    # ------------------ Step 5: Save JSON ------------------
    if forecast_data:
        RUNTIME_DIR.mkdir(exist_ok=True)
        forecast_path = RUNTIME_DIR / "next_session_plan.json"
        forecast_path.write_text(json.dumps(forecast_data, indent=2))
        console.print(f"[green]✅ Forecast saved → {forecast_path}[/green]")
    else:
        console.print("[yellow]⚠️ No valid forecasts generated[/yellow]")


# ───────────────────────── FORECAST MODE TRIGGER ─────────────────────────
def handle_market_holiday_or_closed_day():
    """
    Handles holiday / non-trading days by running Forecast Mode automatically.
    Generates a next-session tactical plan and archives it.
    """
    today = datetime.now(tz).date()

    if not is_trading_day(today):
        next_day = today + timedelta(days=1)
        # roll forward until next trading day
        while not is_trading_day(next_day):
            next_day += timedelta(days=1)

        console.rule("[bold yellow]🎌 MARKET HOLIDAY — NSE CLOSED[/bold yellow]")
        console.print(
            f"{today:%A, %d %B %Y} → [bold cyan]{HOLIDAYS.get(today.strftime('%Y-%m-%d'), 'Unknown reason')}[/bold cyan]"
        )
        console.print(
            f"📅 Next session resumes on [green]{next_day:%A, %d %B %Y}[/green]"
        )
        console.print("[dim]Running Strategic Forecast Mode...[/dim]\n")

        try:
            run_forecast_mode(next_day)

            # Archive forecast result
            forecast_file = Path("runtime/next_session_plan.json")
            archive_dir = Path("archive")
            archive_dir.mkdir(exist_ok=True)
            archive_file = archive_dir / f"forecast_{next_day:%Y%m%d}.json"

            if forecast_file.exists():
                archive_file.write_text(forecast_file.read_text())
                console.print(f"[dim]📦 Forecast archived → {archive_file.name}[/dim]")
            else:
                console.print("[yellow]⚠️ No forecast file found to archive.[/yellow]")

        except Exception as e:
            console.print(f"[red]❌ Forecast generation failed: {e}[/red]")

        console.print(
            "[dim]Cockpit will idle until next trading session. You can safely close now.[/dim]\n"
        )
        sys.exit(0)


# ──────────────────────────────────────────────────────────────────────────────
#  📊 Queen Cockpit v7 – True Analytics Mode
#  Part 3 of 3: Render Engine + Runtime Loop + Cleanup
# ──────────────────────────────────────────────────────────────────────────────


def render_card(sym, key, eod_mode=False):
    """
    Render actionable card per symbol with advanced indicators (v7.1):
    - Supertrend, VWAP bands, RSI–EMA cross, and urgency-colored trend meter.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Kolkata")
    now = datetime.now(tz)

    df = fetch_intraday(key)
    if df is None or df.is_empty():
        console.print(f"[yellow]⚠️ No intraday data for {sym}[/yellow]")
        return None

    ind = indicators(df)
    if not ind:
        console.print(f"[yellow]⚠️ Indicators unavailable for {sym}[/yellow]")
        return None

    cmp_ = float(df["close"][-1])
    prev_cmp = LAST_CMP.get(sym)
    delta = cmp_ - prev_cmp if prev_cmp else 0.0
    delta_pct = ((cmp_ - prev_cmp) / prev_cmp * 100) if prev_cmp else 0.0
    LAST_CMP[sym] = cmp_

    # --- Derived Bias and Trend Confluence ---
    ema_bias = ind["EMA_BIAS"]
    supertrend_bias = ind["SUPERTREND_BIAS"]
    rsi_cross = ind["RSI_CROSS"]

    # VWAP band context
    if cmp_ >= ind["VWAP_UPPER"]:
        vwap_zone = "Overbought"
    elif cmp_ <= ind["VWAP_LOWER"]:
        vwap_zone = "Oversold"
    else:
        vwap_zone = "Neutral"

    # --- Core Scoring Logic ---
    score = 0
    score += 2 if ema_bias == "Bullish" else 0
    score += 2 if supertrend_bias == "Bullish" else 0
    score += 1 if rsi_cross == "Bullish" else 0
    score += 1 if ind["OBV"] == "Rising" else 0
    score += 1 if vwap_zone == "Neutral" else 0
    score += 2 if ind["RSI"] > 55 else 0
    score += 1 if cmp_ > ind["CPR"] else 0
    score = min(score, 10)

    bias = "Weak" if score < 4 else "Neutral" if score < 6 else "Long"
    clr = "red" if bias == "Weak" else "yellow" if bias == "Neutral" else "green"
    badge = "🔴" if bias == "Weak" else "🟡" if bias == "Neutral" else "🟢"

    # --- Trend Strength Meter ---
    bar_full = 10
    filled = int(score)
    trend_bar = "█" * filled + "░" * (bar_full - filled)
    urgency_color = "magenta" if score >= 8 else "yellow" if score >= 5 else "dim"

    # --- Smart Action + Urgency ---
    urgency = "LOW"
    action = "WAIT / OBSERVE"
    if (
        ema_bias == "Bullish"
        and supertrend_bias == "Bullish"
        and rsi_cross == "Bullish"
        and cmp_ > ind["VWAP"]
        and ind["RSI"] > 58
    ):
        urgency = "HIGH"
        action = f"⚡ Breakout Alignment → Enter above ₹{cmp_:.2f}"
        log_high_confidence_signal(sym, cmp_, ind, score)
    elif (
        ema_bias == "Bullish"
        and (supertrend_bias == "Bullish" or rsi_cross == "Bullish")
        and ind["RSI"] > 50
    ):
        urgency = "MEDIUM"
        action = f"🚀 Long Bias forming → Watch ₹{cmp_:.2f}"
    elif ema_bias == "Bearish" or supertrend_bias == "Bearish":
        urgency = "LOW"
        action = "❌ Avoid / Short Bias Zone"

    # --- Display Panel ---
    console.print(
        f"[bold {clr}]{sym}[/bold {clr}] {badge} | CMP ₹{cmp_:.2f} | RSI {ind['RSI']:.1f} | VWAP {ind['VWAP']:.2f} ({vwap_zone})"
    )
    console.print(
        f"EMA Bias: {ema_bias} | Supertrend: {supertrend_bias} | RSI–EMA: {rsi_cross} | OBV: {ind['OBV']}"
    )
    console.print(
        f"ATR: {ind['ATR']:.2f} | CPR: {ind['CPR']:.2f} | SUPERTREND: {ind['SUPERTREND']:.2f}"
    )
    console.print(
        f"🎯 Action: [{clr}]{action}[/{clr}] | Urgency: [bold]{urgency}[/bold]"
    )
    console.print(
        f"[{urgency_color}]Trend Strength → {trend_bar} {score:.1f}/10[/{urgency_color}]"
    )
    console.print(f"[dim]{'─'*80}[/dim]")

    return {
        "sym": sym,
        "cmp": cmp_,
        "delta": delta,
        "delta_pct": delta_pct,
        "bias": bias,
        "score": score,
        "EMA_BIAS": ema_bias,
        "RSI": ind["RSI"],
        "OBV": ind["OBV"],
        "CPR": ind["CPR"],
        "ATR": ind["ATR"],
        "SUPERTREND_BIAS": supertrend_bias,
        "RSI_CROSS": rsi_cross,
        "VWAP": ind["VWAP"],
        "VWAP_UPPER": ind["VWAP_UPPER"],
        "VWAP_LOWER": ind["VWAP_LOWER"],
        "urgency": urgency,
        "action": action,
    }


# ───────────────────────── HIGH-CONFIDENCE SIGNAL LOGGER ─────────────────────────
def log_high_confidence_signal(sym: str, cmp_: float, ind: dict, score: float):
    """
    Append every HIGH-urgency breakout signal into runtime/high_signals.json
    for daily review or journaling.
    """
    from datetime import datetime
    from pathlib import Path
    import json

    path = Path("runtime/high_signals.json")
    path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "timestamp": now,
        "symbol": sym,
        "cmp": round(cmp_, 2),
        "score": round(score, 1),
        "rsi": round(ind.get("RSI", 0), 1),
        "ema_bias": ind.get("EMA_BIAS", ""),
        "supertrend": ind.get("SUPERTREND_BIAS", ""),
        "rsi_cross": ind.get("RSI_CROSS", ""),
        "vwap_zone": (
            "Overbought"
            if cmp_ >= ind.get("VWAP_UPPER", 0)
            else "Oversold"
            if cmp_ <= ind.get("VWAP_LOWER", 0)
            else "Neutral"
        ),
    }

    try:
        data = []
        if path.exists():
            data = json.loads(path.read_text())
        data.append(record)
        # keep last 100 records
        path.write_text(json.dumps(data[-100:], indent=2))
    except Exception as e:
        console.print(f"[red]⚠️ High-signal log write failed: {e}[/red]")


# ─────────────────────────────── AUTO CLEANUP ────────────────────────────────
def perform_cleanup():
    """Trim old cache and alerts post-EOD."""
    console.rule("[magenta]🧹 Performing End-of-Day Cleanup[/magenta]")
    try:
        if OHL_CACHE_FILE.exists():
            cache = json.loads(OHL_CACHE_FILE.read_text())
            cutoff = datetime.now(tz).date() - timedelta(days=10)
            cleaned = {
                k: v
                for k, v in cache.items()
                if "timestamp" in v
                and datetime.fromisoformat(v["timestamp"]).date() > cutoff
            }
            OHL_CACHE_FILE.write_text(json.dumps(cleaned, indent=2))
            console.print(
                f"[green]✅ OHL cache cleaned — {len(cache) - len(cleaned)} old entries removed[/green]"
            )
        if ALERT_LOG_FILE.exists():
            alerts = json.loads(ALERT_LOG_FILE.read_text())
            if len(alerts) > 200:
                ALERT_LOG_FILE.write_text(json.dumps(alerts[-200:], indent=2))
                console.print("[cyan]🔻 Alerts log trimmed to last 200 entries[/cyan]")
        console.print("[bold magenta]Cleanup complete![/bold magenta]")
    except Exception as e:
        console.print(f"[red]⚠️ Cleanup error: {e}[/red]")


# ───────────────────────── MORNING SUMMARY HELPER ─────────────────────────
def morning_summary():
    """
    Prints top 5 high-confidence signals from runtime/high_signals.json
    sorted by score for quick pre-market review.
    """
    from pathlib import Path
    import json
    from rich.table import Table
    from rich import box

    path = Path("runtime/high_signals.json")
    if not path.exists():
        console.print("[dim]No high-confidence signals logged yet.[/dim]")
        return

    try:
        data = json.loads(path.read_text())
        if not data:
            console.print("[dim]No high-confidence signals logged yet.[/dim]")
            return

        top_signals = sorted(data, key=lambda x: x.get("score", 0), reverse=True)[:5]

        console.rule("[bold cyan]🌅 Morning Signal Summary[/bold cyan]")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Symbol", style="bold cyan")
        table.add_column("Score", justify="right")
        table.add_column("CMP", justify="right")
        table.add_column("RSI", justify="right")
        table.add_column("Bias", justify="center")
        table.add_column("VWAP Zone", justify="center")
        table.add_column("Time", justify="center")

        for s in top_signals:
            table.add_row(
                s["symbol"],
                f"{s['score']:.1f}",
                f"₹{s['cmp']:.2f}",
                f"{s['rsi']:.1f}",
                f"{s['ema_bias']} / {s['supertrend']}",
                s["vwap_zone"],
                s["timestamp"].split(" ")[-1],
            )
        console.print(table)
        console.rule("[dim]──────────────────────────────────────────[/dim]")

    except Exception as e:
        console.print(f"[red]⚠️ Morning summary failed: {e}[/red]")


# ───────────────────────── ARCHIVE VIEWER HELPER ─────────────────────────
def view_archive_summary(target_date: str):
    """
    Quickly view archived high-confidence signals from a specific date.
    Example: view_archive_summary("2025-11-04")
    """
    from pathlib import Path
    import json
    from rich.table import Table
    from rich import box

    archive_path = Path(f"archive/high_signals_{target_date}.json")
    if not archive_path.exists():
        console.print(f"[red]⚠️ No archive found for {target_date}[/red]")
        return

    try:
        data = json.loads(archive_path.read_text())
        if not data:
            console.print(f"[dim]No signals found in archive for {target_date}[/dim]")
            return

        top_signals = sorted(data, key=lambda x: x.get("score", 0), reverse=True)[:5]

        console.rule(f"[bold cyan]📜 Archived Signals for {target_date}[/bold cyan]")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Symbol", style="bold cyan")
        table.add_column("Score", justify="right")
        table.add_column("CMP", justify="right")
        table.add_column("RSI", justify="right")
        table.add_column("Bias", justify="center")
        table.add_column("VWAP Zone", justify="center")
        table.add_column("Time", justify="center")

        for s in top_signals:
            table.add_row(
                s["symbol"],
                f"{s['score']:.1f}",
                f"₹{s['cmp']:.2f}",
                f"{s['rsi']:.1f}",
                f"{s['ema_bias']} / {s['supertrend']}",
                s["vwap_zone"],
                s["timestamp"].split(" ")[-1],
            )
        console.print(table)
        console.rule("[dim]──────────────────────────────────────────────[/dim]")

    except Exception as e:
        console.print(f"[red]⚠️ Archive viewer failed: {e}[/red]")


# ───────────────────────── ARCHIVE STRENGTH ANALYZER ─────────────────────────
def analyze_archive_trend(last_n: int = 5):
    """
    Shows the average signal strength trend from the last N archived days.
    Example output: "Signal Strength → 6.3 → 7.1 → 7.8 ↑"
    """
    from pathlib import Path
    import json
    import re
    from statistics import mean

    archive_dir = Path("archive")
    if not archive_dir.exists():
        console.print("[dim]No archive folder found yet.[/dim]")
        return

    files = sorted(archive_dir.glob("high_signals_*.json"))
    if not files:
        console.print("[dim]No archived signal files found yet.[/dim]")
        return

    # pick the last N files
    files = files[-last_n:]

    daily_averages = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            if not data:
                continue
            avg_score = mean(
                [
                    s.get("score", 0)
                    for s in data
                    if isinstance(s.get("score", 0), (int, float))
                ]
            )
            day = re.findall(r"(\d{4}-\d{2}-\d{2})", f.name)
            label = day[0] if day else f.name
            daily_averages.append((label, round(avg_score, 2)))
        except Exception as e:
            console.print(f"[red]⚠️ Failed to read {f.name}: {e}[/red]")

    if not daily_averages:
        console.print("[dim]No valid archived data for trend analysis.[/dim]")
        return

    # build visual line
    trend_values = [v for _, v in daily_averages]
    direction = (
        "↑"
        if trend_values[-1] > trend_values[0]
        else "↓"
        if trend_values[-1] < trend_values[0]
        else "→"
    )
    trend_line = " → ".join([f"{v:.1f}" for v in trend_values])

    console.rule("[bold magenta]📈 5-Day Signal Strength Trend[/bold magenta]")
    for d, v in daily_averages:
        console.print(f"[cyan]{d}[/cyan] → Avg Score: [bold]{v:.2f}[/bold]")
    console.print(f"[magenta]Signal Strength → {trend_line} {direction}[/magenta]")
    console.rule("[dim]──────────────────────────────────────────────[/dim]")


# ───────────────────────── 7-DAY ROLLING STRENGTH GAUGE ─────────────────────────
def weekly_strength_gauge(last_n: int = 7):
    """
    Displays a simple ASCII strength bar based on the rolling average score
    across the last N archived days (default = 7).
    Example: Strength [██████░░░░] 6.2/10 → Moderately Bullish
    """
    from pathlib import Path
    import json
    from statistics import mean

    archive_dir = Path("archive")
    if not archive_dir.exists():
        console.print("[dim]No archive folder found yet.[/dim]")
        return

    files = sorted(archive_dir.glob("high_signals_*.json"))
    if not files:
        console.print("[dim]No archived signal files found yet.[/dim]")
        return

    # take last N valid archives
    files = files[-last_n:]
    daily_scores = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            if not data:
                continue
            scores = [
                s.get("score", 0)
                for s in data
                if isinstance(s.get("score", 0), (int, float))
            ]
            if scores:
                daily_scores.append(mean(scores))
        except Exception:
            continue

    if not daily_scores:
        console.print("[dim]No valid archived data to compute weekly strength.[/dim]")
        return

    avg_strength = round(mean(daily_scores), 1)
    bar_len = 10
    filled = int(round(avg_strength))
    bar = "█" * filled + "░" * (bar_len - filled)

    if avg_strength >= 8:
        sentiment = "🔥 Strong Bullish"
        color = "green"
    elif avg_strength >= 6:
        sentiment = "💪 Moderately Bullish"
        color = "yellow"
    elif avg_strength >= 4:
        sentiment = "⚖️ Neutral"
        color = "cyan"
    else:
        sentiment = "🔻 Weak / Cautious"
        color = "red"

    console.rule("[bold magenta]📊 7-Day Rolling Strength Gauge[/bold magenta]")
    console.print(
        f"[{color}]Strength [{bar}] {avg_strength}/10 → {sentiment}[/{color}]"
    )
    console.rule("[dim]──────────────────────────────────────────────[/dim]")


# ───────────────────────── MORNING BRIEFING DASHBOARD (ONE-TIME AUTO) ─────────────────────────
def morning_briefing():
    """
    Unified pre-market dashboard that:
      1. Archives and clears yesterday's high signals
      2. Shows top signals from current file (Morning Recap)
      3. Displays 5-day trendline and 7-day rolling strength gauge
      4. Auto-runs only once per day (via .runtime/morning_done.txt flag)
    """
    from datetime import time as _time
    from pathlib import Path
    import json

    console.rule("[bold cyan]🌄 Morning Briefing — Pre-Market Dashboard[/bold cyan]")

    try:
        now = datetime.now(timezone("Asia/Kolkata"))
        today = now.date()
        last_td = last_trading_day(today - timedelta(days=1))
        _now_time = now.time()

        runtime_dir = Path("runtime")
        runtime_dir.mkdir(exist_ok=True)
        flag_file = runtime_dir / "morning_done.txt"

        # 🛑 Check if already triggered today
        if flag_file.exists():
            last_run_date = flag_file.read_text().strip()
            if last_run_date == str(today):
                console.print(
                    f"[dim]🌅 Morning briefing already completed for {today}[/dim]"
                )
                console.rule(
                    "[dim]──────────────────────────────────────────────[/dim]"
                )
                return

        # Only archive before market opens (09:00–09:15)
        if _time(9, 0) <= _now_time < _time(9, 15):
            archive_dir = Path("archive")
            archive_dir.mkdir(exist_ok=True)
            high_log = Path("runtime/high_signals.json")

            if high_log.exists():
                archive_name = f"high_signals_{last_td}.json"
                archive_path = archive_dir / archive_name
                try:
                    archive_path.write_text(high_log.read_text())
                    console.print(f"[dim]📦 Archived {archive_name}[/dim]")

                    # Clear for the new session
                    high_log.write_text("[]")
                    console.print(
                        "[dim]🧹 Cleared current high_signals.json for new session[/dim]"
                    )
                except Exception as e:
                    console.print(f"[red]⚠️ Archival failed: {e}[/red]")

        # 🌄 1️⃣ Morning recap (today’s signals)
        console.rule("[bold cyan]🌅 Morning Recap[/bold cyan]")
        morning_summary()

        # 📈 2️⃣ Multi-day trend analyzer
        analyze_archive_trend()

        # 📊 3️⃣ Weekly rolling gauge
        weekly_strength_gauge()

        # ✅ Mark as completed for the day
        flag_file.write_text(str(today))
        console.print(f"[green]✅ Morning briefing marked complete for {today}[/green]")

        console.print(
            "[dim]Pre-market signal intelligence loaded — ready for live session ⚡[/dim]"
        )
        console.rule("[dim]──────────────────────────────────────────────[/dim]")

    except Exception as e:
        console.print(f"[red]⚠️ Morning briefing failed: {e}[/red]")


# ───────────────────────── ENHANCED MORNING SYSTEM BANNER ─────────────────────────
def morning_system_banner(
    stage: str = "startup", duration: float = None, signals: int = None
):
    """
    Display and log console banners for the Morning Intelligence System with performance stats.

    Args:
        stage (str): One of {"startup", "complete", "skipped"}
        duration (float): Duration of morning briefing (seconds)
        signals (int): Number of signals found during briefing
    """
    log_path = Path("runtime/morning_events.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    perf_info = ""
    if duration is not None:
        perf_info += f" | duration={int(duration)}s"
    if signals is not None:
        perf_info += f" | signals={signals}"

    with open(log_path, "a") as f:
        f.write(f"{ts} | {stage.upper()}{perf_info}\n")

    if stage == "startup":
        console.print(
            "[dim]🧭 Morning Intelligence System active — awaiting 09:00 IST window...[/dim]"
        )
        console.print(
            "[dim]Will auto-run 🌄 Morning Briefing once between 09:00–09:15 each trading day.[/dim]\n"
        )

    elif stage == "complete":
        msg = f"[green]🌞 Morning Intelligence complete — transitioning to live cockpit.[/green]"
        if duration is not None and signals is not None:
            msg += f" [dim](Duration {int(duration)}s | Signals {signals})[/dim]"
        console.print(msg + "\n")

        # Performance trend
        avg_duration, avg_signals = 0, 0
        lines = log_path.read_text().splitlines()
        complete_runs = [l for l in lines if "COMPLETE" in l and "duration" in l]
        if complete_runs:
            last_five = complete_runs[-5:]
            total_dur, total_sig = 0, 0
            for l in last_five:
                try:
                    parts = l.split("|")
                    dur = (
                        [p for p in parts if "duration" in p][0]
                        .split("=")[1]
                        .replace("s", "")
                    )
                    sig = [p for p in parts if "signals" in p][0].split("=")[1]
                    total_dur += int(dur)
                    total_sig += int(sig)
                except Exception:
                    pass
            avg_duration = total_dur / len(last_five)
            avg_signals = total_sig / len(last_five)
            console.print(
                f"[cyan]📊 Avg Morning Performance (last {len(last_five)} runs): "
                f"{avg_duration:.1f}s avg scan | {avg_signals:.1f} signals[/cyan]\n"
            )

    elif stage == "skipped":
        console.print(
            "[cyan]⏭ Morning briefing window passed — running live cockpit directly.[/cyan]\n"
        )

    else:
        console.print(f"[yellow]⚠️ Unknown banner stage: {stage}[/yellow]\n")


def view_last_forecast():
    """
    📜 View the most recent archived forecast plan (v7.2+).
    Displays symbol-wise tactical summary and overall market bias.
    """
    archive_dir = Path("archive")
    if not archive_dir.exists():
        console.print("[yellow]⚠️ No archive folder found yet.[/yellow]")
        return

    # find the most recent forecast file
    forecast_files = sorted(archive_dir.glob("forecast_*.json"), reverse=True)
    if not forecast_files:
        console.print("[yellow]⚠️ No archived forecast files found.[/yellow]")
        return

    latest = forecast_files[0]
    try:
        data = json.loads(latest.read_text())
        console.rule(
            f"[bold cyan]📜 LAST FORECAST PLAN ({latest.stem.replace('forecast_', '')})[/bold cyan]"
        )
        if not data:
            console.print("[dim]No forecast entries available.[/dim]")
            return

        bullish = neutral = weak = 0
        rsis = []
        for row in data:
            sym = row["symbol"]
            bias = row["bias"]
            rsi = row["rsi"]
            rsis.append(rsi)
            setup = row.get("setup", "N/A")
            color = (
                "green"
                if "Bullish" in setup
                else "red"
                if "Weak" in setup
                else "yellow"
            )
            console.print(
                f"[{color}]{sym:<8}[/] → {bias:8} | RSI {rsi:>5.1f} | VWAP {row['vwap']:.2f} | CPR {row['cpr']:.2f} | {setup}"
            )
            if "Bullish" in setup:
                bullish += 1
            elif "Weak" in setup:
                weak += 1
            else:
                neutral += 1

        avg_rsi = sum(rsis) / len(rsis)
        console.rule(
            f"[bold white]Summary:[/bold white] {bullish} Bullish, {neutral} Neutral, {weak} Weak | "
            f"Avg RSI {avg_rsi:.1f} | "
            f"Bias → [cyan]{'Positive' if avg_rsi>55 else 'Negative' if avg_rsi<45 else 'Balanced'}[/cyan]"
        )

        console.print(
            f"[dim]🧾 Source: {latest.name} | {len(data)} symbols reviewed[/dim]\n"
        )

    except Exception as e:
        console.print(f"[red]⚠️ Failed to read forecast file: {e}[/red]")


# ───────────────────────── STARTUP ─────────────────────────
tz = ZoneInfo("Asia/Kolkata")

morning_system_banner("startup")

if __name__ == "__main__":
    handle_market_holiday_or_closed_day()
    view_last_forecast()
    morning_summary()
    analyze_archive_trend()
    weekly_strength_gauge()

    start = datetime.now(tz)
    today = start.date()
    market_open = start.replace(hour=9, minute=15, second=0)
    market_close = start.replace(hour=15, minute=30, second=0)
    live = (market_open <= start < market_close) and is_trading_day(today)

    # ───────────────────────── HOLIDAY CHECK ─────────────────────────
    if not is_trading_day(today):
        console.rule("[bold red]🎌 MARKET HOLIDAY — NSE CLOSED[/bold red]")
        holiday_desc = HOLIDAYS.get(today.strftime("%Y-%m-%d"), "Non-trading day")
        console.print(f"[yellow]{today:%A, %d %B %Y}[/yellow] → {holiday_desc}")

        # Find next trading day
        next_day = today + timedelta(days=1)
        while not is_trading_day(next_day):
            next_day += timedelta(days=1)

        console.print(
            f"[cyan]📅 Next session resumes on {next_day.strftime('%A, %d %B %Y')}[/cyan]"
        )
        console.print("[dim]Cockpit will idle until next trading session.[/dim]\n")

        # Log event
        log_path = Path("runtime/morning_events.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | HOLIDAY | {holiday_desc}\n")

        time.sleep(5)
        sys.exit(0)

    # ───────────────────────── POST-MARKET SAFETY ─────────────────────────
    if not live and start.hour < 23 and is_trading_day(today):
        console.print("[yellow]🕓 Post-Market intraday mode enabled[/yellow]")
        live = True

    last_td = last_trading_day()

    # ───────────────────────── AUTO MORNING SUMMARY TRIGGER ─────────────────────────
    try:
        _now_ist = datetime.now(_tz("Asia/Kolkata")).time()
        if _time(9, 0) <= _now_ist < _time(9, 15):
            console.rule(
                "[bold cyan]🌄 Auto Morning Recap (09:00–09:15 IST)[/bold cyan]"
            )
            start_time = time.time()
            signals_before = 0
            high_log = Path("runtime/high_signals.json")

            if high_log.exists():
                try:
                    data = json.loads(high_log.read_text())
                    signals_before = len(data)
                except Exception:
                    pass

            # Run main morning logic
            morning_briefing()

            signals_after = 0
            if high_log.exists():
                try:
                    data = json.loads(high_log.read_text())
                    signals_after = len(data)
                except Exception:
                    pass

            duration = time.time() - start_time
            signals_found = max(0, signals_after - signals_before)
            morning_system_banner("complete", duration, signals_found)

            # Archive and clear
            archive_dir = Path("archive")
            archive_dir.mkdir(exist_ok=True)
            if high_log.exists():
                try:
                    archive_name = f"high_signals_{last_trading_day()}.json"
                    archive_path = archive_dir / archive_name
                    archive_path.write_text(high_log.read_text())
                    console.print(f"[dim]📦 Archived {archive_name}[/dim]")
                    high_log.write_text("[]")
                    console.print(
                        "[dim]🧹 Cleared current high_signals.json for new session[/dim]"
                    )
                except Exception as e:
                    console.print(f"[red]⚠️ Archival failed: {e}[/red]")

            console.print(
                "[dim]Pre-market signal scan complete — switching to live cockpit...[/dim]\n"
            )

        elif _now_ist >= _time(9, 15):
            morning_system_banner("skipped")

    except Exception as e:
        console.print(f"[red]⚠️ Auto-summary trigger failed: {e}[/red]")

    # ───────────────────────── HEADER BUILDER ─────────────────────────
    def header(top, bottom, cycles):
        now = datetime.now(tz)
        up = now - start
        mm, ss = divmod(int(up.total_seconds()), 60)
        alerts = (
            json.loads(ALERT_LOG_FILE.read_text()) if ALERT_LOG_FILE.exists() else []
        )
        active = [a for a in alerts[-50:] if a.get("urgency") == "HIGH"]
        session = "LIVE" if live else "EOD"

        return Panel.fit(
            f"🕒 {now:%H:%M:%S} | Session: {session} | Service Day {ACTIVE_SERVICE_DAY}\n"
            f"🟢 Cache Hits {CACHE_HITS}  🟡 Refresh {CACHE_REFRESHES} | ⚡ Active Alerts {len(active)}\n"
            f"🔥 Top {top['sym']} {top['delta_pct']:+.2f}% | 📉 Weakest {bottom['sym']} {bottom['delta_pct']:+.2f}%\n"
            f"⏱ Runtime {mm}m {ss}s | Cycles {cycles}",
            border_style="bright_black",
            title="Market Cockpit",
        )

    # ───────────────────────── LIVE DASHBOARD LOOP ─────────────────────────
    with Live(console=console, refresh_per_second=2, transient=False) as live_view:
        cycles = 0
        while True:
            cycles += 1
            movers = []
            for sym, key in TICKERS.items():
                info = render_card(sym, key, not live)
                if info:
                    movers.append(info)

            if not movers:
                continue

            top = max(movers, key=lambda x: x["delta_pct"])
            bottom = min(movers, key=lambda x: x["delta_pct"])

            table = Table(
                show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY
            )
            for c in ("Rank", "Symbol", "Δ %", "Bias", "⚡"):
                table.add_column(c, justify="center")

            for i, m in enumerate(
                sorted(movers, key=lambda x: x["delta_pct"], reverse=True)[:5], 1
            ):
                color = (
                    "green"
                    if m["delta_pct"] > 0.2
                    else "red"
                    if m["delta_pct"] < -0.2
                    else "yellow"
                )
                table.add_row(
                    str(i),
                    m["sym"],
                    f"[{color}]{m['delta_pct']:+.2f}%[/]",
                    m["bias"],
                    "⚡" if m["urgency"] == "HIGH" else "",
                )

            group = Group(header(top, bottom, cycles), table)
            live_view.update(group)

            now = datetime.now(tz)
            if now >= market_close and not is_trading_day(
                now.date() + timedelta(days=1)
            ):
                perform_cleanup()
                break

            wait_until_next_boundary(REFRESH_MINUTES)

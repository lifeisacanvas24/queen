#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
#  intraday_cockpit_expanded_v4.py
#
#  📊 Advanced Intraday Market Cockpit
#  --------------------------------------------------------
#  • Live intraday and EOD detection
#  • UC/LC auto-fetch via NSE API with persistent caching
#  • Targets, Stoploss & Re-entry tracking (persistent)
#  • Top/Bottom movers summary with event logging
#  • Holiday awareness & session labeling
#  • Modular, readable layout (each layer cleanly separated)
#
#  Author  : ChatGPT Quant Build v4 (for Aravind)
#  Version : 4.0  |  Updated : 2025-11-03
# ─────────────────────────────────────────────────────────────────────────────

import os, sys
import time
import json
from datetime import datetime, date, timedelta
import numpy as np
import polars as pl
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from pathlib import Path
from rich.live import Live
from rich.layout import Layout
from rich.table import Table, box, Text
from rich.panel import Panel
from rich.align import Align
import math
import os
from datetime import datetime, timedelta
import glob
from collections import defaultdict
import re

# ───────────────────────── CONFIG ─────────────────────────
ENABLE_DEBUG_LOGGING = True
REFRESH_MINUTES = 3
NSE_CACHE_REFRESH_MINUTES = 30  # configurable auto-refresh for UC/LC cache
HEADERS = {"Accept": "application/json"}

TICKERS = {
    "NETWEB": "NSE_EQ|INE0NT901020",
    "SMLISUZU": "NSE_EQ|INE294B01019",
    "FORCEMOT": "NSE_EQ|INE451A01017",  # add more if needed
}


# Add to config area
VDU_MODE = True  # True = live-updating dashboard, False = normal scroll mode
PAGE_SIZE = 3  # number of symbols per VDU page
VDU_PAGE_INDEX = 0

# ───────────────────────── PATHS ─────────────────────────
ROOT = (
    Path.home()
    / "Library/Mobile Documents/com~apple~CloudDocs/projects/git-repos/gsheetapps/queen"
)
DATA_DIR = ROOT / "data"
RUNTIME_DIR = DATA_DIR / "runtime"
STATE_DIR = RUNTIME_DIR / "state"
LOG_DIR = RUNTIME_DIR / "logs"
HOLIDAY_FILE = DATA_DIR / "static/nse_holidays.json"
UC_LC_CACHE_FILE = STATE_DIR / "nse_bands_cache.json"

for p in [STATE_DIR, LOG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

console = Console()
LAST_CMP = {sym: None for sym in TICKERS}


# ───────────────────────── LOGGING UTILITIES (UPDATED) ─────────────────────────
# ───────────────────────── ROTATING EVENT LOGGER ─────────────────────────
def log_event(msg: str, event_type: str = "INFO"):
    """
    Write timestamped log entries to daily log files.
    ✅ Auto-creates a new log file each trading day
    ✅ Prunes logs older than 7 days automatically
    ✅ Keeps log directory clean
    ✅ Non-blocking (won’t interrupt main loop)
    """
    from datetime import datetime, timedelta

    # Ensure log directory exists
    os.makedirs(STATE_DIR, exist_ok=True)

    # Daily log filename, e.g. intraday_events_2025-11-03.log
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_file = STATE_DIR / f"intraday_events_{today_str}.log"

    # Prepare entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{event_type}] {msg}\n"

    try:
        # Write to today's log
        with open(log_file, "a") as f:
            f.write(entry)
    except Exception:
        pass  # never block the main cockpit loop

    # Optional echo for visible alerts
    if event_type in {"UC/LC", "ERR", "WARN"}:
        console.print(f"[bold yellow]{entry.strip()}[/bold yellow]")

    # ───────────────────────── Auto-clean old logs (>7 days) ─────────────────────────
    try:
        cutoff = datetime.now() - timedelta(days=7)
        for f_name in os.listdir(STATE_DIR):
            if f_name.startswith("intraday_events_") and f_name.endswith(".log"):
                try:
                    date_str = f_name.replace("intraday_events_", "").replace(
                        ".log", ""
                    )
                    f_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if f_date < cutoff:
                        os.remove(STATE_DIR / f_name)
                        console.print(f"[dim]🧹 Removed old log: {f_name}[/dim]")
                except Exception:
                    continue
    except Exception:
        pass


# ───────────────────────── HOLIDAY UTILITIES ─────────────────────────
def load_nse_holidays():
    """Return dict {date: description} for NSE holidays."""
    try:
        with open(HOLIDAY_FILE, "r") as f:
            data = json.load(f)
        return {str(d["date"]): d.get("description", "") for d in data if "date" in d}
    except Exception:
        return {}


HOLIDAYS = load_nse_holidays()


def is_trading_day(d: date) -> bool:
    ds = d.strftime("%Y-%m-%d")
    return d.weekday() < 5 and ds not in HOLIDAYS


def last_trading_day(target: date | None = None) -> str:
    if target is None:
        target = date.today()
    d = target
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


_last_printed_trading_day = None


# ───────────────────────── UC/LC CACHE UTILITIES ─────────────────────────
UC_LC_CACHE = {}


def load_uc_lc_cache():
    """Load persistent UC/LC band cache (auto resets if older than refresh interval)."""
    global UC_LC_CACHE
    try:
        if UC_LC_CACHE_FILE.exists():
            with open(UC_LC_CACHE_FILE, "r") as f:
                cache = json.load(f)
            # check expiry
            ts = datetime.fromisoformat(cache.get("_timestamp", "2000-01-01T00:00:00"))
            if datetime.now() - ts < timedelta(minutes=NSE_CACHE_REFRESH_MINUTES):
                UC_LC_CACHE = cache
                if ENABLE_DEBUG_LOGGING:
                    console.print(
                        f"[dim]💾 UC/LC cache loaded ({len(cache)-1} symbols)[/dim]"
                    )
                return
        UC_LC_CACHE = {"_timestamp": datetime.now().isoformat()}
        save_uc_lc_cache()
    except Exception as e:
        console.print(f"[red]UC/LC cache load failed: {e}[/red]")
        UC_LC_CACHE = {"_timestamp": datetime.now().isoformat()}


def save_uc_lc_cache():
    """Persist UC/LC band cache."""
    try:
        UC_LC_CACHE["_timestamp"] = datetime.now().isoformat()
        with open(UC_LC_CACHE_FILE, "w") as f:
            json.dump(UC_LC_CACHE, f, indent=2)
    except Exception as e:
        console.print(f"[red]UC/LC cache save failed: {e}[/red]")


load_uc_lc_cache()


# ───────────────────────── NSE UC/LC FETCHER ─────────────────────────
def fetch_nse_bands(symbol: str, cache_refresh_minutes: int = 30) -> dict | None:
    """
    Fetch UC/LC price bands for a symbol using NSE's public API.
    ✅ Auto-casts values to float before caching (prevents mixed-type math errors)
    ✅ Persists cache for current trading day under STATE_DIR/nse_bands_cache.json
    ✅ Refreshes cache if data is older than `cache_refresh_minutes`
    ✅ Logs cache hits/misses via log_event()
    """
    from datetime import datetime

    os.makedirs(STATE_DIR, exist_ok=True)
    cache_file = os.path.join(STATE_DIR, "nse_bands_cache.json")

    # ───────────────────────── Load cache safely ─────────────────────────
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cache = json.load(f)
            # Retroactive coercion of stored string values to float
            for sym in list(cache.keys()):
                bands = cache[sym].get("bands", {})
                for k, v in list(bands.items()):
                    try:
                        bands[k] = float(v)
                    except Exception:
                        bands[k] = None
        else:
            cache = {}
    except Exception:
        cache = {}

    today_str = date.today().strftime("%Y-%m-%d")

    # ───────────────────────── Use cached value if fresh ─────────────────────────
    if symbol in cache:
        entry = cache[symbol]
        if (
            entry.get("date") == today_str
            and (datetime.now().timestamp() - entry.get("timestamp", 0))
            < cache_refresh_minutes * 60
        ):
            bands = entry.get("bands", {})
            # Ensure floats before returning
            for k, v in list(bands.items()):
                try:
                    bands[k] = float(v)
                except Exception:
                    bands[k] = None
            log_event(f"NSE UC/LC cache hit for {symbol}", event_type="CACHE")
            return bands

    # ───────────────────────── NSE API Fetch ─────────────────────────
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
        "Host": "www.nseindia.com",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }

    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

    try:
        with requests.Session() as s:
            # Warm-up request to get cookies
            s.get("https://www.nseindia.com", headers=headers, timeout=5)
            r = s.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                console.print(
                    f"[yellow]⚠️ NSE fetch failed for {symbol}: HTTP {r.status_code}[/yellow]"
                )
                log_event(
                    f"NSE fetch failed for {symbol}: HTTP {r.status_code}",
                    event_type="WARN",
                )
                return None

            data = r.json()

        price_info = data.get("priceInfo", {})
        if not price_info:
            console.print(
                f"[yellow]⚠️ No UC/LC info for {symbol} in NSE response[/yellow]"
            )
            log_event(f"No UC/LC info returned for {symbol}", event_type="WARN")
            return None

        def safe_float(x):
            try:
                return float(x)
            except Exception:
                return None

        upper = safe_float(price_info.get("upperCP"))
        lower = safe_float(price_info.get("lowerCP"))
        prev_close = safe_float(price_info.get("previousClose"))

        band_data = {
            "upper_circuit": upper,
            "lower_circuit": lower,
            "prev_close": prev_close,
        }

        # Cache persistently
        cache[symbol] = {
            "date": today_str,
            "timestamp": datetime.now().timestamp(),
            "bands": band_data,
        }

        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

        log_event(f"Fetched fresh UC/LC data for {symbol}", event_type="INFO")
        return band_data

    except Exception as e:
        console.print(f"[yellow]⚠️ UC/LC fetch error for {symbol}: {e}[/yellow]")
        log_event(f"UC/LC fetch error for {symbol}: {e}", event_type="ERR")
        return None


# ───────────────────────── INTRADAY FETCHERS ─────────────────────────
def fetch_intraday(key: str) -> pl.DataFrame | None:
    """Fetch intraday 15-min candles with numeric schema."""
    url = f"https://api.upstox.com/v3/historical-candle/intraday/{key}/minutes/15"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        j = r.json()
        if "data" not in j or not j["data"].get("candles"):
            raise ValueError("No intraday candles returned")
        records = []
        for c in j["data"]["candles"]:
            try:
                ts, o, h, l, cl, v = c[:6]
                records.append((ts, float(o), float(h), float(l), float(cl), float(v)))
            except Exception:
                continue
        return pl.DataFrame(
            records,
            schema=["time", "open", "high", "low", "close", "volume"],
            orient="row",
        ).sort("time")
    except Exception as e:
        console.print(f"[red]⚠️ Intraday fetch failed: {e}[/red]")
        return None


def fetch_daily_ohl(key: str) -> dict | None:
    """Fetch OHL for today or last valid trading day (holiday aware)."""
    global _last_printed_trading_day
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    trading_day = last_trading_day(today)

    if _last_printed_trading_day != trading_day:
        console.print(
            f"[dim]📅 Using OHL from {trading_day} (last valid trading day)[/dim]"
        )
        if today_str in HOLIDAYS:
            console.print(
                f"[yellow]🏖 Market Holiday today → {HOLIDAYS[today_str]}[/yellow]"
            )
        _last_printed_trading_day = trading_day

    url = f"https://api.upstox.com/v3/historical-candle/{key}/days/1/{trading_day}/{trading_day}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_ACCESS_TOKEN', '')}",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        j = r.json()
        if "data" not in j or not j["data"].get("candles"):
            return None
        o, h, l, c, v = j["data"]["candles"][-1][1:6]
        return {
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "prev_close": float(c),
        }
    except Exception as e:
        console.print(f"[red]OHL fetch failed: {e}[/red]")
        return None


def ensure_ohl(key: str, df: pl.DataFrame) -> dict:
    ohl = fetch_daily_ohl(key)
    if not ohl and df is not None and not df.is_empty():
        ohl = {
            "open": float(df["open"][0]),
            "high": float(df["high"].max()),
            "low": float(df["low"].min()),
            "prev_close": float(df["close"][-2])
            if len(df) > 1
            else float(df["close"][0]),
        }
    return ohl


# ───────────────────────── INDICATORS ─────────────────────────
def indicators(df: pl.DataFrame) -> dict:
    if df.is_empty():
        return {"CPR": 0, "VWAP": 0, "ATR": 0, "RSI": 50, "OBV": "Flat"}

    typical = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical * df["volume"]).sum() / df["volume"].sum()
    h, l, c = df["high"][-1], df["low"][-1], df["close"][-1]
    pivot = (h + l + c) / 3
    bc, tc = (h + l) / 2, 2 * pivot - (h + l) / 2
    cpr = (bc + tc) / 2
    tr = df["high"] - df["low"]
    atr = float(tr.tail(min(len(df), 14)).mean()) * 0.5

    closes = df["close"].to_numpy()
    delta = np.diff(closes)
    gains, losses = np.clip(delta, 0, None), np.clip(-delta, 0, None)
    avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains)
    avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses)
    rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss != 0 else 100

    obv = [0]
    vols = df["volume"].to_numpy()
    for i in range(1, len(closes)):
        obv.append(obv[-1] + vols[i] * (1 if closes[i] > closes[i - 1] else -1))
    obv_trend = "Rising" if obv[-1] > obv[0] else "Falling"

    return {
        "CPR": round(cpr, 2),
        "VWAP": round(vwap, 2),
        "ATR": round(atr, 2),
        "RSI": round(rsi, 2),
        "OBV": obv_trend,
    }


def build_vdu_dashboard(movers_data: list, refresh_time: str, session: str):
    """Render full paged VDU dashboard — rotates through symbols automatically."""
    global VDU_PAGE_INDEX

    # ───────────────────────── Summary Table ─────────────────────────
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY)
    table.add_column("Symbol", justify="left", style="bold white")
    table.add_column("CMP (₹)", justify="right")
    table.add_column("Δ%", justify="right")
    table.add_column("Bias", justify="center")
    table.add_column("Score", justify="center")
    table.add_column("RSI", justify="center")
    table.add_column("OBV", justify="center")

    movers_sorted = sorted(
        movers_data, key=lambda x: x.get("delta_pct", 0), reverse=True
    )

    for m in movers_sorted:
        color = (
            "green"
            if m.get("delta", 0) > 0
            else "red"
            if m.get("delta", 0) < 0
            else "white"
        )
        bias_color = (
            "green"
            if "Long" in m["bias"]
            else "yellow"
            if "Neutral" in m["bias"]
            else "red"
            if "Weak" in m["bias"]
            else "white"
        )
        table.add_row(
            m["sym"],
            f"[{color}]{m['cmp']:.2f}[/{color}]",
            f"[{color}]{m['delta_pct']:+.2f}%[/{color}]",
            f"[{bias_color}]{m['bias']}[/{bias_color}]",
            f"{m['score']:.1f}",
            f"{m['RSI']:.1f}",
            m["OBV"],
        )

    # ───────────────────────── Pagination logic ─────────────────────────
    total = len(movers_sorted)
    if total == 0:
        return Panel("No symbols loaded", title="📊 Intraday Cockpit")

    total_pages = math.ceil(total / PAGE_SIZE)
    start_idx = (VDU_PAGE_INDEX % total_pages) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_symbols = movers_sorted[start_idx:end_idx]
    VDU_PAGE_INDEX += 1  # advance page for next refresh

    # ───────────────────────── Card grid for current page ─────────────────────────
    card_grid = Table.grid(padding=1)
    for m in page_symbols:
        t1 = round(m["cmp"] + m["ATR"] * 0.8, 2)
        t2 = round(m["cmp"] + m["ATR"] * 1.6, 2)
        t3 = round(m["cmp"] + m["ATR"] * 2.0, 2)
        sl = round(m["cmp"] - m["ATR"] * 1.0, 2)

        uc_label = "🚀 UC Locked" if m.get("uc_locked") else ""
        lc_label = "💀 LC Locked" if m.get("lc_locked") else ""

        reentry_logic = "🔔 Re-entry if CPR reclaim + OBV Rising"
        summary = (
            f"Momentum continuation above VWAP"
            if m["bias"] == "Long"
            else f"Below CPR; fading structure"
            if m["bias"] == "Weak"
            else "Near VWAP consolidation"
        )

        t1_flag = m.get("t_flags", {}).get("T1", "⚪")
        t2_flag = m.get("t_flags", {}).get("T2", "⚪")
        t3_flag = m.get("t_flags", {}).get("T3", "⚪")

        content = (
            f"[bold]{m['sym']}[/bold] | CMP ₹{m['cmp']:.2f} | Bias: {m['bias']} | Score: {m['score']:.1f}\n"
            f"[dim]O:[/dim] {m['cmp'] - 30:.2f}  [dim]H:[/dim] {m['cmp'] + 30:.2f}  [dim]L:[/dim] {m['cmp'] - 60:.2f}\n"
            f"[cyan]Targets →[/cyan] "
            f"T1 ₹{t1} {t1_flag} | T2 ₹{t2} {t2_flag} | T3 ₹{t3} {t3_flag} | SL ₹{sl} 🧯\n"
            f"[dim]CPR:[/dim] {m['CPR']} | [dim]ATR:[/dim] {m['ATR']} | [dim]RSI:[/dim] {m['RSI']:.1f}\n"
            f"[blue]{reentry_logic}[/blue]\n"
            f"[magenta]Summary:[/magenta] {summary}\n"
        )

        if uc_label or lc_label:
            content += (
                f"[bold green]{uc_label}[/bold green][bold red]{lc_label}[/bold red]\n"
            )

        card = Panel(
            Align.left(Text.from_markup(content)),
            border_style="bright_black",
            title=f"[bold cyan]{m['sym']}[/bold cyan]",
            padding=(0, 1),
        )
        card_grid.add_row(card)

    # ───────────────────────── Bottom Summary Lines ─────────────────────────
    top_line, movers_line = "", ""
    if movers_sorted:
        top = movers_sorted[0]
        bottom = movers_sorted[-1]
        top_line = (
            f"[bold green]🔥 Top Mover:[/bold green] "
            f"{top['sym']} +₹{top['delta']:+.2f} (+{top['delta_pct']:.2f}%)  "
            f"[bold red]| 📉 Weakest:[/bold red] "
            f"{bottom['sym']} ₹{bottom['delta']:+.2f} ({bottom['delta_pct']:.2f}%)"
        )
        movers_line = "[bold blue]🏁 Movers:[/bold blue] " + " ".join(
            [
                f"[bright_cyan]{i+1}️⃣ {m['sym']} {m['delta_pct']:+.1f}%[/bright_cyan]"
                for i, m in enumerate(movers_sorted[:5])
            ]
        )

    # ───────────────────────── Final Layout ─────────────────────────
    layout = Layout()
    layout.split_column(
        Layout(Panel(table, title="📈 Market Snapshot")),
        Layout(
            Panel(
                card_grid,
                title=f"📄 Page {VDU_PAGE_INDEX % total_pages + 1}/{total_pages}",
            )
        ),
        Layout(Text.from_markup(top_line + "\n" + movers_line)),
    )

    header = f"📊 Intraday Cockpit — {session} | 🕒 Last updated: {refresh_time}"

    return Panel(layout, title=header, border_style="bold blue", padding=(1, 2))


# ───────────────────────── TARGET/STOPLOSS STATE ─────────────────────────
STATE_FILE = STATE_DIR / "targets_state.json"
LOG_FILE = STATE_DIR / "intraday_events.log"


def load_target_state() -> dict:
    """Load persistent memory of targets, SLs, re-entry."""
    try:
        if not STATE_FILE.exists():
            return {
                "meta": {"last_reset": last_trading_day()},
                "symbols": {
                    s: {
                        "T1": False,
                        "T2": False,
                        "T3": False,
                        "SL": False,
                        "REENTRY": False,
                    }
                    for s in TICKERS
                },
            }
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        td = last_trading_day()
        if data.get("meta", {}).get("last_reset") != td:
            console.print(
                f"[yellow]🔄 Auto-resetting state for new trading day: {td}[/yellow]"
            )
            data = {
                "meta": {"last_reset": td},
                "symbols": {
                    s: {
                        "T1": False,
                        "T2": False,
                        "T3": False,
                        "SL": False,
                        "REENTRY": False,
                    }
                    for s in TICKERS
                },
            }
        return data
    except Exception:
        return {
            "meta": {"last_reset": last_trading_day()},
            "symbols": {
                s: {
                    "T1": False,
                    "T2": False,
                    "T3": False,
                    "SL": False,
                    "REENTRY": False,
                }
                for s in TICKERS
            },
        }


def save_target_state(state: dict):
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


TARGET_STATE = load_target_state()


# ───────────────────────── RENDER ENGINE ─────────────────────────
def render_card(sym, key, eod_mode=False):
    """Render rich console card for a symbol with actionable signals."""
    df = fetch_intraday(key) if not eod_mode else pl.DataFrame()
    if df is None or df.is_empty():
        return None

    ohl = ensure_ohl(key, df)
    ind = indicators(df)
    cmp_ = float(df["close"][-1])

    # ΔCMP tracking
    prev_cmp = LAST_CMP[sym]
    LAST_CMP[sym] = cmp_
    delta, delta_pct = 0, 0
    if prev_cmp:
        delta = cmp_ - prev_cmp
        delta_pct = (delta / prev_cmp) * 100

    # Base score calculation
    score = round(
        (ind["RSI"] / 15)
        + (1 if ind["OBV"] == "Rising" else 0)
        + (abs(cmp_ - ind["VWAP"]) / max(ind["ATR"], 1) < 0.1) * 2,
        1,
    )
    if score >= 6:
        bias, clr, badge = "Long", "green", "🟢"
    elif score >= 4:
        bias, clr, badge = "Neutral", "yellow", "🟡"
    else:
        bias, clr, badge = "Weak", "red", "🔴"

    atr = max(ind["ATR"], 25)
    t1, t2, t3 = [round(cmp_ + atr * x, 2) for x in (0.8, 1.6, 2.0)]
    sl = round(cmp_ - atr * 1.0, 2)

    # ───────────────────────── UC/LC Detection ─────────────────────────
    bands = fetch_nse_bands(sym)
    uc_txt, lc_txt = "", ""
    circuit_txt = ""

    if bands:
        uc = bands.get("upper_circuit")
        lc = bands.get("lower_circuit")
        prev_close = bands.get("prev_close", ohl["prev_close"] if ohl else None)

        try:
            uc = float(uc) if uc is not None else None
            lc = float(lc) if lc is not None else None
            prev_close = float(prev_close) if prev_close is not None else None
        except Exception:
            console.print(
                f"[yellow]⚠️ Invalid UC/LC data types for {sym} — skipping check[/yellow]"
            )
            uc, lc, prev_close = None, None, None

        if uc and abs(cmp_ - uc) <= 0.1:
            uc_txt = f"[bold green]🚀 UC Locked ({cmp_} ≈ {uc})[/bold green]"
            bias, clr, badge = "UC Locked", "green", "🟢"
            score = 10.0
            log_event(
                f"🚀 UC Locked detected: {sym} at ₹{cmp_} (+{((cmp_ - prev_close)/prev_close)*100:.2f}%)"
            )
        elif lc and abs(cmp_ - lc) <= 0.1:
            lc_txt = f"[bold red]💀 LC Locked ({cmp_} ≈ {lc})[/bold red]"
            bias, clr, badge = "LC Locked", "red", "🔴"
            score = 0.0
            log_event(
                f"💀 LC Locked detected: {sym} at ₹{cmp_} ({((cmp_ - prev_close)/prev_close)*100:.2f}%)"
            )
        elif not uc and not lc:
            console.print(
                f"[yellow]⚠️ UC/LC keys missing for {sym} in NSE response[/yellow]"
            )
        else:
            console.print(f"[yellow]⚠️ No UC/LC lock condition met for {sym}[/yellow]")
    else:
        console.print(f"[yellow]⚠️ No UC/LC info for {sym}[/yellow]")

    # ───────────────────────── Display ─────────────────────────
    header = (
        f"[bold {clr}]{sym}[/bold {clr}] {badge} | "
        f"CMP ₹{cmp_:.2f} | VWAP {ind['VWAP']:.2f} | RSI {ind['RSI']:.2f} | OBV {ind['OBV']}"
    )
    console.print(header)
    console.print(f"[dim]{'─'*90}[/dim]")
    console.print(
        f"O:{ohl['open']:.2f}  H:{ohl['high']:.2f}  L:{ohl['low']:.2f}  PrevC:{ohl['prev_close']:.2f}"
    )

    if uc_txt:
        console.print(uc_txt)
    elif lc_txt:
        console.print(lc_txt)
    elif circuit_txt:
        console.print(circuit_txt)

    console.print(f"Targets → T1 ₹{t1} | T2 ₹{t2} | T3 ₹{t3} | SL ₹{sl}")
    console.print(
        f"CPR: {ind['CPR']} | ATR: {ind['ATR']} | Bias: {bias} | Score {score}/10"
    )

    # ───────────────────────── Action Signal Section ─────────────────────────
    action = "WAIT / OBSERVE"
    action_color = "yellow"
    next_target = None
    action_note = ""
    confidence = score

    if bias == "Long" and ind["RSI"] > 60 and ind["OBV"] == "Rising":
        action = "ENTER LONG"
        action_color = "green"
        next_target = t1 if cmp_ < t1 else t2 if cmp_ < t2 else t3
        action_note = "Momentum strong; near-term continuation likely."
    elif bias == "Weak" or ind["RSI"] < 40:
        action = "AVOID / SHORT BIAS"
        action_color = "red"
        next_target = sl
        action_note = "Weak structure; below VWAP/CPR."
    elif bias == "Neutral":
        action = "WAIT FOR CONFIRMATION"
        action_color = "yellow"
        action_note = "Neutral zone; watch VWAP breakout."

    console.print("")
    console.print(f"🎯 Action: [{action_color}]{action}[/{action_color}]")
    if next_target:
        console.print(f"Next Target: ₹{next_target:.2f} | Stoploss: ₹{sl:.2f}")
    console.print(f"Confidence: [bold cyan]{confidence:.1f}/10[/bold cyan]")
    if action_note:
        console.print(f"[dim]{action_note}[/dim]")

    console.print(f"[dim]{'─'*90}[/dim]\n")

    return {
        "sym": sym,
        "cmp": cmp_,
        "delta": delta,
        "delta_pct": delta_pct,
        "bias": bias,
        "score": score,
        "CPR": ind["CPR"],
        "ATR": ind["ATR"],
        "RSI": ind["RSI"],
        "OBV": ind["OBV"],
        "uc_locked": "UC Locked" in bias,
        "lc_locked": "LC Locked" in bias,
        "action": action,
        "next_target": next_target,
        "stoploss": sl,
        "confidence": confidence,
    }


# ───────────────────────── MOVERS SUMMARY + EVENT TRACKING ─────────────────────────
def process_symbols(eod_mode=False):
    """Process each symbol, handle events (targets, SL, reentry), log & summarize."""
    movers = []
    state_changed = False

    for sym, key in TICKERS.items():
        try:
            info = render_card(sym, key, eod_mode)
            if not info:
                continue

            cmp_ = info["cmp"]
            delta = info["delta"]
            delta_pct = info["delta_pct"]

            # restore memory
            memory = TARGET_STATE["symbols"].get(
                sym,
                {"T1": False, "T2": False, "T3": False, "SL": False, "REENTRY": False},
            )

            atr = 25
            t1, t2, t3 = [round(cmp_ + atr * x, 2) for x in (0.8, 1.6, 2.0)]
            sl = round(cmp_ - atr * 1.0, 2)

            # Target checks
            if cmp_ >= t1 and not memory["T1"]:
                console.print(f"[bold green]🏁 {sym} hit T1![/bold green]")
                log_event(f"{sym} hit T1 at ₹{cmp_}")
                memory["T1"] = True
                state_changed = True
            if cmp_ >= t2 and not memory["T2"]:
                console.print(f"[bold yellow]🏆 {sym} hit T2![/bold yellow]")
                log_event(f"{sym} hit T2 at ₹{cmp_}")
                memory["T2"] = True
                state_changed = True
            if cmp_ >= t3 and not memory["T3"]:
                console.print(f"[bold cyan]🥇 {sym} hit T3![/bold cyan]")
                log_event(f"{sym} hit T3 at ₹{cmp_}")
                memory["T3"] = True
                state_changed = True

            # Stoploss check
            if cmp_ <= sl and not memory["SL"]:
                console.print(
                    f"[bold red]💀 {sym} Stop-loss hit at ₹{cmp_}![/bold red]"
                )
                log_event(f"{sym} Stop-loss hit at ₹{cmp_}")
                memory["SL"] = True
                state_changed = True

            # Re-entry check (simplified momentum reclaim)
            if not memory["REENTRY"] and delta > 0 and cmp_ > t1:
                console.print(
                    f"[magenta]🔔 {sym} Re-entry triggered (momentum reclaim)![/magenta]"
                )
                log_event(f"{sym} Re-entry triggered (momentum reclaim)")
                memory["REENTRY"] = True
                state_changed = True

            TARGET_STATE["symbols"][sym] = memory
            movers.append(info)

        except Exception as e:
            console.print(f"[red]{sym}: {e}[/red]")

    if state_changed:
        save_target_state(TARGET_STATE)

    # mover summary
    if movers:
        movers_sorted = sorted(movers, key=lambda x: x["delta_pct"], reverse=True)
        top = movers_sorted[0]
        bottom = movers_sorted[-1]

        console.print(
            f"[bold green]🔥 Top Mover:[/bold green] {top['sym']} +₹{top['delta']:.2f} (+{top['delta_pct']:.2f}%)  "
            f"[bold red]| 📉 Weakest:[/bold red] {bottom['sym']} ₹{bottom['delta']:.2f} ({bottom['delta_pct']:.2f}%)"
        )

        ranks = []
        for i, m in enumerate(movers_sorted[:5], 1):
            ranks.append(f"{i}️⃣ {m['sym']} {m['delta_pct']:+.1f}%")
        summary_line = " | ".join(ranks)
        console.print(f"[bold cyan]🏁 Movers: {summary_line}[/bold cyan]\n")
        log_event(f"MOVERS: {summary_line}")


# ───────────────────────── SMART REFRESH ─────────────────────────
def wait_until_next_boundary(interval_minutes: int):
    now = datetime.now()
    interval = timedelta(minutes=interval_minutes)
    next_boundary = (
        (now - datetime.min) // interval * interval + interval + datetime.min
    )
    sleep_seconds = (next_boundary - now).total_seconds()
    next_time = now + timedelta(seconds=sleep_seconds)
    console.print(
        f"[dim]⏳ Next refresh at {next_time.strftime('%H:%M:%S')} (in {sleep_seconds/60:.1f} min)[/dim]"
    )
    time.sleep(sleep_seconds)


# ───────────────────────── LOG SUMMARY HELPER (MULTI-DAY) ───────────────────
# ───────────────────────── LOG SUMMARY HELPER (ENHANCED) ─────────────────────────
# ───────────────────────── LOG SUMMARY HELPER (v3 — EXPORT METADATA) ─────────────────────────
def summarize_logs(days: int = 1, export: bool = False):
    """
    Summarize last N days of intraday logs with analytics and exportable metadata.
    Exports a CSV containing:
      - Symbol event counts (UC, LC, Target, SL, Re-entry)
      - Header section with Cache Hit Rate, UC/LC counts, and Log Time Window
    """
    import glob
    from datetime import datetime, timedelta
    from collections import defaultdict

    cutoff = datetime.now() - timedelta(days=days)
    log_files = sorted(glob.glob(str(STATE_DIR / "intraday_events_*.log")))

    stats = {
        "UC/LC": 0,
        "TARGET": 0,
        "STOPLOSS": 0,
        "REENTRY": 0,
        "CACHE": 0,
        "WARN": 0,
        "ERR": 0,
        "INFO": 0,
    }

    symbol_stats = defaultdict(
        lambda: {"UC": 0, "LC": 0, "TARGET": 0, "SL": 0, "REENTRY": 0}
    )
    uc_symbols, lc_symbols = set(), set()
    first_time, last_time = None, None
    total_lines = 0
    cache_hits, cache_misses = 0, 0

    # ─────────────── Parse logs ───────────────
    for path in log_files:
        fname = os.path.basename(path)
        try:
            f_date = datetime.strptime(
                fname.replace("intraday_events_", "").replace(".log", ""), "%Y-%m-%d"
            )
        except Exception:
            continue
        if f_date < cutoff:
            continue

        with open(path, "r") as f:
            for line in f:
                total_lines += 1
                # detect time
                if "[" in line and "]" in line:
                    ts_part = line.split("]")[0].replace("[", "")
                    try:
                        t = datetime.strptime(ts_part, "%Y-%m-%d %H:%M:%S")
                        if not first_time:
                            first_time = t
                        last_time = t
                    except Exception:
                        pass

                # category counting
                for k in stats.keys():
                    if f"[{k}]" in line:
                        stats[k] += 1

                # cache hits/misses
                if "cache hit" in line.lower():
                    cache_hits += 1
                if (
                    "fetch" in line.lower()
                    and "NSE" in line
                    and "cache hit" not in line.lower()
                ):
                    cache_misses += 1

                # symbol pattern recognition
                for sym in TICKERS.keys():
                    if sym in line:
                        if "UC Locked" in line:
                            symbol_stats[sym]["UC"] += 1
                            uc_symbols.add(sym)
                        elif "LC Locked" in line:
                            symbol_stats[sym]["LC"] += 1
                            lc_symbols.add(sym)
                        elif "Target" in line or "T1" in line or "T2" in line:
                            symbol_stats[sym]["TARGET"] += 1
                        elif "Stoploss" in line or "SL hit" in line:
                            symbol_stats[sym]["SL"] += 1
                        elif "Re-entry" in line:
                            symbol_stats[sym]["REENTRY"] += 1

    # ─────────────── Display Summary ───────────────
    console.rule(
        f"[bold cyan]📊 Intraday Cockpit Log Summary[/bold cyan]", style="cyan"
    )
    console.print(f"Analyzed last {days} day(s) ({total_lines} entries)\n")

    # Stats table
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY)
    table.add_column("Category", justify="left")
    table.add_column("Count", justify="right")
    for k, v in stats.items():
        color = (
            "green"
            if k in {"INFO", "CACHE"} and v > 0
            else "yellow"
            if k == "WARN" and v > 0
            else "red"
            if k == "ERR" and v > 0
            else "cyan"
        )
        table.add_row(k, f"[{color}]{v}[/{color}]")
    console.print(table)

    # Cache metrics
    hit_rate = (
        (cache_hits / (cache_hits + cache_misses) * 100)
        if (cache_hits + cache_misses) > 0
        else 0
    )
    if cache_hits + cache_misses > 0:
        console.print(
            f"\n💾 Cache Hits: [green]{cache_hits}[/green] | Misses: [yellow]{cache_misses}[/yellow] | Hit Rate: [bold cyan]{hit_rate:.1f}%[/bold cyan]"
        )
    else:
        console.print(f"\n💾 Cache activity: [dim]No entries logged[/dim]")

    # UC/LC summary
    console.print(
        "\n🚀 UC Symbols:",
        ", ".join(sorted(uc_symbols)) if uc_symbols else "[dim]None[/dim]",
    )
    console.print(
        "💀 LC Symbols:",
        ", ".join(sorted(lc_symbols)) if lc_symbols else "[dim]None[/dim]",
    )

    # Time range
    time_window = ""
    if first_time and last_time:
        time_window = (
            f"{first_time.strftime('%H:%M:%S')} → {last_time.strftime('%H:%M:%S')}"
        )
        console.print(f"\n🕒 Log period: {time_window}")

    # Leaderboard
    console.rule(
        "[bold magenta]🏆 Symbol Activity Leaderboard[/bold magenta]", style="magenta"
    )
    leaderboard = Table(
        show_header=True, header_style="bold magenta", box=box.SIMPLE_HEAVY
    )
    leaderboard.add_column("Symbol")
    leaderboard.add_column("🚀 UC", justify="right")
    leaderboard.add_column("💀 LC", justify="right")
    leaderboard.add_column("🎯 Target", justify="right")
    leaderboard.add_column("🛑 SL", justify="right")
    leaderboard.add_column("🔁 Re-entry", justify="right")
    leaderboard.add_column("Total", justify="right")

    for sym, vals in sorted(
        symbol_stats.items(), key=lambda x: sum(x[1].values()), reverse=True
    ):
        total = sum(vals.values())
        if total == 0:
            continue
        leaderboard.add_row(
            sym,
            str(vals["UC"]),
            str(vals["LC"]),
            str(vals["TARGET"]),
            str(vals["SL"]),
            str(vals["REENTRY"]),
            str(total),
        )
    console.print(leaderboard)

    console.print(f"\nLog files scanned:")
    for f in log_files[-days:]:
        console.print(f"• {os.path.basename(f)}")

    # ─────────────── CSV Export (with metadata header) ───────────────
    if export:
        csv_path = STATE_DIR / f"log_summary_{datetime.now().strftime('%Y-%m-%d')}.csv"
        with open(csv_path, "w") as f:
            f.write("# Intraday Cockpit Log Summary Export\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Log Period: {time_window or 'N/A'}\n")
            f.write(f"# UC Count: {len(uc_symbols)} | LC Count: {len(lc_symbols)}\n")
            f.write(
                f"# Cache Hit Rate: {hit_rate:.1f}% ({cache_hits} hits, {cache_misses} misses)\n"
            )
            f.write("# Symbol,UC,LC,Target,SL,Reentry,Total\n")
            for sym, vals in symbol_stats.items():
                total = sum(vals.values())
                if total == 0:
                    continue
                f.write(
                    f"{sym},{vals['UC']},{vals['LC']},{vals['TARGET']},{vals['SL']},{vals['REENTRY']},{total}\n"
                )
        console.print(f"\n💾 Summary exported to: [cyan]{csv_path}[/cyan]\n")

    console.print("[green]📈 Daily summary complete — safe to exit cockpit.[/green]\n")


# ───────────────────────── MAIN EXECUTION ─────────────────────────
if __name__ == "__main__":
    # ───────────────────────── SESSION & MODE DETECTION ─────────────────────────
    now = datetime.now()
    eod_mode = not is_trading_day(date.today())
    last_td = last_trading_day()

    # Optional summary mode (manual trigger)
    if "--summary" in sys.argv:
        try:
            idx = sys.argv.index("--summary")
            days = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 1
        except Exception:
            days = 1
        export = "--export" in sys.argv
        summarize_logs(days, export=export)
        sys.exit(0)

    # Define NSE market hours (09:15 to 15:30 IST)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    market_live = not eod_mode and (market_open <= now < market_close)

    # Determine session
    if now < market_open:
        session = "Pre-Open"
    elif now < now.replace(hour=11):
        session = "Morning"
    elif now < now.replace(hour=14):
        session = "Midday"
    elif now < market_close:
        session = "Closing"
    else:
        session = "Post-Close"

    mode_icon = "🟢" if market_live else "🟡"
    mode_label = (
        f"{mode_icon}  📈 Mode: [green]LIVE Intraday[/green]"
        if market_live
        else f"{mode_icon}  📈 Mode: [yellow]EOD (Market Closed)[/yellow]"
    )

    console.rule(
        f"{mode_label}  |  Last Trading Day: [bold cyan]{last_td}[/bold cyan]",
        style="bold blue",
    )
    console.print(
        f"[cyan]🧠 Session:[/cyan] {session}  |  [cyan]Refresh Interval:[/cyan] {REFRESH_MINUTES} min\n"
    )

    if market_live:
        console.print(
            f"[green]🚀 Market live — auto-refresh every {REFRESH_MINUTES} min.[/green]\n"
        )
    else:
        console.print(
            "[yellow]🕓 Market closed — switching to EOD snapshot mode.[/yellow]\n"
        )
        eod_mode = True

    # ───────────────────────── MAIN LOOP ─────────────────────────
    while True:
        console.print(f"[dim]{'═'*100}[/dim]")
        now_str = datetime.now().strftime("%H:%M:%S")
        console.print(f"[cyan]⏳ Fetching new candles at {now_str} IST...[/cyan]")
        log_event(f"Refresh cycle started at {now_str}", event_type="INFO")

        movers_data = []
        for sym, key in TICKERS.items():
            try:
                info = render_card(sym, key, eod_mode)
                if info:
                    movers_data.append(info)
            except Exception as e:
                console.print(f"[red]{sym}: {e}[/red]")
                log_event(f"{sym}: {e}", event_type="ERR")

        # ───────────────────────── Movers Summary ─────────────────────────
        if movers_data:
            top = max(movers_data, key=lambda x: x["delta_pct"])
            bottom = min(movers_data, key=lambda x: x["delta_pct"])

            console.print(
                f"[bold green]🔥 Top Mover:[/bold green] {top['sym']} "
                f"{top['delta_pct']:+.2f}%  "
                f"[bold red]| 📉 Weakest:[/bold red] {bottom['sym']} "
                f"{bottom['delta_pct']:+.2f}%"
            )

            movers_ranked = sorted(
                movers_data, key=lambda x: x["delta_pct"], reverse=True
            )
            rank_line = "[bold blue]🏁 Movers:[/bold blue] " + " | ".join(
                [
                    f"[bright_cyan]{i+1}️⃣ {m['sym']} {m['delta_pct']:+.1f}%[/bright_cyan]"
                    for i, m in enumerate(movers_ranked[:5])
                ]
            )
            console.print(rank_line)

        # ───────────────────────── Action Focus Summary ─────────────────────────
        longs, waits, shorts = [], [], []
        for m in movers_data:
            sym = m["sym"]
            action = m.get("action", "")
            prev_state = TARGET_STATE.get("symbols", {}).get(sym, {})
            prev_active = prev_state.get("ACTIVE", False)

            if "ENTER LONG" in action:
                if prev_active:
                    longs.append(f"{sym} 🕐")
                else:
                    longs.append(sym)
                TARGET_STATE["symbols"][sym]["ACTIVE"] = True

            elif "WAIT" in action or "OBSERVE" in action:
                waits.append(sym)
                TARGET_STATE["symbols"][sym]["ACTIVE"] = False

            elif "AVOID" in action or "SHORT" in action:
                shorts.append(sym)
                TARGET_STATE["symbols"][sym]["ACTIVE"] = False

        # ───────────────────────── Exit-Zone Tracking, Smart Alerts & Re-Entry ─────────────────────────
        reentry_alerts = []

        for m in movers_data:
            sym = m["sym"]
            action = m.get("action", "")
            state = TARGET_STATE["symbols"].setdefault(
                sym,
                {
                    "ACTIVE": False,
                    "REENTRY_COUNT": 0,
                    "LAST_ENTRY_TIME": None,
                    "LAST_EXIT_TIME": None,
                },
            )
            was_active = state.get("ACTIVE", False)
            rsi = m.get("RSI", 0)
            bias = m.get("bias", "")

            # --- Fresh entry trigger ---
            if "ENTER LONG" in action and not was_active:
                if state.get("LAST_EXIT_TIME"):
                    state["REENTRY_COUNT"] = state.get("REENTRY_COUNT", 0) + 1
                    log_event(
                        f"🔁 Re-entry detected: {sym} (#{state['REENTRY_COUNT']}) (RSI {rsi:.1f}, Bias {bias})",
                        event_type="REENTRY",
                    )
                    reentry_alerts.append(
                        f"{sym} (#{state['REENTRY_COUNT']}) – RSI {rsi:.1f}, Bias {bias}"
                    )
                else:
                    log_event(
                        f"🟢 NEW Long Setup detected: {sym} (RSI {rsi:.1f}, Bias {bias})",
                        event_type="TARGET",
                    )

                state["ACTIVE"] = True
                state["LAST_ENTRY_TIME"] = datetime.now().strftime("%H:%M:%S")

            # --- Exit trigger ---
            elif was_active and (
                ("ENTER LONG" not in action and bias not in ("Long", "UC Locked"))
                or rsi < 50
            ):
                log_event(
                    f"ℹ️ {sym} exited active zone (RSI {rsi:.1f}, Bias {bias})",
                    event_type="INFO",
                )
                state["ACTIVE"] = False
                state["LAST_EXIT_TIME"] = datetime.now().strftime("%H:%M:%S")

        save_target_state(TARGET_STATE)

        # ───────────────────────── Live Re-entry Alerts ─────────────────────────
        if reentry_alerts:
            console.print("")
            console.rule(
                "[bold magenta]🔁 ACTIVE RE-ENTRY ALERT(S)[/bold magenta]",
                style="magenta",
            )
            for alert in reentry_alerts:
                console.print(f"[magenta]{alert}[/magenta]")
            console.print("")

        # ───────────────────────── Display Action Summary ─────────────────────────
        console.print("")
        focus_line = "[bold magenta]🎯 Action Focus →[/bold magenta] "

        if longs:
            focus_line += " ENTER LONG: [green]" + ", ".join(longs) + "[/green]"
        if waits:
            focus_line += " | ⚠️ HOLD/WAIT: [yellow]" + ", ".join(waits) + "[/yellow]"
        if shorts:
            focus_line += " | 🚫 AVOID/SHORT: [red]" + ", ".join(shorts) + "[/red]"

        if not (longs or waits or shorts):
            focus_line += "[dim]No actionable setups this cycle[/dim]"

        console.print(focus_line)

        # ───────────────────────── EOD EXIT ─────────────────────────
        if eod_mode or datetime.now() >= market_close:
            console.print(
                "\n[yellow]✅ EOD snapshot complete — exiting cockpit loop.[/yellow]\n"
            )
            log_event("EOD snapshot complete, exiting cockpit loop", event_type="INFO")

            console.print("[cyan]📊 Generating enhanced daily log summary...[/cyan]")
            summarize_logs(days=1, export=True)
            log_event("Enhanced daily summary complete", event_type="INFO")
            break

        wait_until_next_boundary(REFRESH_MINUTES)

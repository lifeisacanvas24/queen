#!/usr/bin/env python3
# ============================================================
# queen/helpers/market.py — v9.6 (single source of truth for time/calendar)
# ============================================================
"""Market Time & Calendar Utilities
--------------------------------
✅ Delegates ALL exchange data to queen.settings.settings (no hardcoded TF tokens)
✅ Provides working-day / holiday logic, market-open gates, and async sleep helpers
❌ Does NOT parse timeframe tokens (delegated to helpers.intervals / settings.timeframes)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from queen.helpers import io
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS

# -----------------------------
# TZ & exchange info (helpers)
# -----------------------------
try:
    MARKET_TZ = ZoneInfo(SETTINGS.market_timezone())
except Exception:
    MARKET_TZ = ZoneInfo("Asia/Kolkata")

MARKET_TZ_KEY = getattr(MARKET_TZ, "key", str(MARKET_TZ))

_EX_INFO: dict = {}
try:
    _EX_INFO = SETTINGS.exchange_info(SETTINGS.active_exchange()) or {}
except Exception:
    _EX_INFO = {}


def _hours() -> dict:
    """Resolve market hours from settings (upper-cased keys internally), with safe fallbacks."""
    h = _EX_INFO.get("MARKET_HOURS") or {}
    if not h:
        h = {
            "PRE_MARKET": "09:00",
            "OPEN": "09:15",
            "CLOSE": "15:30",
            "POST_MARKET": "23:59",
        }
    return {
        "PRE_MARKET": h.get("PRE_MARKET") or h.get("pre_market") or "09:00",
        "OPEN": h.get("OPEN") or h.get("open") or "09:15",
        "CLOSE": h.get("CLOSE") or h.get("close") or "15:30",
        "POST_MARKET": h.get("POST_MARKET") or h.get("post_market") or "23:59",
    }


MARKET_HOURS = _hours()
TRADING_DAYS = _EX_INFO.get(
    "TRADING_DAYS", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
)
EXPIRY_DAY = _EX_INFO.get("EXPIRY_DAY", "Thursday")


def _holidays_path() -> Path | None:
    """Find the holidays file, preferring exchange config; warn if configured path is missing."""
    try:
        p = _EX_INFO.get("HOLIDAYS")
        if p:
            p = Path(p).expanduser().resolve()
            if p.exists():
                return p
            log.warning(f"[Market] Holiday file missing at {p}")
    except Exception:
        pass
    try:
        hp = SETTINGS.PATHS.get("HOLIDAYS")
        if hp:
            p2 = Path(hp).expanduser().resolve()
            if p2.exists():
                return p2
    except Exception:
        pass
    return None


HOLIDAY_FILE = _holidays_path()

# -----------------------------
# Holidays (Polars + cache)
# -----------------------------
_HOLIDAYS_CACHE: dict[int, set[str]] | None = None


def _normalize_holiday_df(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize holiday 'date' column to ISO ('YYYY-MM-DD') and add year for partitioning."""
    if df.is_empty():
        return df

    # normalize column names
    df = df.rename({c: c.lower() for c in df.columns})

    # ensure there is a 'date' column
    if "date" not in df.columns:
        for cand in ("dt", "day", "on_date"):
            if cand in df.columns:
                df = df.rename({cand: "date"})
                break
    if "date" not in df.columns:
        log.warning("[Market] Holiday file missing 'date' column.")
        return pl.DataFrame()

    date_str = pl.col("date").cast(pl.Utf8)

    # parse a few common formats → Date → back to iso string
    parsed = (
        pl.when(date_str.str.contains(r"^\d{4}-\d{2}-\d{2}$"))
          .then(date_str.str.strptime(pl.Date, "%Y-%m-%d", strict=False))
        .when(date_str.str.contains(r"^\d{2}-\d{2}-\d{4}$"))
          .then(date_str.str.strptime(pl.Date, "%d-%m-%Y", strict=False))
        .when(date_str.str.contains(r"^\d{4}/\d{2}/\d{2}$"))
          .then(date_str.str.strptime(pl.Date, "%Y/%m/%d", strict=False))
        .otherwise(None)
          .alias("parsed_date")
    )

    out = (
        df.with_columns(parsed)
          .with_columns([
              pl.col("parsed_date").dt.year().alias("year"),
              pl.col("parsed_date").cast(pl.Utf8).alias("iso_date"),
          ])
          .drop_nulls(subset=["parsed_date"])
    )

    # keep 'date' as ISO string for compatibility
    out = out.with_columns(pl.col("iso_date").alias("date"))
    return out.select(["date", "year"])


def _read_holidays(path: Path | None) -> pl.DataFrame:
    if not path or not path.exists():
        if path:
            log.warning(f"[Market] Holiday file not found: {path}")
        return pl.DataFrame()
    try:
        if path.suffix.lower() == ".csv":
            return io.read_csv(path)
        return io.read_json(path)
    except Exception as e:
        log.error(f"[Market] Holiday read failed for {path.name} → {e}")
        return pl.DataFrame()


def _load_holidays() -> dict[int, set[str]]:
    df = _normalize_holiday_df(_read_holidays(HOLIDAY_FILE))
    out: dict[int, set[str]] = {}
    for s in df.get_column("date").to_list() if not df.is_empty() else []:
        try:
            y = int(str(s)[:4])
            out.setdefault(y, set()).add(str(s))
        except Exception:
            continue
    if out:
        log.info(f"[Market] Holidays loaded: years={sorted(out.keys())}")
    return out


def _holidays() -> dict[int, set[str]]:
    global _HOLIDAYS_CACHE
    if _HOLIDAYS_CACHE is None:
        _HOLIDAYS_CACHE = _load_holidays()
    return _HOLIDAYS_CACHE


def reload_holidays() -> None:
    """Force a reload of the holidays cache (e.g., when file updated)."""
    global _HOLIDAYS_CACHE
    _HOLIDAYS_CACHE = None


# -----------------------------
# Time helpers
# -----------------------------
def ensure_tz_aware(ts: dt.datetime) -> dt.datetime:
    """Coerce a naive datetime to MARKET_TZ; otherwise convert to MARKET_TZ."""
    return ts.replace(tzinfo=MARKET_TZ) if ts.tzinfo is None else ts.astimezone(MARKET_TZ)


# -----------------------------
# Day logic
# -----------------------------
def is_holiday(d: date | None = None) -> bool:
    d = d or dt.datetime.now(MARKET_TZ).date()
    return d.isoformat() in _holidays().get(d.year, set())


def is_working_day(d: date) -> bool:
    return d.strftime("%A") in TRADING_DAYS and not is_holiday(d)


def last_working_day(ref: date | None = None) -> date:
    ref = ref or dt.datetime.now(MARKET_TZ).date()
    d = ref
    while not is_working_day(d):
        d -= timedelta(days=1)
    return d


def next_working_day(d: date) -> date:
    d = d + timedelta(days=1)
    while not is_working_day(d):
        d += timedelta(days=1)
    return d


def offset_working_day(start: date, offset: int) -> date:
    cur = start
    step = 1 if offset > 0 else -1
    remain = abs(offset)
    while remain > 0:
        cur += timedelta(days=step)
        if is_working_day(cur):
            remain -= 1
    return cur


# -----------------------------
# Sessions & gates
# -----------------------------
def _t(hhmm: str) -> dt.time:
    return dt.time.fromisoformat(hhmm)


_SESSIONS = {
    "PRE_MARKET": (_t(MARKET_HOURS["PRE_MARKET"]), _t(MARKET_HOURS["OPEN"])),
    "REGULAR": (_t(MARKET_HOURS["OPEN"]), _t(MARKET_HOURS["CLOSE"])),
    "POST_MARKET": (_t(MARKET_HOURS["CLOSE"]), _t(MARKET_HOURS["POST_MARKET"])),
}


def current_session(now: dt.datetime | None = None) -> str:
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    for name, (start, end) in _SESSIONS.items():
        s = dt.datetime.combine(now.date(), start, MARKET_TZ)
        e = dt.datetime.combine(now.date(), end, MARKET_TZ)
        if s <= now <= e:
            return name
    return "CLOSED"


def is_market_open(now: dt.datetime | None = None) -> bool:
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    if now.strftime("%A") not in TRADING_DAYS or is_holiday(now.date()):
        return False
    s, e = _SESSIONS["REGULAR"]
    sdt = dt.datetime.combine(now.date(), s, MARKET_TZ)
    edt = dt.datetime.combine(now.date(), e, MARKET_TZ)
    # inclusive close to match current_session semantics
    return sdt <= now <= edt


def _intraday_available(now: dt.datetime) -> bool:
    if now.strftime("%A") not in TRADING_DAYS or is_holiday(now.date()):
        return False
    return current_session(now) in {"REGULAR", "POST_MARKET"}


def get_gate(now: dt.datetime | None = None) -> str:
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    d = now.date()
    if d.strftime("%A") not in TRADING_DAYS:
        return "WEEKEND"
    if is_holiday(d):
        return "HOLIDAY"
    sess = current_session(now)
    return {"PRE_MARKET": "PRE", "REGULAR": "LIVE", "POST_MARKET": "POST"}.get(sess, "CLOSED")


def current_historical_service_day(now: dt.datetime | None = None) -> date:
    """Return which calendar day should be used for historical service during different sessions."""
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    sess = current_session(now)
    d = now.date()
    if not is_working_day(d):
        return last_working_day(d)
    if sess == "REGULAR":
        return last_working_day(d - timedelta(days=1))
    if sess == "POST_MARKET":
        return d
    return last_working_day(d - timedelta(days=1))


def get_market_state() -> dict:
    now = dt.datetime.now(MARKET_TZ)
    sess = current_session(now)
    working = is_working_day(now.date())
    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "is_open": is_market_open(now),
        "is_holiday": is_holiday(now.date()),
        "is_working_day": working,
        "intraday_available": _intraday_available(now),
        "session": sess,
        "gate": get_gate(now),
        "next_open": next_working_day(now.date()).isoformat(),
        "service_day": current_historical_service_day(now).isoformat(),
    }

# ✅ Canonical trading aliases (DRY)
def is_trading_day(d: date) -> bool:
    return is_working_day(d)

def last_trading_day(ref: date | None = None) -> date:
    return last_working_day(ref)

def next_trading_day(d: date) -> date:
    return next_working_day(d)

# -----------------------------
# Candle sleep math (pure & testable)
# -----------------------------


def compute_sleep_delay(
    now: dt.datetime,
    interval_minutes: int,
    jitter_ratio: float = 0.3,
    *,
    jitter_value: float | None = None,   # deterministic tests: pass a value in [-1, +1]
) -> tuple[float, dt.datetime]:
    """Compute the sleep delay (seconds) until the next candle boundary.

    Returns:
        (delay_seconds, next_wake_dt_in_market_tz)

    Guarantees:
        - delay is clamped to [1, period-1]
        - boundary logic mirrors sleep_until_next_candle()

    """
    now = ensure_tz_aware(now)
    seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    period = max(60, int(interval_minutes * 60))

    mod = seconds_today % period
    delay = 1 if mod == 0 or mod >= (period - 2) else (period - mod)

    if jitter_ratio:
        if jitter_value is None:
            j = random.uniform(-jitter_ratio, jitter_ratio)
        else:
            # bound user-supplied jitter_value to [-1, +1] for safety
            j = max(-1.0, min(1.0, float(jitter_value)))
        delay += j * period

    delay = max(1.0, min(delay, period - 1))
    next_wake = (now + dt.timedelta(seconds=delay)).astimezone(MARKET_TZ)
    return delay, next_wake
# -----------------------------
# Async helpers
# -----------------------------
async def sleep_until_next_candle(
    interval_minutes: int,
    jitter_ratio: float = 0.3,
    emit_log: bool = True,
) -> None:
    now = dt.datetime.now(MARKET_TZ)
    delay, nxt = compute_sleep_delay(now, interval_minutes, jitter_ratio=jitter_ratio)
    if emit_log:
        log.info(
            f"[MarketClock] Sleeping {delay:.2f}s → next candle at {nxt:%H:%M:%S} {MARKET_TZ_KEY}"
        )
    await asyncio.sleep(delay)

async def market_open_waiter(poll_seconds: int = 30, verbose: bool = True) -> None:
    """Poll until market open according to settings calendar."""
    while not is_market_open():
        if verbose:
            st = get_market_state()
            log.info(f"[Gate] Waiting for open — {st['timestamp']} | gate={st['gate']}")
        await asyncio.sleep(poll_seconds)
    if verbose:
        log.info("[Gate] Market OPEN — resuming.")


class _MarketGate:
    """Async context manager that waits until a desired gate condition is true."""

    def __init__(self, mode: str = "intraday"):  # "intraday" | "regular" | "any_working"
        self.mode = mode

    async def __aenter__(self):
        while True:
            st = get_market_state()
            is_working = st["is_working_day"]
            sess = st["session"]
            if (
                (self.mode == "intraday" and is_working and sess in {"REGULAR", "POST_MARKET"})
                or (self.mode == "regular" and is_working and sess == "REGULAR")
                or (self.mode == "any_working" and is_working)
            ):
                break
            log.info(
                f"[Gate] Waiting (mode={self.mode}) — {st['timestamp']} | gate={st['gate']} | session={sess}"
            )
            await asyncio.sleep(60)
        log.info("[Gate] Market OPEN — resuming.")
        return self

    async def __aexit__(self, *_):
        return False


def market_gate(mode: str = "intraday") -> _MarketGate:
    return _MarketGate(mode)


def historical_available() -> bool:
    """Placeholder hook for future calendar rules around historical availability."""
    return True

def sessions():  # tiny accessor to avoid underscore import in tests
    return dict(_SESSIONS)

#!/usr/bin/env python3
# ============================================================
# queen/helpers/market.py — v9.3 (Settings-Driven + Polars + DRY)
# ============================================================
"""Market calendar & timing utilities for NSE/BSE.

✅ Settings-driven (no hardcoded constants)
✅ Timezone-safe (Asia/Kolkata from settings)
✅ Async-ready helpers for daemons/schedulers
✅ Exposes market_gate(), MarketClock, sleep_until_next_candle()
✅ Holiday loading via Polars (JSON/CSV), robust & cached
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Optional, Set

import polars as pl
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS
from zoneinfo import ZoneInfo

# ------------------------------------------------------------
# 🌍 Exchange / TZ from settings
# ------------------------------------------------------------
_ACTIVE_EX = SETTINGS.DEFAULTS["EXCHANGE"]
_EX_INFO = SETTINGS.EXCHANGE["EXCHANGES"][_ACTIVE_EX]

MARKET_TZ = ZoneInfo(SETTINGS.EXCHANGE["MARKET_TIMEZONE"])
MARKET_HOURS = _EX_INFO["MARKET_HOURS"]  # PRE_MARKET / OPEN / CLOSE / POST_MARKET
TRADING_DAYS = _EX_INFO.get(
    "TRADING_DAYS", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
)
EXPIRY_DAY = _EX_INFO.get("EXPIRY_DAY", "Thursday")
HOLIDAY_FILE = Path(_EX_INFO["HOLIDAYS"]).expanduser().resolve()

# ------------------------------------------------------------
# 📅 Holidays (Polars loader + cache)
# ------------------------------------------------------------
_HOLIDAYS_CACHE: Dict[int, Set[str]] | None = None


def _read_holidays_polars(path: Path) -> pl.DataFrame:
    if not path.exists():
        log.warning(f"[Market] Holiday file not found: {path}")
        return pl.DataFrame()
    try:
        if path.suffix.lower() == ".csv":
            df = pl.read_csv(path)
        else:
            try:
                df = pl.read_json(path)  # JSON array
            except Exception:
                df = pl.read_ndjson(path)  # NDJSON fallback
        return df
    except Exception as e:
        log.error(f"[Market] Holiday read failed for {path.name} → {e}")
        return pl.DataFrame()


def _normalize_holiday_df(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    df = df.rename({c: c.lower() for c in df.columns})
    if "date" not in df.columns:
        for cand in ("dt", "day", "on_date"):
            if cand in df.columns:
                df = df.rename({cand: "date"})
                break
    if "date" not in df.columns:
        log.warning("[Market] Holiday file missing 'date' column.")
        return pl.DataFrame()
    try:
        df = df.with_columns(pl.col("date").cast(pl.Utf8))
    except Exception:
        pass
    return df.select("date")


def _load_holidays() -> Dict[int, Set[str]]:
    df = _normalize_holiday_df(_read_holidays_polars(HOLIDAY_FILE))
    if df.is_empty():
        return {}
    dates = df["date"].to_list()
    out: Dict[int, Set[str]] = {}
    for d in dates:
        try:
            y = int(d.split("-")[0])
        except Exception:
            continue
        out.setdefault(y, set()).add(d)
    log.info(
        f"[Market] Loaded {sum(len(v) for v in out.values())} holidays from {HOLIDAY_FILE.name}"
    )
    return out


def _holidays() -> Dict[int, Set[str]]:
    global _HOLIDAYS_CACHE
    if _HOLIDAYS_CACHE is None:
        _HOLIDAYS_CACHE = _load_holidays()
    return _HOLIDAYS_CACHE


# ------------------------------------------------------------
# 🧭 Time helpers
# ------------------------------------------------------------
def ensure_tz_aware(ts: dt.datetime) -> dt.datetime:
    """Ensure datetime is timezone-aware in MARKET_TZ."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=MARKET_TZ)
    return ts.astimezone(MARKET_TZ)


# ------------------------------------------------------------
# 📆 Day logic
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# 🕒 Sessions & state
# ------------------------------------------------------------
def _t(hhmm: str) -> dt.time:
    return dt.time.fromisoformat(hhmm)


_SESSIONS = {
    "PRE_MARKET": (_t(MARKET_HOURS["PRE_MARKET"]), _t(MARKET_HOURS["OPEN"])),
    "REGULAR": (_t(MARKET_HOURS["OPEN"]), _t(MARKET_HOURS["CLOSE"])),
    "POST_MARKET": (_t(MARKET_HOURS["CLOSE"]), _t(MARKET_HOURS["POST_MARKET"])),
}


def current_session(now: Optional[dt.datetime] = None) -> str:
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    for name, (start, end) in _SESSIONS.items():
        s = dt.datetime.combine(now.date(), start, MARKET_TZ)
        e = dt.datetime.combine(now.date(), end, MARKET_TZ)
        if s <= now <= e:
            return name
    return "CLOSED"


def is_market_open(now: Optional[dt.datetime] = None) -> bool:
    """True only during REGULAR session on a working day."""
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    if now.strftime("%A") not in TRADING_DAYS or is_holiday(now.date()):
        return False
    start, end = _SESSIONS["REGULAR"]
    s = dt.datetime.combine(now.date(), start, MARKET_TZ)
    e = dt.datetime.combine(now.date(), end, MARKET_TZ)
    return s <= now <= e


def _intraday_available(now: dt.datetime) -> bool:
    """Intraday data commonly available during REGULAR and POST_MARKET on working days."""
    if now.strftime("%A") not in TRADING_DAYS or is_holiday(now.date()):
        return False
    sess = current_session(now)
    return sess in {"REGULAR", "POST_MARKET"}


def get_gate(now: Optional[dt.datetime] = None) -> str:
    now = ensure_tz_aware(now or dt.datetime.now(MARKET_TZ))
    d = now.date()
    if d.strftime("%A") not in TRADING_DAYS:
        return "WEEKEND"
    if is_holiday(d):
        return "HOLIDAY"
    sess = current_session(now)
    if sess == "PRE_MARKET":
        return "PRE"
    if sess == "REGULAR":
        return "LIVE"
    if sess == "POST_MARKET":
        return "POST"
    return "CLOSED"


def get_market_state() -> dict:
    now = dt.datetime.now(MARKET_TZ)
    sess = current_session(now)
    working = is_working_day(now.date())
    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "is_open": is_market_open(now),  # True only during REGULAR
        "is_holiday": is_holiday(now.date()),
        "is_working_day": working,
        "intraday_available": _intraday_available(now),
        "session": sess,
        "gate": get_gate(now),
        "next_open": next_working_day(now.date()).isoformat(),
    }


def current_historical_service_day(now: dt.datetime | None = None) -> date:
    """Exchange date that the historical endpoint effectively exposes now."""
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


# ------------------------------------------------------------
# ⏳ Async helpers
# ------------------------------------------------------------
async def sleep_until_next_candle(
    interval_minutes: int, jitter_ratio: float = 0.3, emit_log: bool = True
):
    """Sleep until next aligned bar close for given minute interval."""
    now = dt.datetime.now(MARKET_TZ)
    seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    period = interval_minutes * 60
    mod = seconds_today % period
    delay = 1 if mod == 0 or mod >= (period - 2) else (period - mod)
    if jitter_ratio:
        jitter = random.uniform(-jitter_ratio, jitter_ratio) * (interval_minutes * 60)
        delay = max(0.0, delay + jitter)
    if emit_log:
        nxt = (now + dt.timedelta(seconds=delay)).strftime("%H:%M:%S")
        log.info(f"[MarketClock] Sleeping {delay:.2f}s → next candle {nxt} IST")
    await asyncio.sleep(delay)


async def market_open_waiter(poll_seconds: int = 30, verbose: bool = True):
    """Block until market open (REGULAR)."""
    while not is_market_open():
        if verbose:
            st = get_market_state()
            log.info(f"[Gate] Waiting for open — {st['timestamp']} | gate={st['gate']}")
        await asyncio.sleep(poll_seconds)
    if verbose:
        log.info("[Gate] Market OPEN — resuming.")


# ------------------------------------------------------------
# ⏱️ Ticking clock
# ------------------------------------------------------------
class MarketClock:
    def __init__(
        self,
        interval: int = 5,
        name: str = "MarketClock",
        verbose: bool = True,
        auto_pause: bool = True,
    ):
        self.interval = interval
        self.name = name
        self.verbose = verbose
        self.auto_pause = auto_pause
        self._subs: Dict[str, asyncio.Queue] = {}
        self._running = False

    def subscribe(self, name: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[name] = q
        if self.verbose:
            log.info(f"[{self.name}] subscriber added → {name}")
        return q

    async def start(self):
        if self._running:
            return
        self._running = True
        if self.verbose:
            log.info(f"[{self.name}] started @ {self.interval}m")
        while self._running:
            state = get_market_state()
            if self.auto_pause and not state["intraday_available"]:
                if self.verbose:
                    log.info(f"[{self.name}] intraday unavailable — waiting")
                await asyncio.sleep(30)
                continue
            tick = {
                "timestamp": dt.datetime.now(MARKET_TZ),
                "session": state["session"],
                "is_open": state["is_open"],
                "gate": state["gate"],
            }
            for nm, q in self._subs.items():
                try:
                    q.put_nowait(tick)
                except asyncio.QueueFull:
                    log.warning(f"[{self.name}] queue full for {nm}, skipping tick")
            if self.verbose:
                log.info(
                    f"[{self.name}] tick | {tick['timestamp'].strftime('%H:%M:%S')} | sess={tick['session']} | subs={len(self._subs)}"
                )
            await sleep_until_next_candle(self.interval, emit_log=False)

    async def stop(self):
        self._running = False
        if self.verbose:
            log.info(f"[{self.name}] stopped")


# ------------------------------------------------------------
# 🔒 Async gate context
# ------------------------------------------------------------
class _MarketGate:
    def __init__(self, mode: str = "intraday"):
        # mode: "intraday" (REGULAR/POST), "regular" (REGULAR only), "any_working"
        self.mode = mode

    async def __aenter__(self):
        while True:
            st = get_market_state()
            is_working = st["is_working_day"]
            sess = st["session"]
            if (
                (
                    self.mode == "intraday"
                    and is_working
                    and sess in {"REGULAR", "POST_MARKET"}
                )
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

    async def __aexit__(self, exc_type, exc, tb):
        return False


def market_gate(mode: str = "intraday") -> _MarketGate:
    return _MarketGate(mode)


def historical_available() -> bool:
    """Historical endpoint serves up to the last working day (always logically 'available')."""
    return True


# ------------------------------------------------------------
# ✅ Self-test
# ------------------------------------------------------------
if __name__ == "__main__":
    import json as _json

    print(_json.dumps(get_market_state(), indent=2))

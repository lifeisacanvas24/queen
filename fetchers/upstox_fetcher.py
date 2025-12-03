#!/usr/bin/env python3
# ============================================================
# queen/fetchers/upstox_fetcher.py — v9.10
# (Full timeframe support + FETCH override + DRY intervals)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import time
from datetime import date, timedelta
from math import ceil
from typing import Any, Dict, Optional

import httpx
import polars as pl

from queen.helpers.fetch_utils import warn_if_same_day_eod
from queen.helpers.instruments import (
    get_instrument_meta,
    resolve_instrument,
    validate_historical_range,
)
from queen.helpers.intervals import to_fetcher_interval
from queen.helpers.logger import log
from queen.helpers.schema_adapter import (
    SCHEMA,
    finalize_candle_df,
    handle_api_error,
    to_candle_df,
    validate_interval,
)
from queen.settings import settings as SETTINGS

# ============================================================
# ⚙️ Config Bootstrap
# ============================================================
BROKER = SETTINGS.DEFAULTS["BROKER"]
BROKER_CFG = SETTINGS.broker_config(BROKER)

RETRY_CFG = BROKER_CFG.get("RETRY", {})
API_BASE_URL = SCHEMA.get("base_url")
if not API_BASE_URL:
    raise RuntimeError(
        "[UpstoxFetcher] 'base_url' missing in broker schema. "
        'Add to api_upstox.json → { "base_url": "https://api.upstox.com/v3/" }'
    )

MAX_RETRIES = int(RETRY_CFG.get("MAX_RETRIES", 3))
TIMEOUT = int(RETRY_CFG.get("TIMEOUT", 10))
BACKOFF_BASE = float(RETRY_CFG.get("BACKOFF_BASE", 2))
UPSTOX_ACCESS_TOKEN = getattr(SETTINGS, "UPSTOX_ACCESS_TOKEN", None)

HISTORICAL_DEF = SCHEMA.get("historical_candle_api", {})
INTRADAY_DEF = SCHEMA.get("intraday_candle_api", {})
DEFAULT_INTERVALS = SETTINGS.DEFAULTS.get(
    "DEFAULT_INTERVALS", {"intraday": "5m", "daily": "1d"}
)

# ============================================================
# 🧩 Per-timeframe FETCH override helper
# ============================================================
def _min_rows_from_settings(token: str, fallback: Any) -> Any:
    """Allow per-timeframe overrides via SETTINGS.FETCH, e.g.:
    FETCH.MIN_ROWS_AUTO_BACKFILL_5M = 120
    FETCH.MIN_ROWS_AUTO_BACKFILL_15M = 90
    FETCH.MIN_ROWS_AUTO_BACKFILL = 80  # global

    If no override found, returns `fallback` *as-is* (so we can use a sentinel).
    """
    try:
        fetch_cfg = SETTINGS.FETCH or {}
    except Exception:
        fetch_cfg = {}

    t = str(token or "").strip().lower()
    suffix = t.upper().replace(":", "")
    key_specific = f"MIN_ROWS_AUTO_BACKFILL_{suffix}"

    if key_specific in fetch_cfg:
        try:
            return int(fetch_cfg[key_specific])
        except Exception:
            pass

    if "MIN_ROWS_AUTO_BACKFILL" in fetch_cfg:
        try:
            return int(fetch_cfg["MIN_ROWS_AUTO_BACKFILL"])
        except Exception:
            pass

    # IMPORTANT: do NOT int() the fallback; just return it.
    return fallback

# ============================================================
# 🛠 HTTP + Backfill helpers
# ============================================================
def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if UPSTOX_ACCESS_TOKEN:
        h["Authorization"] = f"Bearer {UPSTOX_ACCESS_TOKEN}"
    return h


def _merge_unique_sort(dfs: list[pl.DataFrame]) -> pl.DataFrame:
    dfs = [d for d in dfs if isinstance(d, pl.DataFrame) and not d.is_empty()]
    if not dfs:
        return pl.DataFrame()
    return (
        pl.concat(dfs, how="vertical_relaxed")
        .unique(subset=["timestamp"])
        .sort("timestamp")
    )


def _estimate_days_for_bars(unit: str, interval_num: int, bars: int) -> int:
    """Convert bars → approx trading days (NSE ~375 minutes/day)."""
    if bars <= 0 or interval_num <= 0:
        return 1
    minutes_per_bar = interval_num * (60 if unit == "hours" else 1)
    return max(1, ceil((bars * minutes_per_bar) / 375.0))


async def _intraday_via_historical(
    symbol: str,
    interval: str | int,
    *,
    days: int | None = None,
    bars: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pl.DataFrame:
    """For minutes/hours, fetch via historical endpoint to span a window.

    - If `start` / `end` provided, they define the explicit window (YYYY-MM-DD*).
    - Otherwise, backfill window is inferred from `days` or `bars`.
    - Also safe for days/weeks/months (delegates wide by default).
    """
    canon = to_fetcher_interval(interval)
    unit, interval_num_s = canon.split(":", 1)
    interval_num = int(interval_num_s)

    today = date.today()
    to_d = (end or today.isoformat())

    if unit in {"days", "weeks", "months"}:
        # Delegate directly for higher TFs; give a wider default if days not provided
        from_d = (start or (today - timedelta(days=int(days or 60))).isoformat())
        df = await fetch_daily_range(symbol, from_d, to_d, interval)
    else:
        if start:
            from_d = start[:10]
        elif bars:
            est_days = _estimate_days_for_bars(unit, interval_num, int(bars))
            from_d = (today - timedelta(days=est_days)).isoformat()
        else:
            from_d = (today - timedelta(days=int(days or 2))).isoformat()
        df = await fetch_daily_range(symbol, from_d, to_d, interval)

    return df.unique(subset=["timestamp"]).sort("timestamp") if not df.is_empty() else df


# ============================================================
# 🧩 Smart intraday wrapper (primary + bridge)
# ============================================================
try:
    from queen.settings.timeframes import DEFAULT_BACKFILL_DAYS_INTRADAY as _DEF_AF_DAYS
    from queen.settings.timeframes import MIN_ROWS_AUTO_BACKFILL as _MIN_ROWS_AF
except Exception:
    _MIN_ROWS_AF = {5: 120, 15: 80, 30: 60, 60: 40}
    _DEF_AF_DAYS = 2


def _resolve_intraday_threshold(
    interval_token: str | int,
    unit: str,
    interval_num: int,
    explicit_thr: int | None,
) -> tuple[int, str]:
    """Decide the min-rows threshold and return (value, source_label).

    Precedence:
      1) explicit_thr (function arg)
      2) SETTINGS.FETCH.MIN_ROWS_AUTO_BACKFILL_{TOKEN} or global MIN_ROWS_AUTO_BACKFILL
      3) timeframes.MIN_ROWS_AUTO_BACKFILL table (minutes_key)
    """
    minutes_key = (interval_num * 60) if unit == "hours" else interval_num

    # 1) explicit
    if explicit_thr is not None:
        return int(explicit_thr), "arg:min_rows_auto_backfill"

    # 2) settings override (specific or global)
    token_str = str(interval_token or "5m").lower()
    _sentinel = object()
    cfg_val = _min_rows_from_settings(token_str, _sentinel)  # type: ignore
    if cfg_val is not _sentinel:
        return int(cfg_val), "settings:FETCH"

    # 3) default table (from queen.settings.timeframes)
    default_thr = _MIN_ROWS_AF.get(minutes_key, 80)
    return int(default_thr), "defaults:MIN_ROWS_AUTO_BACKFILL"


async def fetch_intraday_smart(
    symbol: str,
    interval: str | int = "5m",
    *,
    min_rows_auto_backfill: int | None = None,
    days: int | None = None,
    bars: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pl.DataFrame:
    """Try intraday endpoint first; if thin, bridge with historical minutes."""
    canon = to_fetcher_interval(interval or DEFAULT_INTERVALS.get("intraday", "5m"))
    unit, interval_num_s = canon.split(":", 1)
    interval_num = int(interval_num_s)

    primary = await fetch_intraday(symbol, interval)
    if unit not in {"minutes", "hours"}:
        return primary

    # --- threshold (value + source label) ---
    thr, thr_src = _resolve_intraday_threshold(
        interval_token=interval,
        unit=unit,
        interval_num=interval_num,
        explicit_thr=min_rows_auto_backfill,
    )
    log.info(
        f"[UpstoxFetcher] threshold={thr} (source={thr_src}) "
        f"for {symbol} @ {interval}"
    )

    if primary.is_empty() or getattr(primary, "height", 0) < thr:
        log.info(
            f"[UpstoxFetcher] {symbol} @ {interval}: "
            f"{getattr(primary,'height',0)} < {thr} → bridging hist"
        )
        bridge = await _intraday_via_historical(
            symbol,
            interval,
            days=(days if days is not None else _DEF_AF_DAYS),
            bars=bars,
            start=start,
            end=end,
        )
        return _merge_unique_sort([bridge, primary])
    return primary

# ============================================================
# 📡 HTTP JSON fetch
# ============================================================
async def _fetch_json(url: str, label: str = "") -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as session:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                start = time.perf_counter()
                response = await session.get(url)
                response.raise_for_status()
                data = response.json()
                if data.get("status") != "success":
                    handle_api_error(data.get("code") or "UNKNOWN")
                log.info(
                    f"[UpstoxFetcher] ✅ {label} | "
                    f"{time.perf_counter() - start:.2f}s | Attempt {attempt}"
                )
                return data
            except Exception as e:
                log.warning(f"[UpstoxFetcher] Retry {attempt}/{MAX_RETRIES} → {e}")
                await asyncio.sleep(BACKOFF_BASE**attempt)
        raise RuntimeError(f"[UpstoxFetcher] Failed after {MAX_RETRIES}: {url}")

# ============================================================
# 📈 Candle Fetchers
# ============================================================
async def fetch_intraday(
    symbol: str,
    interval: str | int = "5m",
    *,
    days: int | None = None,
    bars: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pl.DataFrame:
    """Fetch intraday candles.

    If explicit backfill hints are supplied (days/bars/start/end),
    use historical minutes bridge. Otherwise fetch **only today's** intraday (pure).
    """
    canon = to_fetcher_interval(interval or DEFAULT_INTERVALS.get("intraday", "5m"))
    unit, interval_num_s = canon.split(":", 1)
    interval_num = int(interval_num_s)

    if not validate_interval(unit, interval_num, intraday=True):
        raise ValueError(
            f"Unsupported intraday interval '{interval}' for unit '{unit}'"
        )

    # Explicit backfill request → go via historical minutes
    if any([days, bars, start, end]):
        log.info(f"[Intraday] {symbol} → using historical minutes bridge for backfill")
        return await _intraday_via_historical(
            symbol,
            interval,
            days=days,
            bars=bars,
            start=start,
            end=end,
        )

    # Normal intraday "today" call (pure)
    instrument_key = resolve_instrument(symbol)
    url_pattern = INTRADAY_DEF.get("url_pattern", "")
    if not url_pattern:
        log.error("[UpstoxFetcher] Intraday URL pattern missing in schema.")
        return pl.DataFrame()

    url = f"{API_BASE_URL}{url_pattern}".format(
        instrument_key=instrument_key,
        unit=unit,
        interval=interval_num,
    )
    data = await _fetch_json(url, f"Intraday {symbol}")

    candles = data.get("data", {}).get("candles", [])
    df_today = finalize_candle_df(
        to_candle_df(candles, symbol),
        symbol,
        get_instrument_meta(symbol)["isin"],
    )
    log.info(f"[Intraday] {symbol} ({unit}:{interval_num}) → {len(df_today)} rows.")
    return df_today


async def fetch_daily_range(
    symbol: str,
    from_date: str,
    to_date: str,
    interval: str | int = "1d",
) -> pl.DataFrame:
    """Fetch historical candles for a symbol/range.

    Historical supports units per schema: minutes|hours|days|weeks|months
    (e.g., 15m, 1h, 1d, 1w, 1mo)
    """
    canon = to_fetcher_interval(interval or DEFAULT_INTERVALS.get("daily", "1d"))
    unit, interval_num_s = canon.split(":", 1)
    interval_num = int(interval_num_s)

    # Schema validation for historical table
    if not validate_interval(unit, interval_num, intraday=False):
        raise ValueError(
            f"Unsupported historical interval '{interval}' for unit '{unit}'"
        )

    instrument_key = resolve_instrument(symbol)
    url_pattern = HISTORICAL_DEF.get("url_pattern", "")
    if not url_pattern:
        log.error("[UpstoxFetcher] Historical URL pattern missing in schema.")
        return pl.DataFrame()

    url = f"{API_BASE_URL}{url_pattern}".format(
        instrument_key=instrument_key,
        unit=unit,
        interval=interval_num,
        to_date=to_date,
        from_date=from_date,
    )

    start_d = date.fromisoformat(from_date)
    if not validate_historical_range(symbol, start_d):
        log.warning(f"[UpstoxFetcher] Skipping {symbol}: before listing date.")
        return pl.DataFrame()

    data = await _fetch_json(url, f"Historical {symbol}")
    candles = data.get("data", {}).get("candles", [])
    if not candles:
        log.info(
            f"[Daily] No candles returned for {symbol} between {from_date} and {to_date}. "
            "If this includes today, EOD may not be published yet."
        )

    df = to_candle_df(candles, symbol)
    meta = get_instrument_meta(symbol)
    df_final = finalize_candle_df(df, symbol, meta["isin"])
    log.info(
        f"[Daily] {symbol} ({unit}:{interval_num}) {from_date}→{to_date} → "
        f"{len(df_final)} rows."
    )
    return df_final

# ============================================================
# 🧠 Unified Dispatcher (now with intraday range support)
# ============================================================
async def fetch_unified(
    symbol: str,
    mode: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str | int = "1",
    *,
    # backfill controls (ignored for pure daily unless you pass minutes/hours)
    days: int | None = None,
    bars: int | None = None,
    start: str | None = None,
    end: str | None = None,
    min_rows_auto_backfill: int | None = None,
) -> pl.DataFrame:
    """Single entrypoint for all fetch styles.

    - mode="intraday" with NO from/to → live intraday via fetch_intraday_smart
    - mode="intraday" WITH from/to   → historical intraday via historical endpoint
    - mode="daily"/"historical"      → historical (days/weeks/months) via fetch_daily_range
    """
    mode = mode.lower()

    if mode in {"intraday", "minute", "min"}:
        use_interval = interval or DEFAULT_INTERVALS.get("intraday", "5m")

        # If caller provides from/to → treat this as historical intraday window
        if from_date or to_date:
            log.info(
                f"[Unified] {symbol} intraday-range {from_date}→{to_date} @ {use_interval}"
            )
            return await _intraday_via_historical(
                symbol,
                use_interval,
                days=days,
                bars=bars,
                start=from_date,
                end=to_date,
            )

        # Otherwise: pure "live-smart" intraday
        return await fetch_intraday_smart(
            symbol,
            use_interval,
            min_rows_auto_backfill=min_rows_auto_backfill,
            days=days,
            bars=bars,
            start=start,
            end=end,
        )

    if mode in {"daily", "historical"}:
        if not (from_date and to_date):
            raise ValueError("from_date and to_date required for daily fetches.")
        use_interval = interval or DEFAULT_INTERVALS.get("daily", "1d")
        log.info(
            f"[Unified] {symbol} daily-range {from_date}→{to_date} @ {use_interval}"
        )
        return await fetch_daily_range(symbol, from_date, to_date, use_interval)

    raise ValueError(f"Unknown mode: {mode}")

# ============================================================
# 🧪 CLI Interface (with backfill controls)
# ============================================================
def run_cli():
    parser = argparse.ArgumentParser(description="Queen Upstox Fetcher CLI")
    parser.add_argument("--symbol", required=True, help="Symbol (e.g. TCS, INFY)")
    parser.add_argument("--mode", choices=["daily", "intraday"], default="daily")
    parser.add_argument("--from", dest="from_date", help="From date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="To date (YYYY-MM-DD)")
    parser.add_argument(
        "--interval",
        default=None,
        help=(
            "Interval like 5m, 15m, 1h, 1d, 1w, 1mo (or minutes:5 / days:1). "
            "If omitted, uses settings.DEFAULT_INTERVALS for the chosen mode."
        ),
    )

    # --- Backfill arguments ---
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Backfill N days of intraday (historical minutes bridge)",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=None,
        help="Approximate bars to backfill (converted to trading days)",
    )
    parser.add_argument(
        "--start",
        dest="start",
        default=None,
        help="Start date (YYYY-MM-DD) for historical minutes window",
    )
    parser.add_argument(
        "--end",
        dest="end",
        default=None,
        help="End date (YYYY-MM-DD) for historical minutes window",
    )

    args = parser.parse_args()

    async def main():
        # choose defaults per mode if interval not provided
        default_intraday = DEFAULT_INTERVALS.get("intraday", "5m")
        default_daily = DEFAULT_INTERVALS.get("daily", "1d")
        use_interval = args.interval or (
            default_daily if args.mode == "daily" else default_intraday
        )

        if args.mode == "daily":
            warn_if_same_day_eod(args.from_date, args.to_date)

        log.info(
            f"[CLI] Fetch starting for {args.symbol} ({args.mode}) @ {use_interval}"
        )

        df = await fetch_unified(
            args.symbol,
            args.mode,
            args.from_date,
            args.to_date,
            use_interval,
            days=args.days,
            bars=args.bars,
            start=args.start,
            end=args.end,
        )

        if df.is_empty():
            log.warning(f"[CLI] No data fetched for {args.symbol}.")
        else:
            first, last = df["timestamp"][0], df["timestamp"][-1]
            log.info(
                f"[CLI] ✅ {args.symbol}: {len(df)} rows | Range {first} → {last}"
            )
            print(df.head(5))

    asyncio.run(main())

# ============================================================
# ✅ Entrypoint
# ============================================================
if __name__ == "__main__":
    run_cli()

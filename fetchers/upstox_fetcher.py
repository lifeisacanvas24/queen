#!/usr/bin/env python3
# ============================================================
# queen/fetchers/upstox_fetcher.py — v9.6 (Full timeframe support)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import time
from datetime import date
from typing import Any, Dict, Optional

import httpx
import polars as pl
from queen.helpers.fetch_utils import warn_if_same_day_eod
from queen.helpers.instruments import (
    get_instrument_meta,
    resolve_instrument,
    validate_historical_range,
)
from queen.helpers.logger import log
from queen.helpers.schema_adapter import (
    SCHEMA,  # single source of truth for API + capabilities
    finalize_candle_df,
    handle_api_error,
    to_candle_df,
    validate_interval,  # validator reads supported_timelines from SCHEMA
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
    "DEFAULT_INTERVALS",
    {"intraday": "5m", "daily": "1d"},
)


# ============================================================
# 🧭 Interval helpers (multi-unit)
# ============================================================
def _parse_unit_interval(value: str | int, *, default_unit: str) -> tuple[str, int]:
    """Accepts:
      - suffix forms: 5m, 1h, 1d, 1w, 1mo
      - explicit forms: minutes:5, hours:1, days:1, weeks:1, months:1
      - bare numbers: '15' → (default_unit, 15)
    Returns: (unit, interval_int) with unit in {"minutes","hours","days","weeks","months"}.
    """
    if isinstance(value, int):
        return default_unit, value

    s = str(value).strip().lower()

    # suffix forms
    if s.endswith("mo"):
        return "months", int(s[:-2] or "1")
    if s.endswith("w"):
        return "weeks", int(s[:-1] or "1")
    if s.endswith("d"):
        return "days", int(s[:-1] or "1")
    if s.endswith("h"):
        return "hours", int(s[:-1] or "1")
    if s.endswith("m"):
        return "minutes", int(s[:-1] or "1")

    # explicit "unit:value"
    if ":" in s:
        u, v = s.split(":", 1)
        u = u.strip()
        if u in {"minutes", "hours", "days", "weeks", "months"}:
            return u, int(v)

    # bare → default unit
    return default_unit, int(s or "1")


# ============================================================
# 🛠 HTTP helpers
# ============================================================
def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if UPSTOX_ACCESS_TOKEN:
        h["Authorization"] = f"Bearer {UPSTOX_ACCESS_TOKEN}"
    return h


async def _fetch_json(url: str, label: str = "") -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as session:
        for attempt in range(1, MAX_RETRIES + 1):
            start = time.perf_counter()
            try:
                response = await session.get(url)
                latency = time.perf_counter() - start
                response.raise_for_status()
                data = response.json()

                if data.get("status") != "success":
                    handle_api_error(data.get("code") or "UNKNOWN")

                log.info(
                    f"[UpstoxFetcher] ✅ {label} | {latency:.2f}s | Attempt {attempt}/{MAX_RETRIES}"
                )
                return data

            except httpx.RequestError as e:
                log.warning(f"[UpstoxFetcher] Network error ({attempt}) → {e}")
            except httpx.HTTPStatusError as e:
                log.error(f"[UpstoxFetcher] HTTP {e.response.status_code} → {url}")
            except Exception as e:
                log.error(f"[UpstoxFetcher] Unexpected error ({attempt}) → {e}")

            await asyncio.sleep(BACKOFF_BASE**attempt)
            log.info(f"[Retry] Waiting before retry {attempt+1}")

    raise RuntimeError(f"[UpstoxFetcher] Failed after {MAX_RETRIES} retries: {url}")


# ============================================================
# 📈 Candle Fetchers
# ============================================================
async def fetch_intraday(symbol: str, interval: str | int = "5m") -> pl.DataFrame:
    """Fetch intraday candles for a symbol.
    Intraday supports units per schema: minutes|hours|days  (e.g., 5m, 1h, 1d)
    """
    unit, interval_num = _parse_unit_interval(interval, default_unit="minutes")

    # Schema validation for intraday table
    if not validate_interval(unit, interval_num, intraday=True):
        raise ValueError(
            f"Unsupported intraday interval '{interval}' for unit '{unit}'"
        )

    instrument_key = resolve_instrument(symbol)
    url_pattern = INTRADAY_DEF.get("url_pattern", "")
    if not url_pattern:
        log.error("[UpstoxFetcher] Intraday URL pattern missing in schema.")
        return pl.DataFrame()

    url = f"{API_BASE_URL}{url_pattern}".format(
        instrument_key=instrument_key, unit=unit, interval=interval_num
    )
    data = await _fetch_json(url, f"Intraday {symbol}")

    candles = data.get("data", {}).get("candles", [])
    df = to_candle_df(candles, symbol)
    meta = get_instrument_meta(symbol)
    df_final = finalize_candle_df(df, symbol, meta["isin"])
    log.info(f"[Intraday] {symbol} ({unit}:{interval_num}) → {len(df_final)} rows.")
    return df_final


async def fetch_daily_range(
    symbol: str, from_date: str, to_date: str, interval: str | int = "1d"
) -> pl.DataFrame:
    """Fetch historical candles for a symbol/range.
    Historical supports units per schema: minutes|hours|days|weeks|months
    (e.g., 15m, 1h, 1d, 1w, 1mo)
    """
    unit, interval_num = _parse_unit_interval(interval, default_unit="days")

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
        f"[Daily] {symbol} ({unit}:{interval_num}) {from_date}→{to_date} → {len(df_final)} rows."
    )
    return df_final


# ============================================================
# 🧠 Unified Dispatcher
# ============================================================
async def fetch_unified(
    symbol: str,
    mode: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str | int = "1",
) -> pl.DataFrame:
    mode = mode.lower()

    if mode in {"intraday", "minute", "min"}:
        # defaults for intraday come from settings if caller passed a blanky string
        use_interval = interval or DEFAULT_INTERVALS.get("intraday", "5m")
        return await fetch_intraday(symbol, use_interval)

    if mode in {"daily", "historical"}:
        if not (from_date and to_date):
            raise ValueError("from_date and to_date required for daily fetches.")
        use_interval = interval or DEFAULT_INTERVALS.get("daily", "1d")
        return await fetch_daily_range(symbol, from_date, to_date, use_interval)

    raise ValueError(f"Unknown mode: {mode}")


# ============================================================
# 🧪 CLI Interface
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
        help="Interval like 5m, 15m, 1h, 1d, 1w, 1mo (or minutes:5 / days:1). "
        "If omitted, uses settings DEFAULT_INTERVALS for the chosen mode.",
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
            args.symbol, args.mode, args.from_date, args.to_date, use_interval
        )

        if df.is_empty():
            log.warning(f"[CLI] No data fetched for {args.symbol}.")
        else:
            first, last = df["timestamp"][0], df["timestamp"][-1]
            log.info(f"[CLI] ✅ {args.symbol}: {len(df)} rows | Range {first} → {last}")
            print(df.head(5))

    asyncio.run(main())


# ============================================================
# ✅ Entrypoint
# ============================================================
if __name__ == "__main__":
    run_cli()

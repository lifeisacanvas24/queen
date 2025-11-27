#!/usr/bin/env python3
# ============================================================
# queen/fetchers/nse_fetcher.py — v3.1 (Unified, Resilient, Dual Cache)
# ============================================================
"""Consolidated NSE fetcher combining:
1. Time-based disk caching for intraday data (O/H/L/VWAP).
2. Daily in-memory caching for meta-data (UC/LC, 52W).
3. Network Retry Logic for resilience.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from queen.helpers.logger import log

# NOTE: MARKET_TZ is needed for the daily meta-cache key
from queen.helpers.market import MARKET_TZ
from queen.settings import settings as SETTINGS

# ------------------------------------------------------------
# 📁 Cache paths
# ------------------------------------------------------------
# Disk Cache for time-sensitive bands (O/H/L/VWAP)
CACHE_FILE: Path = SETTINGS.PATHS["CACHE"] / "nse_bands_cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

__MEM_DISK_CACHE: Dict[str, dict] = {}
__CACHE_MTIME: float | None = None

# In-Memory Cache for daily meta-data (UC/LC, 52W)
_META_CACHE: Dict[Tuple[str, date], Dict[str, Any]] = {}


def _clean_price(v) -> Optional[float]:
    """Cast to float, treat 0 / empty as None."""
    if v in (None, "", "-", "--"):
        return None
    try:
        f = float(v)
        return f if f != 0.0 else None
    except Exception:
        return None


# ------------------------------------------------------------
# 🌐 NSE HTTP config (settings-backed)
# ------------------------------------------------------------
_ext = getattr(SETTINGS, "EXTERNAL_APIS", {}) or {}
_nse_cfg = _ext.get("NSE", {}) or {}

_NSE_BASE_URL: str = _nse_cfg.get("BASE_URL", "https://www.nseindia.com").rstrip("/")
_NSE_QUOTE_PATH: str = _nse_cfg.get(
    "QUOTE_EQUITY", "/api/quote-equity?symbol={symbol}"
)
_NSE_QUOTE_REFERER_PATH: str = _nse_cfg.get(
    "QUOTE_REFERER", "/get-quotes/equity?symbol={symbol}"
)

# Using the robust headers from v2.3
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/plain, */*",
}


def _quote_url(symbol: str) -> str:
    return f"{_NSE_BASE_URL}{_NSE_QUOTE_PATH.format(symbol=symbol)}"


def _referer_url(symbol: str) -> str:
    return f"{_NSE_BASE_URL}{_NSE_QUOTE_REFERER_PATH.format(symbol=symbol)}"


# ------------------------------------------------------------
# 🔄 Disk cache helpers (Time-based, persistent)
# ------------------------------------------------------------
def _read_disk_cache() -> Dict[str, dict]:
    """Reads time-based cache from disk (original v2.3/v3.0 logic)."""
    global __MEM_DISK_CACHE, __CACHE_MTIME
    try:
        if not CACHE_FILE.exists():
            return {}

        mtime = CACHE_FILE.stat().st_mtime
        if __CACHE_MTIME is not None and mtime == __CACHE_MTIME and __MEM_DISK_CACHE:
            return __MEM_DISK_CACHE

        data = json.loads(CACHE_FILE.read_text() or "{}")
        if isinstance(data, dict):
            __MEM_DISK_CACHE = data
            __CACHE_MTIME = mtime
            return __MEM_DISK_CACHE
    except Exception as e:
        log.warning(f"[NSE] disk cache read failed: {e}")
    return __MEM_DISK_CACHE or {}


def _write_disk_cache(cache: Dict[str, dict]) -> None:
    """Writes time-based cache to disk (original v2.3/v3.0 logic)."""
    global __MEM_DISK_CACHE, __CACHE_MTIME
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
        __MEM_DISK_CACHE = cache
        __CACHE_MTIME = CACHE_FILE.stat().st_mtime
    except Exception as e:
        log.warning(f"[NSE] disk cache write failed: {e}")


# ------------------------------------------------------------
# 🕒 Daily Meta Cache Helpers (In-memory, daily reset)
# ------------------------------------------------------------
def _today() -> date:
    """Gets today's date in MARKET_TZ."""
    return datetime.now(MARKET_TZ).date()


# ------------------------------------------------------------
# 🌐 Core Fetching Logic (with Retries)
# ------------------------------------------------------------
def _fetch_and_parse_quote(
    symbol: str, retries: int = 2, backoff_s: float = 0.8
) -> Dict[str, Any]:
    """Performs the network request with retries and returns all parsed price info.
    (Integrated retry logic from nse_fetcher_new.py v2.3)
    """
    sym = symbol.upper()
    url = _quote_url(sym)
    last_err = None
    raw_data: Optional[dict] = None

    # --- Network Fetch with Retry Loop ---
    for attempt in range(1, retries + 1):
        try:
            with requests.Session() as s:
                # NSE wants a priming request to BASE_URL
                s.get(_NSE_BASE_URL, headers=_HEADERS, timeout=5)
                r = s.get(
                    url,
                    headers={**_HEADERS, "Referer": _referer_url(sym)},
                    timeout=10,
                )
                r.raise_for_status()
                raw_data = r.json() or {}
                # Successfully fetched, break the retry loop
                break

        except Exception as e:
            last_err = e
            log.warning(
                f"[NSE] fetch retry {attempt}/{retries} failed for {sym} → {e}"
            )
            time.sleep(backoff_s * attempt)

    # If all attempts failed
    if raw_data is None:
        log.warning(f"[NSE] fetch failed after {retries} retries for {sym}: {last_err}")
        return {}

    # --- Parsing Logic (Executed only on successful fetch) ---
    bands: dict = {}
    price_info = raw_data.get("priceInfo", {}) or {}

    # Core bands (UC/LC/PC)
    # Using the correct key for upper circuit (v2.3 logic)
    uc = _clean_price(price_info.get("upperCP"))
    lc = _clean_price(price_info.get("lowerCP"))
    pc = _clean_price(price_info.get("previousClose"))

    # Intraday fields (O/L/H/VWAP/LP)
    open_ = _clean_price(price_info.get("open"))
    last_price = _clean_price(price_info.get("lastPrice"))
    vwap = _clean_price(price_info.get("vwap"))
    day_high = day_low = None
    try:
        intraday = price_info.get("intraDayHighLow") or {}
        day_high = _clean_price(intraday.get("max"))
        day_low = _clean_price(intraday.get("min"))
    except Exception:
        pass

    # 52W high/low
    year_high = year_low = None
    try:
        whl = price_info.get("weekHighLow") or {}
        year_high = _clean_price(whl.get("max"))
        year_low = _clean_price(whl.get("min"))
    except Exception:
        pass

    # Build the result dictionary
    if uc is not None: bands["upper_circuit"] = uc
    if lc is not None: bands["lower_circuit"] = lc
    if pc is not None: bands["prev_close"] = pc
    if open_ is not None: bands["open"] = open_
    if last_price is not None: bands["last_price"] = last_price
    if vwap is not None: bands["vwap"] = vwap
    if day_high is not None: bands["day_high"] = day_high
    if day_low is not None: bands["day_low"] = day_low
    if year_high is not None: bands["year_high"] = year_high
    if year_low is not None: bands["year_low"] = year_low

    return bands


# ------------------------------------------------------------
# 📈 Public API - Time-Sensitive (Disk Cache)
# ------------------------------------------------------------
def fetch_nse_bands(symbol: str, cache_refresh_minutes: int = 30) -> Optional[dict]:
    """Fetch all bands, using time-based disk cache."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

    cache = _read_disk_cache()
    now = time.time()
    entry = cache.get(symbol)

    # Fresh enough cache — just reuse
    if entry and (now - float(entry.get("timestamp", 0))) < cache_refresh_minutes * 60:
        return entry.get("bands") or None

    # Call the new resilient fetcher
    bands = _fetch_and_parse_quote(symbol)

    # completely empty → keep old cache if any
    if not bands:
        log.warning(f"[NSE] Empty bands for {symbol} → keeping old disk cache")
        return entry.get("bands") if entry else None

    cache[symbol] = {"timestamp": now, "bands": bands}
    _write_disk_cache(cache)
    return bands


def get_cached_nse_bands(symbol: str) -> Optional[dict]:
    """Read bands from time-based disk cache only (no network)."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None
    cache = _read_disk_cache()
    entry = cache.get(symbol)
    return entry.get("bands") if entry else None


# ------------------------------------------------------------
# 📊 Public API - Daily Meta-Data (In-Memory Cache)
# ------------------------------------------------------------
def get_daily_cached_meta(symbol: str) -> Dict[str, Any]:
    """Fetch meta-data (UC/LC/PC/52W H/L), using in-memory cache keyed daily."""
    sym = symbol.upper()
    today = _today()
    key = (sym, today)

    # Fresh cache for today — reuse
    if key in _META_CACHE:
        return _META_CACHE[key]

    # Call the new resilient fetcher
    bands = _fetch_and_parse_quote(sym)

    # Filter bands to only include the daily-relevant meta-data
    meta_keys = [
        "upper_circuit", "lower_circuit", "prev_close",
        "year_high", "year_low"
    ]
    meta = {k: bands[k] for k in meta_keys if k in bands}

    _META_CACHE[key] = meta
    return meta


__all__ = ["fetch_nse_bands", "get_cached_nse_bands", "get_daily_cached_meta"]

#!/usr/bin/env python3
# ============================================================
# queen/fetchers/nse_fetcher.py — v2.3 (UNIFIED, forward-only)
# Single NSE meta authority:
#   • UC/LC, prevClose, O/H/L/VWAP, 52W H/L
#   • Settings-aware URLs
#   • Disk TTL cache + same-day in-memory memo
#   • Retry + safe parsing
# NO backward-compat exports from nse_meta_cache.py
# ============================================================
from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

from queen.helpers.logger import log
from queen.helpers.market import MARKET_TZ
from queen.settings import settings as SETTINGS

# ------------------------------------------------------------
# 📁 Cache paths (disk TTL cache)
# ------------------------------------------------------------
CACHE_FILE: Path = SETTINGS.PATHS["CACHE"] / "nse_bands_cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

__MEM_CACHE: Dict[str, dict] = {}
__CACHE_MTIME: float | None = None

# Same-day in-memory memo (faster for repeated reads)
__DAY_MEMO: Dict[Tuple[str, date], Dict[str, float | None]] = {}

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
# 🔁 Disk cache helpers
# ------------------------------------------------------------
def _read_cache() -> Dict[str, dict]:
    global __MEM_CACHE, __CACHE_MTIME
    try:
        if not CACHE_FILE.exists():
            return {}

        mtime = CACHE_FILE.stat().st_mtime
        if __CACHE_MTIME is not None and mtime == __CACHE_MTIME and __MEM_CACHE:
            return __MEM_CACHE

        data = json.loads(CACHE_FILE.read_text() or "{}")
        if isinstance(data, dict):
            __MEM_CACHE = data
            __CACHE_MTIME = mtime
            return __MEM_CACHE
    except Exception as e:
        log.warning(f"[NSE] cache read failed: {e}")
    return __MEM_CACHE or {}

def _write_cache(cache: Dict[str, dict]) -> None:
    global __MEM_CACHE, __CACHE_MTIME
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
        __MEM_CACHE = cache
        __CACHE_MTIME = CACHE_FILE.stat().st_mtime
    except Exception as e:
        log.warning(f"[NSE] cache write failed: {e}")

# ------------------------------------------------------------
# 🧼 Safe number casting
# ------------------------------------------------------------
def _clean_price(v) -> Optional[float]:
    """Cast to float, treat 0 / empty / '-' as None."""
    if v in (None, "", "-", "--"):
        return None
    try:
        f = float(v)
        return f if f != 0.0 else None
    except Exception:
        return None

def _today_ist() -> date:
    return datetime.now(MARKET_TZ).date()

# ------------------------------------------------------------
# 🌐 NSE network fetch (retry-safe)
# ------------------------------------------------------------
def _fetch_from_nse(symbol: str, retries: int = 2, backoff_s: float = 0.8) -> dict:
    url = _quote_url(symbol)
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            with requests.Session() as s:
                # Prime base URL (NSE anti-bot gate)
                s.get(_NSE_BASE_URL, headers=_HEADERS, timeout=5)
                r = s.get(
                    url,
                    headers={**_HEADERS, "Referer": _referer_url(symbol)},
                    timeout=10,
                )
                r.raise_for_status()
                return r.json() or {}
        except Exception as e:
            last_err = e
            log.warning(f"[NSE] fetch retry {attempt}/{retries} failed for {symbol} → {e}")
            time.sleep(backoff_s * attempt)

    raise RuntimeError(f"[NSE] fetch failed after {retries} retries for {symbol}: {last_err}")

# ------------------------------------------------------------
# ✅ Public API (single source of truth)
# ------------------------------------------------------------
def fetch_nse_bands(symbol: str, cache_refresh_minutes: int = 30) -> Optional[dict]:
    """Fetch NSE meta: UC/LC + prevClose + O/H/L/VWAP + 52W H/L.
    Disk TTL cache + same-day memo.

    Returns:
        {
          "upper_circuit": float | None,
          "lower_circuit": float | None,
          "prev_close": float | None,
          "open": float | None,
          "last_price": float | None,
          "vwap": float | None,
          "day_high": float | None,
          "day_low": float | None,
          "year_high": float | None,
          "year_low": float | None,
        }
    or None on total failure.

    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

    today = _today_ist()
    memo_key = (symbol, today)
    if memo_key in __DAY_MEMO:
        return __DAY_MEMO[memo_key]

    cache = _read_cache()
    now = time.time()
    entry = cache.get(symbol)

    # ✅ Fresh TTL cache hit
    if entry and (now - float(entry.get("timestamp", 0))) < cache_refresh_minutes * 60:
        bands = entry.get("bands") or None
        if isinstance(bands, dict):
            __DAY_MEMO[memo_key] = bands
        return bands

    try:
        j = _fetch_from_nse(symbol)
        price_info = (j.get("priceInfo") or {}) if isinstance(j, dict) else {}

        # Core bands
        uc = _clean_price(price_info.get("upperCP"))
        lc = _clean_price(price_info.get("lowerCP"))
        pc = _clean_price(price_info.get("previousClose"))

        # Intraday fields
        open_ = _clean_price(price_info.get("open"))
        last_price = _clean_price(price_info.get("lastPrice"))
        vwap = _clean_price(price_info.get("vwap"))

        # Day high/low
        day_high = day_low = None
        intraday = price_info.get("intraDayHighLow") or {}
        if isinstance(intraday, dict):
            day_high = _clean_price(intraday.get("max"))
            day_low = _clean_price(intraday.get("min"))

        # 52W high/low (NSE uses weekHighLow.max/min)
        year_high = year_low = None
        whl = price_info.get("weekHighLow") or {}
        if isinstance(whl, dict):
            year_high = _clean_price(whl.get("max") or whl.get("high"))
            year_low = _clean_price(whl.get("min") or whl.get("low"))

        bands: dict = {
            "upper_circuit": uc,
            "lower_circuit": lc,
            "prev_close": pc,
            "open": open_,
            "last_price": last_price,
            "vwap": vwap,
            "day_high": day_high,
            "day_low": day_low,
            "year_high": year_high,
            "year_low": year_low,
        }

        # If NSE returned nothing meaningful, keep old cache if exists
        if not any(v is not None for v in bands.values()):
            log.warning(f"[NSE] Empty meta for {symbol} → keeping old cache if any")
            old = entry.get("bands") if entry else None
            if isinstance(old, dict):
                __DAY_MEMO[memo_key] = old
            return old

        cache[symbol] = {"timestamp": now, "bands": bands}
        _write_cache(cache)

        __DAY_MEMO[memo_key] = bands
        return bands

    except Exception as e:
        log.warning(f"[NSE] fetch failed for {symbol}: {e}")
        # fallback to old TTL cache if present
        old = entry.get("bands") if entry else None
        if isinstance(old, dict):
            __DAY_MEMO[memo_key] = old
        return old

def get_cached_nse_bands(symbol: str) -> Optional[dict]:
    """Read bands from disk cache only (no network)."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None
    cache = _read_cache()
    entry = cache.get(symbol)
    return entry.get("bands") if entry else None

__all__ = ["fetch_nse_bands", "get_cached_nse_bands"]

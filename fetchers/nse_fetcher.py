#!/usr/bin/env python3
# ============================================================
# queen/fetchers/nse_fetcher.py — v2.2
# UC/LC + prevClose + O/H/L/VWAP/52W (cached, settings-aware)
# ============================================================
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS

# ------------------------------------------------------------
# 📁 Cache paths
# ------------------------------------------------------------
CACHE_FILE: Path = SETTINGS.PATHS["CACHE"] / "nse_bands_cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

__MEM_CACHE: Dict[str, dict] = {}
__CACHE_MTIME: float | None = None


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
# 🌐 Fetch bands (UC/LC + prevClose + O/H/L/VWAP/52W)
# ------------------------------------------------------------
def fetch_nse_bands(symbol: str, cache_refresh_minutes: int = 30) -> Optional[dict]:
    """Fetch NSE UC/LC + previous close + intraday O/H/L/VWAP + 52W.

    Returns (when available):
        {
          "upper_circuit": float,
          "lower_circuit": float,
          "prev_close": float,
          "open": float,
          "last_price": float,
          "vwap": float,
          "day_high": float,
          "day_low": float,
          "year_high": float | None,
          "year_low": float | None,
        }
    or None on failure.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

    cache = _read_cache()
    now = time.time()
    entry = cache.get(symbol)

    # ✅ Fresh enough cache — just reuse
    if entry and (now - float(entry.get("timestamp", 0))) < cache_refresh_minutes * 60:
        return entry.get("bands") or None

    url = _quote_url(symbol)

    try:
        with requests.Session() as s:
            # NSE wants a priming request to BASE_URL
            s.get(_NSE_BASE_URL, headers=_HEADERS, timeout=5)
            r = s.get(
                url,
                headers={**_HEADERS, "Referer": _referer_url(symbol)},
                timeout=10,
            )
            r.raise_for_status()
            j = r.json() or {}
            price_info = j.get("priceInfo", {}) or {}

        # Core bands
        uc = _clean_price(price_info.get("lowerCP" if False else "upperCP"))
        lc = _clean_price(price_info.get("lowerCP"))
        pc = _clean_price(price_info.get("previousClose"))

        # Intraday fields
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

        bands: dict = {}
        if uc is not None:
            bands["upper_circuit"] = uc
        if lc is not None:
            bands["lower_circuit"] = lc
        if pc is not None:
            bands["prev_close"] = pc
        if open_ is not None:
            bands["open"] = open_
        if last_price is not None:
            bands["last_price"] = last_price
        if vwap is not None:
            bands["vwap"] = vwap
        if day_high is not None:
            bands["day_high"] = day_high
        if day_low is not None:
            bands["day_low"] = day_low
        if year_high is not None:
            bands["year_high"] = year_high
        if year_low is not None:
            bands["year_low"] = year_low

        # completely empty → keep old cache if any
        if not bands:
            log.warning(f"[NSE] Empty bands for {symbol} → keeping old cache")
            return entry.get("bands") if entry else None

        cache[symbol] = {"timestamp": now, "bands": bands}
        _write_cache(cache)
        return bands

    except Exception as e:
        log.warning(f"[NSE] fetch failed for {symbol}: {e}")
        return entry.get("bands") if entry else None


def get_cached_nse_bands(symbol: str) -> Optional[dict]:
    """Read bands from cache only (no network)."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None
    cache = _read_cache()
    entry = cache.get(symbol)
    return entry.get("bands") if entry else None


__all__ = ["fetch_nse_bands", "get_cached_nse_bands"]

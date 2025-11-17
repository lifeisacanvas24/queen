#!/usr/bin/env python3
# ============================================================
# queen/fetchers/nse_fetcher.py — v2.1
# UC/LC + prevClose (cached, settings-aware)
# ------------------------------------------------------------
#  • Reads cache path via SETTINGS.PATHS["CACHE"]
#  • NSE HTTP endpoints come from settings.EXTERNAL_APIS["NSE"]
#    with safe defaults if missing (no hard-coded URLs in logic)
#  • Safe fallback to last-good cache on NSE failure
#  • Simple in-process + file-based cache
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

# tiny in-process cache
__MEM_CACHE: Dict[str, dict] = {}
__CACHE_MTIME: float | None = None

# ------------------------------------------------------------
# 🌐 NSE HTTP config (settings-backed)
# ------------------------------------------------------------
# EXTERNAL_APIS = {
#     "NSE": {
#         "BASE_URL": "https://www.nseindia.com",
#         "QUOTE_EQUITY": "/api/quote-equity?symbol={symbol}",
#         "QUOTE_REFERER": "/get-quotes/equity?symbol={symbol}",
#     },
# }
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
            # in-process cache still valid
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
# 🌐 Fetch bands (UC/LC + prevClose)
# ------------------------------------------------------------
def fetch_nse_bands(symbol: str, cache_refresh_minutes: int = 30) -> Optional[dict]:
    """Fetch NSE UC/LC + previous close + 52W high/low for a symbol.

    Returns:
        {
          "upper_circuit": float,
          "lower_circuit": float,
          "prev_close": float,
          "year_high": float | None,  # 52W high
          "year_low": float | None,   # 52W low
        }
    or None if nothing usable is available.

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

        uc = float(price_info.get("upperCP") or 0.0)
        lc = float(price_info.get("lowerCP") or 0.0)
        pc = float(price_info.get("previousClose") or 0.0)

        # 52W high/low: from priceInfo.weekHighLow.{max,min}
        year_high = year_low = None
        try:
            whl = price_info.get("weekHighLow") or {}
            if whl.get("max") not in (None, "", "-"):
                year_high = float(whl["max"])
            if whl.get("min") not in (None, "", "-"):
                year_low = float(whl["min"])
        except Exception:
            pass

        bands: dict = {
            "upper_circuit": uc,
            "lower_circuit": lc,
            "prev_close": pc,
        }
        if year_high is not None:
            bands["year_high"] = year_high
        if year_low is not None:
            bands["year_low"] = year_low

        if all(
            v == 0.0
            for k, v in bands.items()
            if k in ("upper_circuit", "lower_circuit", "prev_close")
        ):
            # likely bad/empty payload; keep old cache if any
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

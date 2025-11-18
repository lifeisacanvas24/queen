#!/usr/bin/env python3
# ============================================================
# queen/fetchers/nse_meta_cache.py — v1.0
# Daily cached NSE meta: UC/LC, prev close, 52W H/L
# ============================================================
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Tuple

import requests

from queen.helpers.logger import log
from queen.helpers.market import MARKET_TZ

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.nseindia.com/",
}

_META_CACHE: Dict[Tuple[str, date], Dict[str, Any]] = {}


def _today() -> date:
    return datetime.now(MARKET_TZ).date()


def _fetch_from_nse(symbol: str) -> Dict[str, Any]:
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    sym = symbol.upper()
    try:
        with requests.Session() as s:
            s.get("https://www.nseindia.com", headers=_HEADERS, timeout=5)
            r = s.get(url, headers=_HEADERS, timeout=10)
            if r.status_code != 200:
                log(f"NSE meta fetch failed {sym}: {r.status_code}", "WARN")
                return {}
            raw = r.json()
    except Exception as e:
        log(f"NSE meta fetch error {sym}: {e}", "ERROR")
        return {}

    pi = (raw or {}).get("priceInfo", {}) or {}
    wl = pi.get("weekHighLow", {}) or {}

    meta = {
        "upper_circuit": float(pi.get("upperCP") or 0) or None,
        "lower_circuit": float(pi.get("lowerCP") or 0) or None,
        "prev_close": float(pi.get("previousClose") or 0) or None,
        "fifty_two_week_high": float(wl.get("max") or 0) or None,
        "fifty_two_week_low": float(wl.get("min") or 0) or None,
    }
    return meta


def get_instrument_meta(symbol: str) -> Dict[str, Any]:
    sym = symbol.upper()
    today = _today()
    key = (sym, today)
    if key in _META_CACHE:
        return _META_CACHE[key]

    meta = _fetch_from_nse(sym)
    _META_CACHE[key] = meta
    return meta

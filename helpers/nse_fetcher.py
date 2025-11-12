#!/usr/bin/env python3
# ============================================================
# queen/helpers/nse_fetcher.py — UC/LC + prevClose (cached)
# ============================================================
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from queen.helpers.logger import log
from queen.settings.settings import PATHS

CACHE_FILE: Path = PATHS["CACHE"] / "nse_bands_cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/plain, */*",
}

def _read_cache() -> Dict[str, dict]:
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}

def _write_cache(cache: Dict[str, dict]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        log.warning(f"[NSE] cache write failed: {e}")

def fetch_nse_bands(symbol: str, cache_refresh_minutes: int = 30) -> Optional[dict]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

    cache = _read_cache()
    now = time.time()
    entry = cache.get(symbol)

    if entry and (now - float(entry.get("timestamp", 0))) < cache_refresh_minutes * 60:
        return entry.get("bands")

    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    try:
        with requests.Session() as s:
            s.get("https://www.nseindia.com", headers=_HEADERS, timeout=5)
            r = s.get(
                url,
                headers={**_HEADERS, "Referer": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"},
                timeout=10,
            )
            r.raise_for_status()
            j = r.json() or {}
            data = j.get("priceInfo", {}) or {}

        bands = {
            "upper_circuit": float(data.get("upperCP") or 0.0),
            "lower_circuit": float(data.get("lowerCP") or 0.0),
            "prev_close": float(data.get("previousClose") or 0.0),
        }
        if all(v == 0.0 for v in bands.values()):
            log.warning(f"[NSE] Empty data for {symbol} → skipping cache write")
            return entry.get("bands") if entry else None

        cache[symbol] = {"timestamp": now, "bands": bands}
        _write_cache(cache)
        return bands
    except Exception as e:
        log.warning(f"[NSE] fetch failed for {symbol}: {e}")
        return entry.get("bands") if entry else None

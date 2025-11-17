#!/usr/bin/env python3
# ============================================================
# queen/services/enrich_instruments.py — v1.0
# Instrument snapshot enricher (OHLC / volume / UC-LC / 52W / avg_price)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl

from queen.fetchers.nse_fetcher import fetch_nse_bands, get_cached_nse_bands


def _safe_float(v: Any) -> Optional[float]:
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _from_df(df: pl.DataFrame) -> Dict[str, Any]:
    """Derive session-level OHLC/volume/avg_price from the intraday DF."""
    out: Dict[str, Any] = {}
    try:
        # open / high / low from session so far
        if "open" in df.columns:
            out["open"] = float(df["open"].head(1)[0])
        if "high" in df.columns:
            out["high"] = float(df["high"].max())
        if "low" in df.columns:
            out["low"] = float(df["low"].min())

        # volume = sum over session
        if "volume" in df.columns:
            vol = float(df["volume"].sum())
            out["volume"] = vol if vol > 0 else None
        else:
            vol = 0.0

        # avg_price (session VWAP-ish)
        if vol > 0 and all(c in df.columns for c in ("close", "volume")):
            num = (df["close"].cast(pl.Float64) * df["volume"].cast(pl.Float64)).sum()
            out["avg_price"] = float(num) / vol if vol else None
    except Exception:
        pass
    return out


def _from_nse(symbol: str) -> Dict[str, Any]:
    """UC/LC + prevClose + 52W bands from NSE fetcher (with cache)."""
    bands = get_cached_nse_bands(symbol) or fetch_nse_bands(symbol)
    if not isinstance(bands, dict):
        return {}

    out: Dict[str, Any] = {}
    uc = _safe_float(bands.get("upper_circuit"))
    lc = _safe_float(bands.get("lower_circuit"))
    pc = _safe_float(bands.get("prev_close"))
    yh = _safe_float(bands.get("year_high"))
    yl = _safe_float(bands.get("year_low"))

    if uc is not None:
        out["upper_circuit"] = uc
    if lc is not None:
        out["lower_circuit"] = lc
    if pc is not None:
        out["prev_close"] = pc
    if yh is not None:
        out["52w_high"] = yh
    if yl is not None:
        out["52w_low"] = yl

    return out


def enrich_instrument_snapshot(
    symbol: str,
    base: Dict[str, Any],
    *,
    df: Optional[pl.DataFrame] = None,
) -> Dict[str, Any]:
    """Merge instrument snapshot fields into `base` dict.

    Adds (when available):
      - open, high, low
      - volume, avg_price
      - prev_close
      - upper_circuit, lower_circuit
      - 52w_high, 52w_low
    """
    out: Dict[str, Any] = dict(base)

    # 1) From DF
    if isinstance(df, pl.DataFrame) and not df.is_empty():
        out.update({k: v for k, v in _from_df(df).items() if v is not None})

    # 2) From NSE bands (UC/LC + prevClose + 52W)
    nse_bits = _from_nse(symbol)
    for k, v in nse_bits.items():
        # don't overwrite if base already has a strong opinion
        if k not in out or out[k] is None:
            out[k] = v

    return out

#!/usr/bin/env python3
# ============================================================
# queen/services/enrich_instruments.py — v1.0
# Instrument snapshot enricher (OHLC / volume / UC-LC / 52W / avg_price)
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import polars as pl

from queen.fetchers.nse_fetcher import fetch_nse_bands, get_cached_nse_bands
from queen.helpers.market import MARKET_TZ  # 👈 reuse this


def _safe_float(v: Any) -> Optional[float]:
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _from_df(df: pl.DataFrame) -> Dict[str, Any]:
    """Derive *today's* session OHLC/volume/avg_price from intraday DF."""
    out: Dict[str, Any] = {}
    if df.is_empty() or "timestamp" not in df.columns:
        return out

    try:
        # restrict to today's bars in MARKET_TZ
        today_ist = datetime.now(tz=MARKET_TZ).date()
        dated = df.with_columns(
            pl.col("timestamp")
            .dt.convert_time_zone(str(MARKET_TZ))
            .dt.date()
            .alias("d")
        )
        df_today = dated.filter(pl.col("d") == today_ist).drop("d")

        # if, for some reason, today has no bars (pre-open etc), fall back to full DF
        src = df_today if not df_today.is_empty() else df

        # open / high / low from chosen slice
        if "open" in src.columns:
            out["open"] = float(src["open"].head(1)[0])
        if "high" in src.columns:
            out["high"] = float(src["high"].max())
        if "low" in src.columns:
            out["low"] = float(src["low"].min())

        # volume = sum over chosen slice
        vol = 0.0
        if "volume" in src.columns:
            vol = float(src["volume"].sum())
            out["volume"] = vol if vol > 0 else None

        # avg_price (session VWAP-ish)
        if vol > 0 and all(c in src.columns for c in ("close", "volume")):
            num = (
                src["close"].cast(pl.Float64)
                * src["volume"].cast(pl.Float64)
            ).sum()
            out["avg_price"] = float(num) / vol if vol else None

    except Exception:
        # swallow & return whatever we managed to compute
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

#!/usr/bin/env python3
# ============================================================
# queen/services/enrich_instruments.py — v1.2
# Instrument snapshot enricher (NSE + intraday volume/avg_price)
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import polars as pl

from queen.fetchers.nse_fetcher import fetch_nse_bands
from queen.helpers.market import MARKET_TZ


def _safe_float(v: Any) -> Optional[float]:
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _from_df(df: pl.DataFrame) -> Dict[str, Any]:
    """Derive session volume + avg_price from intraday DF (today only)."""
    out: Dict[str, Any] = {}
    if df.is_empty() or "timestamp" not in df.columns:
        return out

    try:
        today_ist = datetime.now(tz=MARKET_TZ).date()
        dated = df.with_columns(
            pl.col("timestamp")
            .dt.convert_time_zone(str(MARKET_TZ))
            .dt.date()
            .alias("d")
        )
        df_today = dated.filter(pl.col("d") == today_ist).drop("d")
        src = df_today if not df_today.is_empty() else df

        vol = 0.0
        if "volume" in src.columns:
            vol = float(src["volume"].sum())
            out["volume"] = vol if vol > 0 else None

        if vol > 0 and all(c in src.columns for c in ("close", "volume")):
            num = (
                src["close"].cast(pl.Float64)
                * src["volume"].cast(pl.Float64)
            ).sum()
            out["avg_price"] = float(num) / vol if vol else None
    except Exception:
        pass

    return out


def _from_nse(symbol: str) -> Dict[str, Any]:
    """OHLC/PrevClose/UC/LC/52W + VWAP from NSE (cached via nse_fetcher)."""
    bands = fetch_nse_bands(symbol)
    if not isinstance(bands, dict):
        return {}

    out: Dict[str, Any] = {}

    op = _safe_float(bands.get("open"))
    lp = _safe_float(bands.get("last_price"))
    dh = _safe_float(bands.get("day_high"))
    dl = _safe_float(bands.get("day_low"))
    vw = _safe_float(bands.get("vwap"))

    uc = _safe_float(bands.get("upper_circuit"))
    lc = _safe_float(bands.get("lower_circuit"))
    pc = _safe_float(bands.get("prev_close"))
    yh = _safe_float(bands.get("year_high"))
    yl = _safe_float(bands.get("year_low"))

    if op is not None:
        out["open"] = op
    # day_high / day_low are your intraday H/L
    if dh is not None:
        out["high"] = dh
    if dl is not None:
        out["low"] = dl
    if vw is not None:
        out["vwap"] = vw
    if lp is not None:
        out["nse_last"] = lp  # optional debug field

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
    """Merge NSE + intraday enrichments into `base` dict.

    Adds (when available):
      - open, high, low, prev_close, vwap
      - volume, avg_price
      - upper_circuit, lower_circuit
      - 52w_high, 52w_low (+ aliases high_52w / low_52w)
    """
    out: Dict[str, Any] = dict(base)

    # 1) Intraday: volume + avg_price only
    if isinstance(df, pl.DataFrame) and not df.is_empty():
        out.update({k: v for k, v in _from_df(df).items() if v is not None})

    # 2) NSE snapshot (single source of truth for OHLC / UC/LC / 52W / VWAP)
    nse_bits = _from_nse(symbol)
    for k, v in nse_bits.items():
        if v is not None and out.get(k) is None:
            out[k] = v

    # 3) Compatibility aliases for 52W fields
    if "52w_high" in out and "high_52w" not in out:
        out["high_52w"] = out["52w_high"]
    if "52w_low" in out and "low_52w" not in out:
        out["low_52w"] = out["52w_low"]

    return out

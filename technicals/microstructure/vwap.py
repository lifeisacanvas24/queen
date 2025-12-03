#!/usr/bin/env python3
# ======================================================================
# queen/technicals/microstructure/vwap.py — v1.0
# ----------------------------------------------------------------------
# VWAP microstructure engine (Polars-only).
#
# Responsibilities:
#   • Ensure DF is time-sorted (AUTO).
#   • Find price + volume columns robustly.
#   • Compute session VWAP (or window VWAP).
#   • Compute last-close distance vs VWAP.
#   • Classify:
#       - zone: "above" / "at" / "below"
#       - band: "far_above" / "above" / "near" / "below" / "far_below"
#
# Output:
#   • VWAPState dataclass (from state_objects.py)
#
# NOTE:
#   • All thresholds are v1 defaults; can be moved to settings later.
# ======================================================================

from __future__ import annotations

from typing import Optional

import polars as pl
from queen.technicals.microstructure.state_objects import VWAPState

# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    """Ensure DF is sorted by timestamp ascending.

    AUTO behaviour: all helpers take responsibility for sorting.
    Safe to call even if already sorted.
    """
    if ts_col not in df.columns:
        return df
    return df.sort(ts_col)


def _pick_price_col(df: pl.DataFrame) -> Optional[str]:
    """Try to find a logical "close/price" column.

    Priority:
      • "close"
      • "Close"
      • "price"
      • "Price"
      • "last_price"
    """
    candidates = ["close", "Close", "price", "Price", "last_price"]
    existing = [c for c in candidates if c in df.columns]
    return existing[0] if existing else None


def _pick_volume_col(df: pl.DataFrame) -> Optional[str]:
    """Try to find a volume column in a robust way.

    Priority:
      • "volume"
      • "Volume"
      • "VOL"
      • "qty"
    """
    candidates = ["volume", "Volume", "VOL", "qty"]
    existing = [c for c in candidates if c in df.columns]
    return existing[0] if existing else None


def _select_window(
    df: pl.DataFrame,
    lookback_bars: int | None,
) -> pl.DataFrame:
    """If lookback_bars is given: last N bars.
    Otherwise: full DF (session VWAP).
    """
    if lookback_bars is None:
        return df
    if df.height <= lookback_bars:
        return df
    return df.tail(lookback_bars)


def _zone_and_band(offset_pct: float, at_tol_pct: float = 0.15) -> tuple[str, str]:
    """Given offset_pct = (last - vwap)/vwap * 100,
    derive:
      • zone: above / at / below
      • band: far_above / above / near / below / far_below
    """
    # zone
    if abs(offset_pct) <= at_tol_pct:
        zone = "at"
    elif offset_pct > 0:
        zone = "above"
    else:
        zone = "below"

    # band (v1 defaults):
    #   • far_above:  offset ≥ +1.5%
    #   • above:      +0.3% ≤ offset < +1.5%
    #   • near:       -0.3% < offset < +0.3%
    #   • below:      -1.5% < offset ≤ -0.3%
    #   • far_below:  offset ≤ -1.5%
    if offset_pct >= 1.5:
        band = "far_above"
    elif offset_pct >= 0.3:
        band = "above"
    elif offset_pct > -0.3:
        band = "near"
    elif offset_pct > -1.5:
        band = "below"
    else:
        band = "far_below"

    return zone, band


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_vwap(
    df: pl.DataFrame,
    *,
    price_col: str | None = None,
    volume_col: str | None = None,
    timestamp_col: str = "timestamp",
    lookback_bars: int | None = None,
) -> VWAPState:
    """POLARS DF (OHLCV-like)  →  VWAPState

    Parameters
    ----------
    df : pl.DataFrame
        Intraday or daily DF with price + volume columns.
    price_col : str | None
        Name of the price/close column. If None, auto-detected.
    volume_col : str | None
        Name of the volume column. If None, auto-detected.
    timestamp_col : str
        Column used to sort the DF (default: "timestamp").
    lookback_bars : int | None
        If given: use only the last N bars for VWAP.
        If None: use the full DF (session VWAP).

    Returns
    -------
    VWAPState
        Dataclass with:
          • vwap
          • last_price
          • offset_pct
          • zone
          • band

    """
    # Empty → neutral VWAP state
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return VWAPState(
            vwap=0.0,
            last_price=0.0,
            offset_pct=0.0,
            zone="at",
            band="near",
        )

    # 1) Ensure sorted
    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)

    # 2) Detect columns
    px_col = price_col or _pick_price_col(df_sorted)
    vol_col = volume_col or _pick_volume_col(df_sorted)

    if px_col is None or vol_col is None:
        # Cannot compute VWAP → treat price and VWAP as 0
        return VWAPState(
            vwap=0.0,
            last_price=0.0,
            offset_pct=0.0,
            zone="at",
            band="near",
        )

    # 3) Window
    window = _select_window(df_sorted, lookback_bars)

    # 4) Prepare series
    px = window.get_column(px_col).cast(pl.Float64)
    vol = window.get_column(vol_col).cast(pl.Float64)

    # 5) VWAP = sum(p * v) / sum(v)
    vol_sum = float(vol.sum() or 0.0)
    if vol_sum <= 0:
        vwap_val = float(px.tail(1).item())
    else:
        vwap_val = float((px * vol).sum() / vol_sum)

    last_price = float(px.tail(1).item())
    if vwap_val > 0:
        offset_pct = (last_price - vwap_val) / vwap_val * 100.0
    else:
        offset_pct = 0.0

    zone, band = _zone_and_band(offset_pct)

    return VWAPState(
        vwap=vwap_val,
        last_price=last_price,
        offset_pct=offset_pct,
        zone=zone,
        band=band,
    )


# ======================================================================
# Example usage (manual test)
# ======================================================================

if __name__ == "__main__":
    data = {
        "timestamp": [
            "2025-11-28 09:15",
            "2025-11-28 09:30",
            "2025-11-28 09:45",
            "2025-11-28 10:00",
            "2025-11-28 10:15",
        ],
        "close": [100, 102, 101, 103, 104],
        "volume": [1000, 1500, 1200, 1300, 1600],
    }
    df = pl.DataFrame(data)
    vs = detect_vwap(df)
    print(vs)
    # Expect:
    #   vwap ≈ weighted average around 102-ish
    #   last_price = 104
    #   offset_pct > 0
    #   zone = "above"

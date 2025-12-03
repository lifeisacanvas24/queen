#!/usr/bin/env python3
# ======================================================================
# queen/helpers/structure.py — v1.0
# ----------------------------------------------------------------------
# Price–structure engine (Polars-only, DF-in → StructureState-out)
#
# Responsibilities:
#   • Ensure intraday DF is time-sorted (AUTO).
#   • Look at a configurable lookback window (default: 20 bars).
#   • Detect:
#       - Trend direction (UP / DOWN / FLAT)
#       - Structural label:
#           IMPULSE_UP / IMPULSE_DOWN
#           PULLBACK_UP / PULLBACK_DOWN
#           COMPRESSION / EXPANSION / RANGE
#       - Simple swing highs / lows (for context only)
#       - Compression ratio (0 → no compression, 1 → very tight)
#
# Output:
#   • StructureState dataclass (from helpers/state_objects.py)
#
# This is intentionally simple and robust:
#   - No indicators, just OHLC + basic ranges.
#   - Easy to replace / refine with more advanced logic later.
# ======================================================================

from __future__ import annotations

from typing import List, Tuple

import polars as pl
from queen.helpers.state_objects import (
    StructureLabel,
    StructureState,
    TrendDirection,
)

# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _ensure_sorted(
    df: pl.DataFrame,
    ts_col: str = "timestamp",
) -> pl.DataFrame:
    """Ensure the given DataFrame is sorted by timestamp ascending.

    AUTO mode: every helper that inspects bars calls this internally.
    """
    if ts_col not in df.columns:
        # No timestamp column → just return as-is
        return df
    # Safe even if already sorted
    return df.sort(ts_col)


def _select_window(
    df: pl.DataFrame,
    lookback_bars: int,
) -> pl.DataFrame:
    """Take the last `lookback_bars` rows (or all if smaller).

    This is our microstructure window; higher-level engines can choose
    different lookbacks per timeframe (e.g. 20 for 5m, 30 for 15m).
    """
    if df.height <= lookback_bars:
        return df
    return df.tail(lookback_bars)


def _compute_trend_direction(
    window: pl.DataFrame,
    price_col: str,
) -> TrendDirection:
    """Very simple trend direction estimator:
    • Compare last close vs average of first half of window.
    • Use small band to mark FLAT (noise).
    """
    if window.is_empty():
        return "FLAT"

    s = window.get_column(price_col).cast(pl.Float64)

    last = float(s.tail(1).item())
    mid_idx = max(1, window.height // 2)
    base = float(s.head(mid_idx).mean())

    if base == 0:
        return "FLAT"

    rel = (last - base) / base

    # Tiny thresholds (can be tuned / moved to settings later)
    if rel >= 0.003:   # +0.3% up
        return "UP"
    if rel <= -0.003:  # -0.3% down
        return "DOWN"
    return "FLAT"


def _compression_ratio(
    window: pl.DataFrame,
    high_col: str,
    low_col: str,
    inner_span: int = 5,
) -> float:
    """Compression metric in [0, 1]:

      • Take full-window range: max(high) - min(low)
      • Take inner-window range (last `inner_span` bars)
      • ratio_raw = inner_range / full_range
      • compression_ratio = 1 - clip(ratio_raw, 0, 1)

    Interpretation:
      • 0.0 → inner range ~= full range (no compression).
      • 1.0 → inner range ≪ full range (strong compression).
    """
    if window.is_empty():
        return 0.0

    hi = window.get_column(high_col).cast(pl.Float64)
    lo = window.get_column(low_col).cast(pl.Float64)

    full_hi = float(hi.max())
    full_lo = float(lo.min())
    full_range = full_hi - full_lo

    if full_range <= 0:
        return 1.0  # price flat → extremely compressed

    # Inner range (last `inner_span` bars)
    if window.height <= inner_span:
        inner = window
    else:
        inner = window.tail(inner_span)

    hi_inner = inner.get_column(high_col).cast(pl.Float64)
    lo_inner = inner.get_column(low_col).cast(pl.Float64)

    inner_range = float(hi_inner.max() - lo_inner.min())
    if inner_range < 0:
        inner_range = 0.0

    raw = inner_range / full_range
    if raw < 0:
        raw = 0.0
    if raw > 1:
        raw = 1.0

    return float(1.0 - raw)


def _recent_extremes(
    window: pl.DataFrame,
    high_col: str,
    low_col: str,
) -> Tuple[float, float]:
    """Convenience: full-window high & low as floats.
    """
    if window.is_empty():
        return 0.0, 0.0

    hi = float(window.get_column(high_col).cast(pl.Float64).max())
    lo = float(window.get_column(low_col).cast(pl.Float64).min())
    return hi, lo


def _find_swings(
    window: pl.DataFrame,
    high_col: str,
    low_col: str,
    max_points: int = 3,
) -> Tuple[List[float], List[float]]:
    """Naive fractal-based swing detection:

      • Swing high at i if:
          high[i] > high[i-1] and high[i] > high[i+1]
      • Swing low at i if:
          low[i] < low[i-1] and low[i] < low[i+1]

    We only return the last `max_points` of each, as a hint for
    structure / debugging, NOT for precise trading decisions.
    """
    n = window.height
    if n < 3:
        return [], []

    hi = window.get_column(high_col).cast(pl.Float64).to_list()
    lo = window.get_column(low_col).cast(pl.Float64).to_list()

    swing_highs: List[float] = []
    swing_lows: List[float] = []

    for i in range(1, n - 1):
        if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]:
            swing_highs.append(float(hi[i]))
        if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:
            swing_lows.append(float(lo[i]))

    # keep only last `max_points`
    if swing_highs:
        swing_highs = swing_highs[-max_points:]
    if swing_lows:
        swing_lows = swing_lows[-max_points:]

    return swing_highs, swing_lows


def _structure_label(
    direction: TrendDirection,
    window: pl.DataFrame,
    price_col: str,
    high_col: str,
    low_col: str,
    compression: float,
) -> StructureLabel:
    """Decide high-level structure label using:

      • direction (UP / DOWN / FLAT)
      • compression (0–1)
      • position of last close vs full range

    Rules (simple v1):

      1) Strong compression → COMPRESSION
      2) FLAT direction → RANGE
      3) UP:
           last_close near top of range → IMPULSE_UP
           else                       → PULLBACK_UP
      4) DOWN:
           last_close near bottom      → IMPULSE_DOWN
           else                        → PULLBACK_DOWN
    """
    if window.is_empty():
        return "RANGE"

    # 1) Compression dominates if very strong
    if compression >= 0.7:
        return "COMPRESSION"

    # 2) Flat → RANGE, unless extremely wide (future EXPANSION logic)
    if direction == "FLAT":
        return "RANGE"

    # 3) Position of last close within window range
    s = window.get_column(price_col).cast(pl.Float64)
    last = float(s.tail(1).item())

    hi, lo = _recent_extremes(window, high_col, low_col)
    rng = hi - lo
    if rng <= 0:
        # Price flat but direction != FLAT → just call it RANGE
        return "RANGE"

    pos = (last - lo) / rng  # 0 at bottom, 1 at top

    if direction == "UP":
        # near top third of range → impulse
        if pos >= 0.66:
            return "IMPULSE_UP"
        return "PULLBACK_UP"

    if direction == "DOWN":
        # near bottom third → impulse down
        if pos <= 0.33:
            return "IMPULSE_DOWN"
        return "PULLBACK_DOWN"

    # fallback (should not hit)
    return "RANGE"


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_structure(
    df: pl.DataFrame,
    *,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    timestamp_col: str = "timestamp",
    lookback_bars: int = 20,
) -> StructureState:
    """Main entrypoint:

    POLARS DF (intraday or daily)  →  StructureState

    This function is:
      • Side-effect free (no mutation of df).
      • Auto-sorting by timestamp.
      • Simple & robust.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV-like frame with at least `price_col`, `high_col`, `low_col`.
    price_col : str
        Column to use as primary price for trend (default: "close").
    high_col : str
        Column for highs (default: "high").
    low_col : str
        Column for lows (default: "low").
    timestamp_col : str
        Timestamp column (default: "timestamp") used for sorting.
    lookback_bars : int
        Number of bars to consider for structure detection.

    Returns
    -------
    StructureState
        Dataclass with direction + structure label + swing points
        + compression_ratio.

    Notes
    -----
    • This is a v1.0 engine; the exact thresholds / rules can be made
      configurable via settings/timeframes.py or settings/structure.py
      later without changing the interface.

    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        # Completely neutral, no information
        return StructureState(
            direction="FLAT",
            label="RANGE",
            swing_highs=[],
            swing_lows=[],
            compression_ratio=0.0,
        )

    # 1) Ensure sorted
    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)

    # 2) Select microstructure window
    window = _select_window(df_sorted, lookback_bars)

    # 3) Compute direction
    direction = _compute_trend_direction(window, price_col)

    # 4) Compression
    comp = _compression_ratio(window, high_col, low_col)

    # 5) Swings (context only)
    sh, sl = _find_swings(window, high_col, low_col)

    # 6) Structure label
    label = _structure_label(direction, window, price_col, high_col, low_col, comp)

    return StructureState(
        direction=direction,
        label=label,
        swing_highs=sh,
        swing_lows=sl,
        compression_ratio=comp,
    )


# ======================================================================
# Example usage (for tests / scan_signals experiments)
# ======================================================================

if __name__ == "__main__":
    # Simple smoke test with synthetic data
    data = {
        "timestamp": [
            "2025-11-28 09:15",
            "2025-11-28 09:30",
            "2025-11-28 09:45",
            "2025-11-28 10:00",
            "2025-11-28 10:15",
            "2025-11-28 10:30",
        ],
        "high": [100, 102, 104, 105, 106, 107],
        "low": [ 98,  99, 100, 101, 102, 103],
        "close": [99, 101, 103, 104, 105, 106],
    }
    test_df = pl.DataFrame(data)
    st = detect_structure(test_df, lookback_bars=6)
    print(st)
    # Expected:
    #   direction ≈ "UP"
    #   label ≈ "IMPULSE_UP" or "PULLBACK_UP"
    #   compression_ratio somewhere in [0, 1]

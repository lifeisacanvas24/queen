#!/usr/bin/env python3
# ======================================================================
# queen/technicals/microstructure/cpr.py — v1.0
# ----------------------------------------------------------------------
# CPR (Central Pivot Range) microstructure engine (Polars-only).
#
# Responsibilities:
#   • Ensure DF is time-sorted (AUTO).
#   • Compute session H/L/C (or use explicit inputs).
#   • Compute:
#       - P (pivot)
#       - BC, TC
#   • Identify:
#       - CPR width (% of price)
#       - Width regime:
#           NARROW / NORMAL / WIDE
#       - Location of last price relative to CPR:
#           above_tc / between_tc_p / between_p_bc / below_bc
#
# Output:
#   • CPRState dataclass (from state_objects.py)
#
# NOTE:
#   • v1 uses same-day H/L/C as proxy if prev-day H/L/C not given.
# ======================================================================

from __future__ import annotations

from typing import Optional

import polars as pl
from queen.technicals.microstructure.state_objects import CPRState

# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    if ts_col not in df.columns:
        return df
    return df.sort(ts_col)


def _pick_ohlc_cols(df: pl.DataFrame) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Detect (high, low, close) columns.
    """
    high_candidates = ["high", "High", "day_high"]
    low_candidates = ["low", "Low", "day_low"]
    close_candidates = ["close", "Close", "last_price"]

    high = next((c for c in high_candidates if c in df.columns), None)
    low = next((c for c in low_candidates if c in df.columns), None)
    close = next((c for c in close_candidates if c in df.columns), None)

    return high, low, close


def _width_regime(width_pct: float) -> str:
    """Simple CPR width classification.

    • NARROW : width_pct < 0.5%
    • NORMAL : 0.5% ≤ width_pct ≤ 1.5%
    • WIDE   : width_pct > 1.5%
    """
    if width_pct < 0.5:
        return "NARROW"
    if width_pct <= 1.5:
        return "NORMAL"
    return "WIDE"


def _location(last_price: float, bc: float, p: float, tc: float) -> str:
    """Location of last price relative to CPR:

    • last > TC         → "above_tc"
    • P < last ≤ TC     → "between_tc_p"
    • BC ≤ last ≤ P     → "between_p_bc"
    • last < BC         → "below_bc"
    """
    if last_price > tc:
        return "above_tc"
    if last_price > p:
        return "between_tc_p"
    if last_price >= bc:
        return "between_p_bc"
    return "below_bc"


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_cpr(
    df: pl.DataFrame,
    *,
    high_col: str | None = None,
    low_col: str | None = None,
    close_col: str | None = None,
    timestamp_col: str = "timestamp",
) -> CPRState:
    """POLARS DF (daily or intraday for ONE session) → CPRState

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV-like frame for the current day (or condensed).
    high_col / low_col / close_col : str | None
        If None, columns are auto-detected.
    timestamp_col : str
        Used for sorting.

    Returns
    -------
    CPRState
        Dataclass with:
          • p (pivot)
          • bc
          • tc
          • width_pct
          • width_regime
          • last_price
          • location

    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return CPRState(
            p=0.0,
            bc=0.0,
            tc=0.0,
            width_pct=0.0,
            width_regime="NARROW",
            last_price=0.0,
            location="between_p_bc",
        )

    # 1) Ensure sorted
    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)

    # 2) Detect OHLC columns
    h_col, l_col, c_col = _pick_ohlc_cols(df_sorted)

    high_col = high_col or h_col
    low_col = low_col or l_col
    close_col = close_col or c_col

    if high_col is None or low_col is None or close_col is None:
        # No CPR possible → neutral
        return CPRState(
            p=0.0,
            bc=0.0,
            tc=0.0,
            width_pct=0.0,
            width_regime="NARROW",
            last_price=0.0,
            location="between_p_bc",
        )

    # 3) Compute H/L/C over the DF
    high_series = df_sorted.get_column(high_col).cast(pl.Float64)
    low_series = df_sorted.get_column(low_col).cast(pl.Float64)
    close_series = df_sorted.get_column(close_col).cast(pl.Float64)

    H = float(high_series.max())
    L = float(low_series.min())
    C = float(close_series.tail(1).item())  # last close in the session

    # 4) CPR formulas (classic)
    p = (H + L + C) / 3.0
    bc = (H + L) / 2.0
    tc = 2.0 * p - bc

    if p != 0.0:
        width_pct = (tc - bc) / p * 100.0
    else:
        width_pct = 0.0

    width_regime = _width_regime(width_pct)
    loc = _location(C, bc, p, tc)

    return CPRState(
        p=p,
        bc=bc,
        tc=tc,
        width_pct=width_pct,
        width_regime=width_regime,
        last_price=C,
        location=loc,
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
        ],
        "high": [100, 102, 103, 104],
        "low": [98, 99, 100, 101],
        "close": [99, 101, 102, 103],
    }
    df = pl.DataFrame(data)
    cpr = detect_cpr(df)
    print(cpr)
    # Expect:
    #   p, bc, tc with a narrow-ish width_pct
    #   location depending on final close vs CPR band

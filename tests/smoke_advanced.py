#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_advanced.py — v1.0
# Verifies:
#   • attach_advanced() adds: bb_mid, bb_upper, bb_lower,
#                             supertrend, atr_upper, atr_lower
#   • shapes match input, dtypes are numeric, basic band sanity
# ============================================================

import math

import numpy as np
import polars as pl
from queen.technicals.indicators.advanced import (
    atr_channels,
    attach_advanced,
    bollinger_bands,
    supertrend,
)


# ---------------- helpers ----------------
def _mk_ohlcv(n: int = 240) -> pl.DataFrame:
    start = pl.datetime(2025, 1, 1, 9, 15, 0)
    end = start + pl.duration(minutes=n - 1)
    ts = pl.datetime_range(start, end, interval="1m", eager=True)

    # synthetic price path (trendy with noise)
    x = np.linspace(0, 8 * math.pi, n)
    base = 100 + 0.1 * np.arange(n) + 2.0 * np.sin(x) + np.random.normal(0, 0.4, n)
    high = base + np.random.uniform(0.2, 0.8, n)
    low = base - np.random.uniform(0.2, 0.8, n)
    close = base + np.random.normal(0, 0.2, n)
    open_ = close + np.random.normal(0, 0.15, n)
    volume = np.random.randint(1000, 5000, n)

    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": open_.astype(float),
            "high": high.astype(float),
            "low": low.astype(float),
            "close": close.astype(float),
            "volume": volume.astype(float),
            "symbol": ["TEST"] * n,  # ✅ fixed
        }
    )


def _is_numeric_dtype(dt: pl.DataType) -> bool:
    return dt in (pl.Float64, pl.Float32, pl.Int64, pl.Int32)


# ---------------- tests ----------------
def test_attach_advanced():
    df = _mk_ohlcv(240)
    out = attach_advanced(df)

    needed = ["bb_mid", "bb_upper", "bb_lower", "supertrend", "atr_upper", "atr_lower"]
    for c in needed:
        assert c in out.columns, f"missing advanced column: {c}"
        assert out.height == df.height, f"mismatched length for {c}"
        assert _is_numeric_dtype(out[c].dtype), f"{c} must be numeric dtype"
        # avoid completely-null columns
        assert out[c].drop_nulls().len() > 0, f"{c} is all nulls"

    # basic band sanity (ignore initial NaNs from rolling windows)
    mid = out["bb_mid"].drop_nans().drop_nulls()
    up = out["bb_upper"].drop_nans().drop_nulls()
    lo = out["bb_lower"].drop_nans().drop_nulls()
    if len(mid) > 0:
        # not strict per-row, but ensure plausible ordering occurs
        assert (up > mid).any(), "bb_upper should exceed bb_mid somewhere"
        assert (mid > lo).any(), "bb_mid should exceed bb_lower somewhere"

    print("✅ smoke_advanced: all checks passed")


def test_components_direct():
    df = _mk_ohlcv(120)
    bb_mid, bb_up, bb_lo = bollinger_bands(df)
    st = supertrend(df)
    up_ch, lo_ch = atr_channels(df)

    # lengths
    for s in (bb_mid, bb_up, bb_lo, st, up_ch, lo_ch):
        assert len(s) == df.height

    # dtypes
    for name, s in {
        "bb_mid": bb_mid,
        "bb_upper": bb_up,
        "bb_lower": bb_lo,
        "supertrend": st,
        "atr_upper": up_ch,
        "atr_lower": lo_ch,
    }.items():
        assert _is_numeric_dtype(s.dtype), f"{name} must be numeric dtype"

    print("✅ smoke_advanced (components): all checks passed")


if __name__ == "__main__":
    test_attach_advanced()
    test_components_direct()

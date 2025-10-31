#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_breadth_combo.py — CMV/SPS + Adv/Dec smoke
# ============================================================
from __future__ import annotations

import math

import polars as pl

# Engines under test (import guarded below in main)
#   breadth_cumulative.compute_breadth(df, context=...)
#   breadth_momentum.compute_breadth_momentum(df, context=...)


def _mk_breadth_frame(n: int = 240) -> pl.DataFrame:
    # synthetic CMV/SPS waves + advance/decline counts
    idx = list(range(n))
    cmv = [math.sin(i * 0.08) + math.sin(i * 0.017) for i in idx]  # [-2..2] raw-ish
    sps = [math.cos(i * 0.06) * 0.8 for i in idx]  # [-0.8..0.8]
    adv = [int(250 + 80 * math.sin(i * 0.05)) for i in idx]  # 250 ± 80
    dec = [int(500 - adv[i]) for i in idx]  # keep total ~500

    # put something resembling an OHLCV backbone to avoid merge/join issues
    close = [100.0 + 0.2 * i + 2.0 * math.sin(i * 0.03) for i in idx]
    open_ = [close[i] - (0.3 * math.sin(i * 0.07)) for i in idx]
    high = [max(open_[i], close[i]) + 0.6 for i in idx]
    low = [min(open_[i], close[i]) - 0.6 for i in idx]
    vol = [1000 + (i % 20) * 7 for i in idx]

    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                start=pl.datetime(2025, 1, 1, 9, 15),
                end=pl.datetime(2025, 1, 1, 9, 15) + pl.duration(minutes=n - 1),
                interval="1m",
                eager=True,
            ),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "CMV": cmv,
            "SPS": sps,
            "adv": adv,
            "dec": dec,
        }
    )


def _assert_range(series: pl.Series, lo: float, hi: float, name: str):
    vals = series.drop_nans().drop_nulls()
    if vals.is_empty():
        return
    mn = float(vals.min())
    mx = float(vals.max())
    assert (
        mn >= lo - 1e-6 and mx <= hi + 1e-6
    ), f"{name} out of [{lo},{hi}]: [{mn},{mx}]"


def test_breadth_combo():
    df = _mk_breadth_frame(360)
    # try imports gracefully
    try:
        from queen.technicals.indicators.breadth_cumulative import (
            compute_breadth as _bc,
        )
    except Exception:
        _bc = None
    try:
        from queen.technicals.indicators.breadth_momentum import (
            compute_breadth_momentum as _bm,
        )
    except Exception:
        _bm = None

    # at least one should exist in the tree
    assert (_bc is not None) or (_bm is not None), "breadth engines not available"

    out = df
    if _bc is not None:
        try:
            out_bc = _bc(df=df, context="intraday_15m")
            assert isinstance(out_bc, pl.DataFrame) and out_bc.height == df.height
            # soft checks on common column names
            for c in ("breadth_cum", "bcum", "BREADTH_CUM"):
                if c in out_bc.columns:
                    _assert_range(out_bc[c], -1.0, 1.0, c)
            out = (
                out.join(
                    out_bc,
                    on=[c for c in ("timestamp",) if c in df.columns],
                    how="inner",
                )
                if "timestamp" in out_bc.columns
                else out.hstack(out_bc)
            )
        except Exception as e:
            raise AssertionError(f"breadth_cumulative failed: {e}")

    if _bm is not None:
        try:
            out_bm = _bm(df=out, context="intraday_15m")
            assert isinstance(out_bm, pl.DataFrame) and out_bm.height == out.height
            # soft checks on common momentum names
            for c in ("bm", "bm_norm", "breadth_mom", "breadth_momentum"):
                if c in out_bm.columns:
                    # normalized channels should be in [-1,1] or [0,1]
                    lo, hi = (-1.0, 1.0) if "norm" not in c.lower() else (0.0, 1.0)
                    _assert_range(out_bm[c], lo, hi, c)
        except Exception as e:
            raise AssertionError(f"breadth_momentum failed: {e}")


if __name__ == "__main__":
    test_breadth_combo()
    print("✅ smoke_breadth_combo: all checks passed")

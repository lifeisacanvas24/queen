#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_breadth.py — Cumulative Breadth smoke test
# ============================================================

from __future__ import annotations

import math

import numpy as np
import polars as pl
from queen.technicals.indicators.breadth_cumulative import (
    compute_breadth,
    summarize_breadth,
)


def _make_cmv_sps(n: int = 180) -> pl.DataFrame:
    """Synthetic CMV/SPS series — simple sin/cos with noise."""
    x = np.linspace(0, 10, n)
    cmv = np.sin(x) + np.random.normal(0, 0.08, n)
    sps = np.cos(x * 0.8) + np.random.normal(0, 0.08, n)
    return pl.DataFrame({"CMV": cmv, "SPS": sps})


def _is_float_dtype(dt) -> bool:
    # Polars dtype guards that work across versions
    return dt in (pl.Float32, pl.Float64)


def test_compute_columns_and_types():
    df = _make_cmv_sps(160)
    out = compute_breadth(df, timeframe="1d")

    required = {"CMV_Breadth", "SPS_Breadth", "Breadth_Persistence", "Breadth_Bias"}
    assert required.issubset(
        set(out.columns)
    ), f"Missing columns: {required - set(out.columns)}"

    assert _is_float_dtype(out["CMV_Breadth"].dtype)
    assert _is_float_dtype(out["SPS_Breadth"].dtype)
    assert _is_float_dtype(out["Breadth_Persistence"].dtype)
    assert out["Breadth_Bias"].dtype == pl.Utf8

    # values should be finite where rolling window filled
    tail = out.tail(10)
    for col in ("CMV_Breadth", "SPS_Breadth", "Breadth_Persistence"):
        vals = tail[col].to_list()
        assert all(
            math.isfinite(float(v)) for v in vals if v is not None
        ), f"Non-finite in {col}"


def test_summary_keys_and_ranges():
    df = _make_cmv_sps(160)
    out = compute_breadth(df, timeframe="1d")
    summary = summarize_breadth(out)

    # required keys
    for k in ("Breadth_Persistence", "Bias", "Strength", "status"):
        assert k in summary, f"summary missing key: {k}"

    # ranges / values
    assert isinstance(summary["Breadth_Persistence"], (int, float))
    assert -1.0 <= float(summary["Breadth_Persistence"]) <= 1.0
    assert summary["Bias"] in {"🟢 Bullish", "⚪ Neutral", "🔴 Bearish"}
    assert summary["Strength"] in {"Strong", "Moderate", "Weak"}
    assert summary["status"] == "ok"


if __name__ == "__main__":
    # run tests inline without pytest
    test_compute_columns_and_types()
    test_summary_keys_and_ranges()
    print("✅ smoke_breadth: all checks passed")

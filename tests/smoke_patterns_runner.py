#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_patterns_runner.py — one-call aggregator smoke
# ============================================================
from __future__ import annotations

import math

import polars as pl
from queen.technicals.patterns.runner import run_patterns


def _mk_ohlcv(n: int = 320) -> pl.DataFrame:
    # gentle waves to trigger a few composites
    close = [100 + 2.0 * math.cos(i * 0.05) for i in range(n)]
    open_ = [close[i] - 0.25 * math.sin(i * 0.09) for i in range(n)]
    high = [max(open_[i], close[i]) + 0.5 for i in range(n)]
    low = [min(open_[i], close[i]) - 0.5 for i in range(n)]
    vol = [1200 + (i % 24) * 7 for i in range(n)]
    return pl.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol}
    )


def test_runner():
    df = _mk_ohlcv()
    out = run_patterns(df, include_core=True, include_composite=True)
    assert out.height == df.height

    # core columns exist (names come from patterns/core.EXPORTS)
    must_have = [
        "doji",
        "hammer",
        "shooting_star",
        "bullish_engulfing",
        "bearish_engulfing",
    ]
    for c in must_have:
        assert c in out.columns, f"missing core column: {c}"
        assert out[c].dtype == pl.Boolean

    # composite columns exist
    for c in ("pattern_name", "pattern_bias", "confidence", "pattern_group"):
        assert c in out.columns, f"missing composite column: {c}"

    # simple sanity: confidence within [0,100]
    conf = out["confidence"].drop_nulls()
    if not conf.is_empty():
        mn, mx = float(conf.min()), float(conf.max())
        assert 0 <= mn <= 100 and 0 <= mx <= 100

    print("✅ smoke_patterns_runner: all checks passed")


if __name__ == "__main__":
    test_runner()

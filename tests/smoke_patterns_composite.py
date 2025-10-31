#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_patterns_composite.py — Multi-candle pattern smoke
# ============================================================
from __future__ import annotations

import polars as pl
from queen.technicals.patterns.composite import detect_composite_patterns


def _mk_ohlcv(n: int = 120) -> pl.DataFrame:
    import math

    return pl.DataFrame(
        {
            "open": [100 + math.sin(i * 0.2) * 2 for i in range(n)],
            "high": [101 + math.sin(i * 0.2) * 2 for i in range(n)],
            "low": [99 + math.sin(i * 0.2) * 2 for i in range(n)],
            "close": [100 + math.cos(i * 0.2) * 2 for i in range(n)],
            "volume": [1000 + (i % 15) * 7 for i in range(n)],
        }
    )


def test_patterns_composite():
    df = _mk_ohlcv()
    out = detect_composite_patterns(df)
    assert "pattern_name" in out.columns
    assert "pattern_bias" in out.columns
    assert "confidence" in out.columns
    assert "pattern_group" in out.columns
    assert out.height == df.height
    print("✅ smoke_patterns_composite: all checks passed")


if __name__ == "__main__":
    test_patterns_composite()

#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_patterns_core.py — Core candle pattern smoke
# ============================================================
from __future__ import annotations

import polars as pl
from queen.technicals.patterns import core as pc


def _mk_ohlcv(n: int = 100) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "open": [100 + (i % 4) for i in range(n)],
            "high": [102 + (i % 5) for i in range(n)],
            "low": [99 - (i % 3) for i in range(n)],
            "close": [101 + ((i % 6) - 3) * 0.3 for i in range(n)],
            "volume": [1000 + (i % 10) * 10 for i in range(n)],
        }
    )


def test_patterns_core():
    df = _mk_ohlcv(120)
    # run all exported detection functions (except required_lookback)
    for name, func in pc.EXPORTS.items():
        if name == "required_lookback":
            continue
        out = func(df)
        assert isinstance(out, pl.Series)
        assert out.len() == df.height
    print("✅ smoke_patterns_core: all checks passed")


if __name__ == "__main__":
    test_patterns_core()

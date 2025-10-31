#!/usr/bin/env python3
from __future__ import annotations

import math

import numpy as np
import polars as pl
from queen.technicals.signals.fusion.liquidity_breadth import (
    compute_liquidity_breadth_fusion as compute_lbx,
)
from queen.technicals.signals.fusion.liquidity_breadth import (
    summarize_liquidity_breadth,
)


def _mk_ohlcv(n=400):
    idx = list(range(n))
    base = [100 + 0.02 * i + 1.0 * math.sin(i * 0.03) for i in idx]
    open_ = [base[i] + 0.1 * math.sin(i * 0.07) for i in idx]
    close = [base[i] + 0.2 * math.sin(i * 0.05) for i in idx]
    high = [max(open_[i], close[i]) + 0.6 for i in idx]
    low = [min(open_[i], close[i]) - 0.6 for i in idx]
    vol = [1000 + (i % 40) * 11 for i in idx]
    # optional helpers if available; neutral defaults are fine otherwise
    rsi14 = [50.0] * n
    obv = np.cumsum(np.random.randint(-5, 5, n)).tolist()
    sps = [0.0] * n
    return pl.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "rsi_14": rsi14,
            "obv": obv,
            "SPS": sps,
        }
    )


def test():
    df = _mk_ohlcv(400)
    out = compute_lbx(df, context="intraday_15m")
    for c in ("LBX", "LBX_norm", "LBX_bias"):
        assert c in out.columns, f"missing {c}"
    s = summarize_liquidity_breadth(out)
    assert "LBX_norm" in s and 0.0 <= s["LBX_norm"] <= 1.0
    print("LBX summary:", s)


if __name__ == "__main__":
    test()
    print("✅ smoke_fusion_lbx: all checks passed")

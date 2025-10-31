#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.fusion.cmv import compute_cmv
from queen.technicals.signals.fusion.market_regime import (
    compute_market_regime,
    summarize_market_regime,
)


def _mk(n=240):
    idx = np.arange(n)
    base = 100 + 0.05 * idx + np.sin(idx * 0.03)
    open_ = base + 0.1 * np.sin(idx * 0.07)
    close = base + 0.2 * np.sin(idx * 0.05)
    high = np.maximum(open_, close) + 0.8
    low = np.minimum(open_, close) - 0.8
    vol = 1000 + (idx % 30) * 13
    rsi = 50 + 10 * np.sin(idx * 0.02)
    obv = np.cumsum(np.random.randint(-5, 5, n))
    sps = np.sin(idx * 0.015)
    return pl.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "rsi_14": rsi,
            "obv": obv,
            "SPS": sps,
        }
    )


def test():
    df = _mk(480)
    df = compute_cmv(df)  # supplies CMV needed by LBX if available
    out = compute_market_regime(df, context="intraday_15m")
    # existence checks
    for c in ("RScore", "RScore_norm", "RScore_bias"):
        assert c in out.columns, f"missing {c}"
    # value sanity
    n = out.height
    assert n == df.height
    s = summarize_market_regime(out)
    assert "RScore_norm" in s and "RScore_bias" in s and "Regime" in s
    print("RScore:", s)


if __name__ == "__main__":
    test()
    print("✅ smoke_fusion_market_regime: all checks passed")

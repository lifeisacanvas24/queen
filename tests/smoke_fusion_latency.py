#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_fusion_latency.py — CMV perf probe (~2k rows)
# ============================================================
from __future__ import annotations

import math
import time

import polars as pl
from queen.technicals.signals.fusion.cmv import compute_cmv


def _mk_ohlcv(n: int = 2000) -> pl.DataFrame:
    idx = list(range(n))
    base = [100.0 + 0.01 * i + 0.8 * math.sin(i * 0.03) for i in idx]
    open_ = [base[i] + 0.1 * math.sin(i * 0.07) for i in idx]
    close = [base[i] + 0.2 * math.sin(i * 0.05) for i in idx]
    high = [max(open_[i], close[i]) + 0.5 for i in idx]
    low = [min(open_[i], close[i]) - 0.5 for i in idx]
    vol = [1000 + (i % 50) * 9 for i in idx]

    # neutral helpers (so compute_cmv doesn’t need to synthesize)
    rsi14 = [50.0 for _ in idx]
    obv = [0.0 for _ in idx]
    sps = [0.0 for _ in idx]

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


def test_latency():
    df = _mk_ohlcv(2000)
    t0 = time.perf_counter()
    out = compute_cmv(df)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    # sanity columns
    needed = ["CMV_raw", "CMV_smooth", "CMV", "CMV_Bias", "CMV_TrendUp", "CMV_Flip"]
    for c in needed:
        assert c in out.columns, f"missing column: {c}"

    # soft perf budget (tune per machine; 40ms is a reasonable guard here)
    assert dt_ms < 40.0, f"CMV too slow: {dt_ms:.2f} ms"
    print(f"⏱️ CMV latency (N≈2000): {dt_ms:.2f} ms")


if __name__ == "__main__":
    test_latency()

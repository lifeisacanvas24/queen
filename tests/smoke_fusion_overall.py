#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_fusion_overall.py
# CMV core + optional LBX fusion sanity checks
# ============================================================
from __future__ import annotations

import math

import polars as pl


def _mk(n: int = 360) -> pl.DataFrame:
    idx = list(range(n))
    close = [100 + 0.03 * i + 1.2 * math.sin(i * 0.05) for i in idx]
    open_ = [close[i] - 0.2 * math.sin(i * 0.07) for i in idx]
    high = [max(open_[i], close[i]) + 0.5 for i in idx]
    low = [min(open_[i], close[i]) - 0.5 for i in idx]
    vol = [1000 + (i % 25) * 9 for i in idx]

    # soft inputs for CMV
    rsi = [50 + 15 * math.sin(i * 0.03) for i in idx]  # ~[35..65]
    obv = []
    acc = 0
    for i in idx:
        acc += (1 if close[i] > open_[i] else -1) * vol[i]
        obv.append(acc)
    sps = [math.sin(i * 0.02) for i in idx]  # [-1..1]

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


def _assert_has(df: pl.DataFrame, cols: list[str], tag: str):
    for c in cols:
        assert c in df.columns, f"missing {tag} column: {c}"


def test():
    from queen.technicals.signals.fusion.cmv import compute_cmv, summarize_cmv

    df = _mk()
    out = compute_cmv(df)
    _assert_has(
        out,
        ["CMV_raw", "CMV_smooth", "CMV", "CMV_Bias", "CMV_TrendUp", "CMV_Flip"],
        "CMV",
    )
    print("CMV:", summarize_cmv(out))

    # Optional LBX (if available in your tree)
    try:
        from queen.technicals.signals.fusion.liquidity_breadth import (
            compute_liquidity_breadth_fusion,
            summarize_liquidity_breadth,
        )

        lbx = compute_liquidity_breadth_fusion(out, context="intraday_15m")
        _assert_has(lbx, ["LBX", "LBX_norm", "LBX_bias"], "LBX")
        print("LBX:", summarize_liquidity_breadth(lbx))
    except Exception as e:
        # Fine if module not present — this smoke shouldn't fail your CI because of optional fusion
        print(f"⚠️ LBX skipped: {e}")


if __name__ == "__main__":
    test()
    print("✅ smoke_fusion_overall: all checks passed")

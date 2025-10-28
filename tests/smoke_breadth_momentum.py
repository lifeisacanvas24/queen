#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_breadth_momentum.py
# ============================================================
import numpy as np
import polars as pl
from queen.technicals.indicators.breadth_momentum import (
    compute_breadth_momentum,
    compute_regime_strength,
    summarize_breadth_momentum,
)


def _assert_between(x: float, lo: float, hi: float):
    assert lo <= x <= hi, f"value {x} not in [{lo},{hi}]"


def _assert_bias(token: str):
    assert token in {"🟢 Bullish", "⚪ Neutral", "🔴 Bearish"}


def test_cmv_sps_path():
    n = 200
    x = np.linspace(0, 10, n)
    cmv = np.sin(x) + np.random.normal(0, 0.05, n)
    sps = np.cos(x) + np.random.normal(0, 0.05, n)
    df = pl.DataFrame({"CMV": cmv, "SPS": sps})

    out = compute_breadth_momentum(df, timeframe="intraday_15m")
    assert "Breadth_Momentum" in out.columns
    assert "Breadth_Momentum_Bias" in out.columns

    last = float(out["Breadth_Momentum"][-1])
    _assert_between(last, -1.0, 1.0)
    _assert_bias(str(out["Breadth_Momentum_Bias"][-1]))

    summary = summarize_breadth_momentum(out)
    assert summary.get("status") == "ok"
    _assert_between(float(summary["Breadth_Momentum"]), -1.0, 1.0)
    _assert_bias(summary["Bias"])

    rscore = compute_regime_strength(out)
    _assert_between(float(rscore), 0.0, 1.0)


def test_adv_dec_path():
    n = 120
    adv = np.random.randint(100, 500, size=n)
    dec = np.random.randint(100, 500, size=n)
    df = pl.DataFrame({"advancers": adv, "decliners": dec})

    out = compute_breadth_momentum(df, timeframe="daily")
    assert "Breadth_Momentum" in out.columns
    assert "Breadth_Momentum_Bias" in out.columns

    last = float(out["Breadth_Momentum"][-1])
    _assert_between(last, -1.0, 1.0)
    _assert_bias(str(out["Breadth_Momentum_Bias"][-1]))

    summary = summarize_breadth_momentum(out)
    assert summary.get("status") == "ok"
    _assert_between(float(summary["Breadth_Momentum"]), -1.0, 1.0)
    _assert_bias(summary["Bias"])

    rscore = compute_regime_strength(out)
    _assert_between(float(rscore), 0.0, 1.0)


if __name__ == "__main__":
    test_cmv_sps_path()
    test_adv_dec_path()
    print("✅ smoke_breadth_momentum: all checks passed")

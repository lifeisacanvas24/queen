#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_all.py — end-to-end indicator orchestrator check
# ============================================================
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl
from queen.technicals.indicators.all import attach_all_indicators


def _mk_ohlcv(n: int = 120) -> pl.DataFrame:
    start = datetime(2025, 1, 1)
    end = start + timedelta(days=n - 1)

    # Polars compat: use positional args (start, end, every) + eager=True
    ts = pl.datetime_range(start, end, "1d", eager=True)

    # Build simple trending OHLCV + synthetic breadth
    base = np.linspace(100, 120, n) + np.random.normal(0, 0.5, n)
    high = base + np.random.uniform(0.2, 1.2, n)
    low = base - np.random.uniform(0.2, 1.2, n)
    close = base + np.random.normal(0, 0.3, n)
    open_ = close + np.random.normal(0, 0.3, n)
    vol = np.random.randint(1000, 5000, n)
    cmv = np.sin(np.linspace(0, 6, n)) + np.random.normal(0, 0.1, n)
    sps = np.cos(np.linspace(0, 6, n)) + np.random.normal(0, 0.1, n)

    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": open_.astype(float),
            "high": high.astype(float),
            "low": low.astype(float),
            "close": close.astype(float),
            "volume": vol.astype(float),
            "symbol": ["TEST"] * n,
            "CMV": cmv.astype(float),
            "SPS": sps.astype(float),
        }
    )


def test_attach_all():
    df = _mk_ohlcv()
    out = attach_all_indicators(df, context="intraday_15m")

    assert out.height == df.height
    assert "timestamp" in out.columns and "close" in out.columns

    # Core
    for c in ["ema_20", "ema_50", "rsi_14", "macd", "signal", "hist"]:
        assert c in out.columns, f"missing core column: {c}"

    # Keltner
    for c in ["KC_mid", "KC_upper", "KC_lower", "KC_norm"]:
        assert c in out.columns, f"missing keltner column: {c}"
    kc_norm = out["KC_norm"].drop_nulls()
    if kc_norm.len() > 0:
        assert kc_norm.min() >= 0.0 and kc_norm.max() <= 1.0

    # Momentum MACD
    for c in [
        "MACD_line",
        "MACD_signal",
        "MACD_hist",
        "MACD_norm",
        "MACD_slope",
        "MACD_crossover",
    ]:
        assert c in out.columns, f"missing momentum_macd column: {c}"
    mm_norm = out["MACD_norm"].drop_nulls()
    if mm_norm.len() > 0:
        assert mm_norm.min() >= -1.0 and mm_norm.max() <= 1.0

    # Chaikin
    for c in ["chaikin", "chaikin_norm", "chaikin_bias", "chaikin_flow"]:
        assert c in out.columns, f"missing chaikin column: {c}"

    # MFI
    for c in ["MFI", "MFI_norm", "MFI_Bias", "MFI_Flow"]:
        assert c in out.columns, f"missing MFI column: {c}"

    # Breadth (if present)
    for maybe in [
        "CMV_Breadth",
        "SPS_Breadth",
        "Breadth_Persistence",
        "Breadth_Bias",
        "Breadth_Momentum",
        "Breadth_Momentum_Bias",
    ]:
        if maybe in out.columns:
            assert out[maybe].len() == out.height

    print("✅ smoke_all: all checks passed")


if __name__ == "__main__":
    test_attach_all()

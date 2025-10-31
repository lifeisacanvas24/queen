#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_liquidity_trap_latency.py
# ------------------------------------------------------------
# Best-of-3 latency probe for liquidity_trap detector on ~2k rows.
# Run:  python -m queen.tests.smoke_liquidity_trap_latency
# ============================================================
from __future__ import annotations

import time

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.tactical_liquidity_trap import (
    detect_liquidity_trap,
)


def _make_df(n: int = 2000) -> pl.DataFrame:
    np.random.seed(123)
    t = np.linspace(0, 12, n)

    cmv = np.sin(t) + np.random.normal(0, 0.06, n)
    sps = np.clip(np.abs(np.sin(t * 0.8)) + np.random.normal(0, 0.03, n), 0, 1)
    mfi = 50 + 20 * np.sin(t + 1) + np.random.normal(0, 2.0, n)
    chaikin = np.cos(t) * 1200 + np.random.normal(0, 150, n)

    base = np.linspace(100, 120, n) + np.random.normal(0, 1.1, n)
    high = base + np.random.uniform(0.5, 1.8, n)
    low = base - np.random.uniform(0.5, 1.8, n)
    close = base + np.random.normal(0, 0.7, n)
    volume = np.random.randint(1_000, 6_000, n)

    return pl.DataFrame(
        {
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "CMV": cmv,
            "SPS": sps,
            "MFI": mfi,
            "Chaikin_Osc": chaikin,
        }
    )


def test_latency():
    df = _make_df(2000)

    # warm-up
    _ = detect_liquidity_trap(df)

    best_ms = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        _ = detect_liquidity_trap(df)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        best_ms = min(best_ms, dt_ms)

    print(f"⏱️ LiquidityTrap latency (N≈2000): {best_ms:.2f} ms")

    # Soft cap (very safe); adjust if you want stricter guardrails
    assert best_ms < 5.0, f"LiquidityTrap too slow: {best_ms:.2f} ms"
    print("✅ smoke_liquidity_trap_latency: completed")


if __name__ == "__main__":
    test_latency()

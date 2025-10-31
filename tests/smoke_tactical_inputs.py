#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_tactical_inputs.py
# ------------------------------------------------------------
# Verifies compute_tactical_inputs() returns all keys and sane ranges.
# Run:  python -m queen.tests.smoke_tactical_inputs
# ============================================================
from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.helpers import compute_tactical_inputs


def test():
    np.random.seed(42)
    n = 600

    base = np.linspace(100, 115, n) + np.random.normal(0, 0.9, n)
    high = base + np.random.uniform(0.3, 1.5, n)
    low = base - np.random.uniform(0.3, 1.5, n)
    close = base + np.random.normal(0, 0.4, n)
    volume = np.random.randint(1_000, 5_000, n)

    # Signals used by fallbacks/fusions
    cmv = np.sin(np.linspace(0, 6, n)) + np.random.normal(0, 0.05, n)
    sps = np.clip(
        np.abs(np.cos(np.linspace(0, 6, n))) + np.random.normal(0, 0.03, n), 0, 1
    )

    df = pl.DataFrame(
        {
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "CMV": cmv,
            "SPS": sps,
        }
    )

    out = compute_tactical_inputs(df, context="intraday_15m")
    # Required keys
    for k in ("RScore", "VolX", "LBX"):
        assert k in out, f"Missing key: {k}"

    # Sanity range checks (they’re normalized 0..1 by design)
    for k, v in out.items():
        assert 0.0 - 1e-6 <= float(v) <= 1.0 + 1e-6, f"{k} out of range: {v}"

    print(
        f"Tactical inputs → RScore={out['RScore']:.3f}, VolX={out['VolX']:.3f}, LBX={out['LBX']:.3f}"
    )
    print("✅ smoke_tactical_inputs: passed")


if __name__ == "__main__":
    test()

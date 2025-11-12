#!/usr/bin/env python3
# ============================================================
# queen/cli/validate_registry.py — v0.2
# Prints indicator/signal counts + sample callability checks
# Run:
#   python -m queen.cli.validate_registry
# ============================================================
from __future__ import annotations

import sys
import traceback

import numpy as np
import polars as pl
from queen.technicals.registry import get_indicator, list_indicators, list_signals

SAMPLE_INDICATORS = ["atr", "bollinger_bands", "supertrend", "adx_dmi", "lbx"]


def _make_df(n: int = 300) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    base = 100 + np.linspace(0, 3, n) + rng.normal(0, 0.5, n)
    high = base + rng.uniform(0.4, 1.6, n)
    low = base - rng.uniform(0.4, 1.6, n)
    close = base + rng.normal(0, 0.2, n)
    open_ = close + rng.normal(0, 0.15, n)
    vol = rng.integers(40_000, 120_000, n)
    return pl.DataFrame(
        {
            "timestamp": np.arange(n, dtype=np.int64),
            "open": open_.astype(float),
            "high": high.astype(float),
            "low": low.astype(float),
            "close": close.astype(float),
            "volume": vol.astype(np.int64),
        }
    )


def main() -> int:
    inds = list_indicators()
    sigs = list_signals()
    print(f"🧭 Indicators: {len(inds)}")
    print(f"🧭 Signals:    {len(sigs)}")

    df = _make_df()

    for name in SAMPLE_INDICATORS:
        ok = name in inds
        print(f"  • {name:<16} registered: {ok}")
        if not ok:
            continue
        try:
            fn = get_indicator(name)
            if name == "adx_dmi":
                out = fn(df, timeframe="15m")
                assert {"adx", "di_plus", "di_minus", "adx_trend"}.issubset(set(out.columns)), "adx_dmi cols missing"
            elif name == "bollinger_bands":
                mid, up, lo = fn(df)
                assert isinstance(mid, pl.Series), "bbands mid is not Series"
                assert mid.len() == df.height, "bbands mid wrong length"
            else:
                _ = fn(df)  # just ensure no exception
            print("     ↳ callable OK")
        except Exception:
            print(f"     ↳ ❌ failed:\n{traceback.format_exc()}")
            return 2

    print("✅ registry validate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

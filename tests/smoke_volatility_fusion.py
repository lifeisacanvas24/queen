import numpy as np
import polars as pl
from queen.technicals.indicators.volatility_fusion import (
    compute_volatility_fusion,
    summarize_volatility,
)


def _mk(n=200):
    rng = np.random.default_rng(1)
    base = np.linspace(100, 110, n) + rng.normal(0, 1.5, n)
    high = base + rng.uniform(0.5, 1.5, n)
    low = base - rng.uniform(0.5, 1.5, n)
    close = base + rng.normal(0, 0.8, n)
    return pl.DataFrame({"high": high, "low": low, "close": close})


def _is_float(dt):
    return dt in (pl.Float64, pl.Float32)


def test_fusion_outputs_and_ranges():
    df = _mk()
    fused = compute_volatility_fusion(df, timeframe="intraday_15m")
    for c in (
        "KC_mid",
        "KC_upper",
        "KC_lower",
        "KC_norm",
        "volx",
        "volx_norm",
        "volx_bias",
    ):
        assert c in fused.columns
    assert _is_float(fused["volx"].dtype)
    assert _is_float(fused["volx_norm"].dtype)
    mn, mx = float(fused["volx_norm"].min()), float(fused["volx_norm"].max())
    assert 0.0 <= mn <= 1.0 and 0.0 <= mx <= 1.0
    s = summarize_volatility(fused)
    for k in ("VolX_norm", "VolX_bias", "State"):
        assert k in s

# ============================================================
# queen/tests/smoke_chaikin.py
# ============================================================
import numpy as np
import polars as pl
from queen.technicals.indicators.volume_chaikin import (
    attach_chaikin,
    chaikin,
    summarize_chaikin,
)

EXPECTED = {"adl", "chaikin", "chaikin_norm", "chaikin_bias", "chaikin_flow"}


def _mk(n: int = 120) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    base = np.linspace(100, 110, n) + rng.normal(0, 0.8, n)
    high = base + rng.uniform(0.4, 1.8, n)
    low = base - rng.uniform(0.4, 1.8, n)
    close = base + rng.normal(0, 0.4, n)
    volume = rng.integers(1000, 5000, n)
    return pl.DataFrame({"high": high, "low": low, "close": close, "volume": volume})


def _is_float(dt) -> bool:
    return dt in (pl.Float64, pl.Float32)


def test_columns_and_types():
    df = _mk(120)
    out = chaikin(df, timeframe="intraday_15m")

    for c in EXPECTED:
        assert c in out.columns, f"missing column: {c}"

    assert _is_float(out["adl"].dtype)
    assert _is_float(out["chaikin"].dtype)
    assert _is_float(out["chaikin_norm"].dtype)
    assert out["chaikin_bias"].dtype == pl.Utf8
    assert out["chaikin_flow"].dtype == pl.Utf8

    chn = out["chaikin_norm"]
    # allow empty-slice in pathological synthetic cases
    if chn.len() > 0:
        mn = float(chn.min())
        mx = float(chn.max())
        assert 0.0 <= mn <= 1.0
        assert 0.0 <= mx <= 1.0


def test_attach_and_summary():
    df = _mk(90)
    attached = attach_chaikin(df, timeframe="intraday_15m")
    for c in EXPECTED:
        assert c in attached.columns

    summary = summarize_chaikin(attached)
    for k in ("Chaikin_Osc", "Bias", "Flow", "State"):
        assert k in summary

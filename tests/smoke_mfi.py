# ============================================================
# queen/tests/smoke_mfi.py
# ============================================================
import numpy as np
import polars as pl
from queen.technicals.indicators.volume_mfi import attach_mfi, mfi, summarize_mfi


def _mk(n=150) -> pl.DataFrame:
    rng = np.random.default_rng(123)
    base = np.linspace(100, 110, n) + rng.normal(0, 0.7, n)
    high = base + rng.uniform(0.3, 1.6, n)
    low = base - rng.uniform(0.3, 1.6, n)
    close = base + rng.normal(0, 0.4, n)
    volume = rng.integers(1_000, 6_000, n)
    return pl.DataFrame({"high": high, "low": low, "close": close, "volume": volume})


def _is_float(dt) -> bool:
    return dt in (pl.Float64, pl.Float32)


def test_columns_and_ranges():
    df = _mk()
    out = mfi(df, timeframe="intraday_15m")
    for c in ("mfi", "mfi_norm", "mfi_bias", "mfi_flow"):
        assert c in out.columns
    assert _is_float(out["mfi"].dtype)
    assert _is_float(out["mfi_norm"].dtype)
    assert out["mfi_bias"].dtype == pl.Utf8
    assert out["mfi_flow"].dtype == pl.Utf8
    mn, mx = float(out["mfi_norm"].min()), float(out["mfi_norm"].max())
    assert 0.0 <= mn <= 1.0 and 0.0 <= mx <= 1.0


def test_attach_and_summary():
    df = _mk(80)
    attached = attach_mfi(df, timeframe="intraday_15m")
    for c in ("mfi", "mfi_norm", "mfi_bias", "mfi_flow"):
        assert c in attached.columns
    summary = summarize_mfi(attached)
    for k in ("MFI", "Bias", "Flow", "State"):
        assert k in summary

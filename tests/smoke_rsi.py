import numpy as np
import polars as pl
from queen.technicals.indicators.rsi import rsi


def _mk(n=120):
    rng = np.random.default_rng(0)
    close = 100 + np.sin(np.linspace(0, 6, n)) + rng.normal(0, 0.3, n)
    return pl.DataFrame({"close": close})


def test_rsi_series():
    df = _mk()
    out = rsi(df, length=14)
    assert isinstance(out, pl.Series)
    assert out.name == "rsi"
    assert out.len() == df.height
    assert out.dtype in (pl.Float64, pl.Float32)

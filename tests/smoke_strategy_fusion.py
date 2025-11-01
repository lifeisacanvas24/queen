#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_strategy_fusion.py
# ============================================================
from __future__ import annotations
import polars as pl
from queen.strategies.fusion import run_strategy


def _mk(n: int = 60, sps: float = 0.65) -> pl.DataFrame:
    df = pl.DataFrame(
        {
            "close": pl.Series([float(i) for i in range(n)]),
            "high": pl.Series([float(i + 1) for i in range(n)]),
            "low": pl.Series([float(i - 1) for i in range(n)]),
            "volume": pl.Series([1000] * n),  # <- Series (no Exprs in constructor)
        }
    )
    idx = pl.arange(0, n, eager=True)
    return df.with_columns(
        [
            pl.lit(float(sps)).alias("SPS"),
            pl.when(idx % 2 == 0)
            .then(pl.lit("TREND"))
            .otherwise(pl.lit("RANGE"))
            .alias("Regime_State"),
            pl.lit(1.12).alias("ATR_Ratio"),
        ]
    )


def test():
    frames = {
        "intraday_15m": _mk(120, 0.68),
        "hourly_1h": _mk(180, 0.62),
        "daily": _mk(200, 0.58),
    }
    out = run_strategy("DEMO", frames)
    assert "per_tf" in out and "fused" in out and isinstance(out["per_tf"], dict)

    for tf, row in out["per_tf"].items():
        for k in ("strategy_score", "bias", "entry_ok", "exit_ok", "risk_band"):
            assert k in row
        assert 0.0 <= row["strategy_score"] <= 1.0
        assert row["bias"] in ("bullish", "neutral", "bearish")
        assert row["risk_band"] in ("low", "medium", "high")

    fused = out["fused"]
    for k in ("score", "bias", "entry_ok", "exit_ok", "risk_band"):
        assert k in fused
    assert 0.0 <= fused["score"] <= 1.0
    assert fused["bias"] in ("bullish", "neutral", "bearish")
    assert fused["risk_band"] in ("low", "medium", "high")

    print("✅ smoke_strategy_fusion: passed")


if __name__ == "__main__":
    test()

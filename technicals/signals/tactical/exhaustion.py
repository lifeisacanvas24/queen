# ============================================================
# queen/technicals/signals/tactical/exhaustion.py
# ------------------------------------------------------------
# ⚡ Tactical Exhaustion Bar Detector (Phase 4.7 • Polars-native)
# Detects exhaustion candles via volume spikes, wick dominance,
# and CMV momentum collapse/flip.
# ============================================================
from __future__ import annotations

import polars as pl

__all__ = ["detect_exhaustion_bars"]

# Optional: make discoverable by our registry (EXPORTS-first rule)
EXPORTS = {"exhaustion": lambda df, **kw: detect_exhaustion_bars(df, **kw)}


def detect_exhaustion_bars(
    df: pl.DataFrame,
    *,
    cmv_col: str = "CMV",
    volume_col: str = "volume",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    lookback_vol: int = 20,
    wick_threshold: float = 0.6,
    cmv_drop: float = 0.4,
) -> pl.DataFrame:
    """Add:
        • Volume_Spike  (× of rolling mean volume)
        • Wick_Ratio    ((range - body) / (body + eps), clamped ≥ 0)
        • CMV_Delta     (first difference of CMV)
        • Exhaustion_Signal  (🟥/🟩/➡️)

    Works across older/newer Polars APIs (no Expr.clip usage).
    """
    # ---- Safety ---------------------------------------------------------
    for col in (cmv_col, volume_col, high_col, low_col, close_col):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # ---- Volume spike vs rolling mean ----------------------------------
    vol_expr = pl.col(volume_col).fill_null(0)
    try:
        vol_ma_expr = vol_expr.rolling_mean(window_size=lookback_vol)
    except TypeError:
        vol_ma_expr = vol_expr.rolling_mean(window=lookback_vol)

    vol_spike_expr = (
        pl.when(vol_ma_expr != 0)
        .then(vol_expr / vol_ma_expr)
        .otherwise(1.0)
        .alias("Volume_Spike")
    )

    # ---- Wick ratio: (range - body) / (body + eps), clamped to >= 0 ----
    hi, lo, cl = pl.col(high_col), pl.col(low_col), pl.col(close_col)
    rng = (hi - lo).abs()
    mid = (hi + lo) / 2
    body = (cl - mid).abs()

    ratio_expr = (rng - body) / (body + 1e-6)
    # version-agnostic clamp (no .clip)
    wick_ratio_expr = (
        pl.when(ratio_expr < 0.0).then(0.0).otherwise(ratio_expr).alias("Wick_Ratio")
    )

    # ---- CMV momentum delta --------------------------------------------
    cmv = pl.col(cmv_col).fill_null(0.0)
    cmv_delta_expr = cmv.diff().fill_null(0.0).alias("CMV_Delta")

    # ---- Materialize derived columns once -------------------------------
    out = df.with_columns([vol_spike_expr, wick_ratio_expr, cmv_delta_expr])

    # ---- Vectorized signal logic ---------------------------------------
    vol_ok = pl.col("Volume_Spike") >= 1.5
    wick_ok = pl.col("Wick_Ratio") >= wick_threshold
    drop_ok = pl.col("CMV_Delta").abs() >= cmv_drop

    bear = (cmv > 0) & (pl.col("CMV_Delta") < 0) & vol_ok & wick_ok & drop_ok
    bull = (cmv < 0) & (pl.col("CMV_Delta") > 0) & vol_ok & wick_ok & drop_ok

    signal_expr = (
        pl.when(bear)
        .then(pl.lit("🟥 Bearish Exhaustion"))
        .when(bull)
        .then(pl.lit("🟩 Bullish Exhaustion"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias("Exhaustion_Signal")
    )

    return out.with_columns(signal_expr)


# ----------------------------------------------------------------------
# 🧪 Stand-alone quick check
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    n = 120
    df = pl.DataFrame(
        {
            "high": np.random.uniform(100, 110, n),
            "low": np.random.uniform(95, 105, n),
            "close": np.random.uniform(97, 108, n),
            "volume": np.random.randint(1_000, 5_000, n),
            "CMV": np.random.uniform(-1, 1, n),
        }
    )
    out = detect_exhaustion_bars(df)
    print(
        out.select(
            ["Volume_Spike", "Wick_Ratio", "CMV_Delta", "Exhaustion_Signal"]
        ).tail(8)
    )

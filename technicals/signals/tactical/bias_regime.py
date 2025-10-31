# ============================================================
# queen/technicals/signals/tactical/bias_regime.py
# ------------------------------------------------------------
# ⚙️ Tactical Bias Regime Engine (Trend / Range / Volatile / Neutral)
# - 100% Polars
# - Vectorized; no Python loops for features
# ============================================================

from __future__ import annotations

import polars as pl


def compute_bias_regime(
    df: pl.DataFrame,
    *,
    cmv_col: str = "CMV",
    adx_col: str = "ADX",
    close_col: str = "close",
    window_atr: int = 14,
    window_flip: int = 10,
) -> pl.DataFrame:
    """Classify regime using ADX strength, CMV direction, ATR expansion, and flip density.

    Adds:
      - ATR           : rolling ATR proxy via TR rolling mean
      - ATR_Ratio     : ATR / rolling(ATR)
      - CMV_Flips     : rolling count of sign flips over window_flip
      - Regime_State  : TREND / RANGE / VOLATILE / NEUTRAL
      - Regime_Emoji  : 🟢 / ⚪ / 🟠 / ⚫ with label
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    required = {cmv_col, adx_col, close_col, "high", "low"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"[bias_regime] Missing required columns: {sorted(missing)}")

    out = df

    # --- 1) TR then ATR (separate steps so ATR exists before ATR_Ratio) ---
    out = out.with_columns(
        (pl.col("high") - pl.col("low")).abs().fill_null(0.0).alias("TR")
    )
    out = out.with_columns(pl.col("TR").rolling_mean(window_atr).alias("ATR"))
    out = out.with_columns(
        (pl.col("ATR") / pl.col("ATR").rolling_mean(window_atr))
        .fill_nan(1.0)
        .fill_null(1.0)
        .alias("ATR_Ratio")
    )

    # --- 2) CMV flip density over window_flip (use staged columns) ---
    out = out.with_columns(
        pl.when(pl.col(cmv_col) > 0)
        .then(1)
        .when(pl.col(cmv_col) < 0)
        .then(-1)
        .otherwise(0)
        .alias("_cmv_sign")
    )
    out = out.with_columns(
        (pl.col("_cmv_sign") != pl.col("_cmv_sign").shift(1))
        .cast(pl.Int8)
        .alias("_cmv_flip1")
    )
    out = out.with_columns(
        pl.col("_cmv_flip1").rolling_sum(window_flip).fill_null(0).alias("CMV_Flips")
    )

    # --- 3) Regime rules (vectorized) ---
    adx = pl.col(adx_col).cast(pl.Float64)
    cmv_abs = pl.col(cmv_col).cast(pl.Float64).abs()
    flips = pl.col("CMV_Flips").cast(pl.Float64)
    atr_r = pl.col("ATR_Ratio").cast(pl.Float64)

    is_trend = (adx > 25.0) & (cmv_abs > 0.5)
    is_range = (adx < 20.0) & (atr_r < 1.10)
    is_volatile = (atr_r > 1.30) | (flips > (window_flip / 2.0))

    out = out.with_columns(
        pl.when(is_trend)
        .then(pl.lit("TREND"))
        .when(is_range)
        .then(pl.lit("RANGE"))
        .when(is_volatile)
        .then(pl.lit("VOLATILE"))
        .otherwise(pl.lit("NEUTRAL"))
        .alias("Regime_State")
    )

    out = out.with_columns(
        pl.when(pl.col("Regime_State") == "TREND")
        .then(pl.lit("🟢 Trend"))
        .when(pl.col("Regime_State") == "RANGE")
        .then(pl.lit("⚪ Range"))
        .when(pl.col("Regime_State") == "VOLATILE")
        .then(pl.lit("🟠 Volatile"))
        .otherwise(pl.lit("⚫ Neutral"))
        .alias("Regime_Emoji")
    )

    # Scratch cleanup
    return out.drop(["_cmv_sign", "_cmv_flip1"])


# ── Optional local smoke ─────────────────────────────────────
if __name__ == "__main__":
    import numpy as np

    n = 200
    df = pl.DataFrame(
        {
            "high": np.random.uniform(100, 110, n),
            "low": np.random.uniform(95, 105, n),
            "close": np.random.uniform(97, 108, n),
            "ADX": np.random.uniform(10, 40, n),
            "CMV": np.random.uniform(-1, 1, n),
        }
    )
    out = compute_bias_regime(df)
    print(
        out.select(
            ["ATR", "ATR_Ratio", "CMV_Flips", "Regime_State", "Regime_Emoji"]
        ).tail(8)
    )

# ------------------------------------------------------------
# 📦 Registry export (for queen.cli.list_signals)
# ------------------------------------------------------------
EXPORTS = {
    "bias_regime": compute_bias_regime,
}

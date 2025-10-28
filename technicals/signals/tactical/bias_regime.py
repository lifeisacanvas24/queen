# ============================================================
# queen/technicals/signals/tactical/bias_regime.py
# ------------------------------------------------------------
# ⚙️ Tactical Bias Regime Engine (Phase 4.6)
# Classifies Trend / Range / Volatile conditions using CMV,
# ADX, and ATR signals over rolling windows.
# ============================================================

import numpy as np
import polars as pl


# ============================================================
# 🧠 Core Computation
# ============================================================
def compute_bias_regime(
    df: pl.DataFrame,
    cmv_col: str = "CMV",
    adx_col: str = "ADX",
    close_col: str = "close",
    window_atr: int = 14,
    window_flip: int = 10,
) -> pl.DataFrame:
    """Detects dominant market regime (Trend / Range / Volatile / Neutral).

    Adds columns:
        ATR, ATR_Ratio, CMV_Flips, Regime_State, Regime_Emoji
    """
    df = df.clone()

    # ✅ Sanity check
    required = [cmv_col, adx_col, close_col, "high", "low"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # --- True Range (TR) and ATR ---
    df = df.with_columns(
        ((pl.col("high") - pl.col("low")).abs()).fill_null(0).alias("TR")
    )
    df = df.with_columns(pl.col("TR").rolling_mean(window_atr).alias("ATR"))

    # --- ATR ratio relative to rolling mean ---
    atr_ratio = df["ATR"] / df["ATR"].rolling_mean(window_atr)
    df = df.with_columns(pl.Series("ATR_Ratio", atr_ratio.fill_nan(1.0)))

    # --- Count CMV flips over last N bars ---
    cmv = df[cmv_col].fill_null(0).to_numpy()
    flips = np.zeros_like(cmv)
    for i in range(window_flip, len(cmv)):
        segment = cmv[i - window_flip : i]
        flips[i] = np.sum(np.diff(np.sign(segment)) != 0)
    df = df.with_columns(pl.Series("CMV_Flips", flips))

    # --- Helper for numeric safety ---
    def safe_num(x, default=0.0):
        return (
            float(x)
            if isinstance(x, (int, float)) and not (x is None or np.isnan(x))
            else default
        )

    # --- Regime classification ---
    regime = []
    for i in range(len(df)):
        adx_val = safe_num(df[adx_col][i])
        cmv_val = safe_num(cmv[i])
        atr_ratio_val = safe_num(atr_ratio[i], 1.0)
        flips_val = safe_num(flips[i])

        if adx_val > 25 and abs(cmv_val) > 0.5:
            regime.append("TREND")
        elif adx_val < 20 and atr_ratio_val < 1.1:
            regime.append("RANGE")
        elif atr_ratio_val > 1.3 or flips_val > window_flip / 2:
            regime.append("VOLATILE")
        else:
            regime.append("NEUTRAL")

    emoji_map = {
        "TREND": "🟢 Trend",
        "RANGE": "⚪ Range",
        "VOLATILE": "🟠 Volatile",
        "NEUTRAL": "⚫ Neutral",
    }

    df = df.with_columns(
        [
            pl.Series("Regime_State", regime),
            pl.Series("Regime_Emoji", [emoji_map[r] for r in regime]),
        ]
    )

    return df


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    n = 100
    np.random.seed(42)
    data = {
        "high": np.random.uniform(100, 110, n),
        "low": np.random.uniform(95, 105, n),
        "close": np.random.uniform(97, 108, n),
        "ADX": np.random.uniform(10, 40, n),
        "CMV": np.random.uniform(-1, 1, n),
    }
    df = pl.DataFrame(data)
    out = compute_bias_regime(df)
    print(
        out.select(
            ["ADX", "CMV", "ATR", "ATR_Ratio", "CMV_Flips", "Regime_Emoji"]
        ).tail(10)
    )

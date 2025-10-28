# ============================================================
# queen/technicals/signals/tactical/divergence.py
# ------------------------------------------------------------
# ⚙️ Volume–Momentum Divergence Engine
# Detects bullish/bearish divergences between price, CMV, and volume
# ============================================================

import numpy as np
import polars as pl


# ============================================================
# 🧠 Core Divergence Detector
# ============================================================
def detect_divergence(
    df: pl.DataFrame,
    price_col: str = "close",
    cmv_col: str = "CMV",
    lookback: int = 5,
    threshold: float = 0.02,
) -> pl.DataFrame:
    """Detects CMV–Price divergences (momentum disagreement zones).
    Flags potential reversal signals:
      🟥 Bearish Divergence (Price up, CMV down)
      🟩 Bullish Divergence (Price down, CMV up)
    """
    if price_col not in df.columns or cmv_col not in df.columns:
        print("⚠️ [Divergence] Skipped: Missing price or CMV columns.")
        return df.with_columns(pl.lit("➡️ Skipped").alias("Divergence_Signal"))

    price = np.array(df[price_col])
    cmv = np.array(df[cmv_col])
    div_signal = np.full(len(price), "➡️ Stable", dtype=object)

    for i in range(lookback, len(price)):
        price_slope = price[i] - price[i - lookback]
        cmv_slope = cmv[i] - cmv[i - lookback]

        # Price up but CMV down → Bearish Divergence
        if price_slope > threshold and cmv_slope < -threshold:
            div_signal[i] = "🟥 Bearish Divergence (Momentum Weakening)"
        # Price down but CMV up → Bullish Divergence
        elif price_slope < -threshold and cmv_slope > threshold:
            div_signal[i] = "🟩 Bullish Divergence (Momentum Building)"

    df = df.with_columns(pl.Series("Divergence_Signal", div_signal))
    return df


# ============================================================
# 🔍 Summary Utility
# ============================================================
def summarize_divergence(df: pl.DataFrame) -> str:
    bull = (df["Divergence_Score"] > 0).sum()
    bear = (df["Divergence_Score"] < 0).sum()
    last_flag = str(df["Divergence_Flag"].drop_nulls()[-1])
    return f"Bullish: {bull} | Bearish: {bear} | Last: {last_flag}"


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    np.random.seed(42)
    n = 200
    x = np.linspace(0, 6, n)
    price = np.sin(x) + 0.1 * np.random.randn(n)
    cmv = np.sin(x + 0.3) * 0.8 + 0.05 * np.random.randn(n)
    mfi = 50 + 10 * np.cos(x)
    chaikin = np.sin(x * 1.2) * 1000

    df = pl.DataFrame({"close": price, "CMV": cmv, "MFI": mfi, "Chaikin_Osc": chaikin})

    df = detect_divergence(df)
    print("✅ Divergence Diagnostic →", summarize_divergence(df))

    plt.figure(figsize=(10, 6))
    plt.plot(df["close"], label="Price", color="white")
    plt.plot(df["CMV"], label="CMV", color="cyan")
    plt.title("Volume–Momentum Divergence Detection")
    bull_idx = np.where(df["Divergence_Score"] > 0)[0]
    bear_idx = np.where(df["Divergence_Score"] < 0)[0]
    plt.scatter(
        bull_idx, df["close"][bull_idx], color="green", label="Bullish Div", zorder=5
    )
    plt.scatter(
        bear_idx, df["close"][bear_idx], color="red", label="Bearish Div", zorder=5
    )
    plt.legend()
    plt.show()

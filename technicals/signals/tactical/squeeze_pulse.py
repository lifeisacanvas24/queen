# ============================================================
# quant/signals/tactical/tactical_squeeze_pulse.py
# ------------------------------------------------------------
# ⚙️ Volume–Volatility Compression Engine (Squeeze Pulse)
# Detects squeeze buildup (low volatility + high SPS/CMV) and
# release events when volatility expands.
# ============================================================

import numpy as np
import polars as pl


# ============================================================
# 🧠 Core Detection Logic
# ============================================================
def detect_squeeze_pulse(
    df: pl.DataFrame,
    bb_upper_col: str = "bb_upper",
    bb_lower_col: str = "bb_lower",
    keltner_upper_col: str = "Keltner_Upper",
    keltner_lower_col: str = "Keltner_Lower",
    atr_col: str = "atr_14",
    sps_col: str = "SPS",
    cmv_col: str = "CMV",
    squeeze_threshold: float = 0.015
) -> pl.DataFrame:
    """Detects Bollinger–Keltner squeeze compression and expansion pulses.
    Flags:
        ⚡ Squeeze Ready (volatility compression)
        🚀 Squeeze Release (volatility expansion)
    """
    required_cols = [bb_upper_col, bb_lower_col, keltner_upper_col, keltner_lower_col]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        print(f"⚠️ [Squeeze] Skipped: Missing {', '.join(missing)} columns.")
        return df.with_columns(pl.lit("➡️ Skipped").alias("Squeeze_Signal"))

    bb_upper = np.array(df[bb_upper_col])
    bb_lower = np.array(df[bb_lower_col])
    kel_upper = np.array(df[keltner_upper_col])
    kel_lower = np.array(df[keltner_lower_col])

    squeeze = np.full(len(bb_upper), "➡️ Stable", dtype=object)

    for i in range(len(bb_upper)):
        bb_width = bb_upper[i] - bb_lower[i]
        kel_width = kel_upper[i] - kel_lower[i]

        # ⚡ Compression: BB inside Keltner
        if bb_upper[i] < kel_upper[i] and bb_lower[i] > kel_lower[i]:
            squeeze[i] = "⚡ Squeeze Ready"
        # 🚀 Expansion: BB outside Keltner after compression
        elif bb_upper[i] > kel_upper[i] and bb_lower[i] < kel_lower[i] and bb_width > kel_width * (1 + squeeze_threshold):
            squeeze[i] = "🚀 Squeeze Release"

    df = df.with_columns(pl.Series("Squeeze_Signal", squeeze))
    return df

# ============================================================
# 🔍 Diagnostic Summary
# ============================================================
def summarize_squeeze(df: pl.DataFrame) -> str:
    ready = (df["Squeeze_Flag"] == "⚡ Squeeze Ready").sum()
    release = (df["Squeeze_Flag"] == "🚀 Squeeze Release").sum()
    last_flag = str(df["Squeeze_Flag"].drop_nulls()[-1])
    return f"Squeeze Ready: {ready} | Releases: {release} | Last: {last_flag}"


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    np.random.seed(42)
    n = 200
    base = np.linspace(100, 120, n)
    noise = np.random.normal(0, 0.5, n)
    price = base + noise
    bb_upper = price + np.random.uniform(1.5, 2.5, n)
    bb_lower = price - np.random.uniform(1.5, 2.5, n)
    keltner_upper = price + np.random.uniform(1.0, 1.5, n)
    keltner_lower = price - np.random.uniform(1.0, 1.5, n)
    atr = np.abs(np.random.normal(1.5, 0.4, n))
    sps = np.random.uniform(0.5, 1.0, n)
    cmv = np.sin(np.linspace(0, 6, n))

    df = pl.DataFrame({
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "keltner_upper": keltner_upper,
        "keltner_lower": keltner_lower,
        "atr_14": atr,
        "SPS": sps,
        "CMV_smooth": cmv
    })

    df = detect_squeeze_pulse(df)
    print("✅ Squeeze Pulse Diagnostic →", summarize_squeeze(df))

    plt.figure(figsize=(10, 5))
    plt.plot(df["atr_14"], label="ATR")
    plt.plot(df["Squeeze_Score"], label="Squeeze Score", color="orange")
    plt.title("Squeeze Pulse Detection")
    plt.legend()
    plt.show()

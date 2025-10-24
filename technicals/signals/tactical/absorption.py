# ============================================================
# quant/signals/tactical/tactical_absorption.py
# ------------------------------------------------------------
# ⚙️ Smart Money Absorption Engine
# Detects accumulation/distribution via volume absorption behavior
# ============================================================

import numpy as np
import polars as pl


# ============================================================
# 🧠 Core Absorption Detection
# ============================================================
def detect_absorption_zones(
    df: pl.DataFrame,
    cmv_col: str = "CMV",
    volume_col: str = "volume",
    mfi_col: str = "MFI",
    chaikin_col: str = "Chaikin_Osc",
    lookback: int = 5,
    absorption_threshold: float = 0.85
) -> pl.DataFrame:
    """Detect potential absorption candles (smart money defending levels).
    Uses CMV, volume, MFI, and Chaikin oscillator relationships.
    """
    if cmv_col not in df.columns or volume_col not in df.columns:
        print("⚠️ [Absorption] Skipped: Missing CMV or volume columns.")
        return df.with_columns(pl.lit("➡️ Skipped").alias("Absorption_Zone"))

    cmv = np.array(df[cmv_col])
    volume = np.array(df[volume_col])
    mfi = np.array(df[mfi_col]) if mfi_col in df.columns else np.zeros_like(cmv)
    chaikin = np.array(df[chaikin_col]) if chaikin_col in df.columns else np.zeros_like(cmv)

    absorption = np.full(len(cmv), "➡️ Stable", dtype=object)

    for i in range(lookback, len(cmv)):
        # Hidden accumulation: CMV flat, volume rising, MFI improving, Chaikin positive
        hidden_buy = abs(cmv[i] - cmv[i - 1]) < 0.05 and volume[i] > volume[i - 1] and mfi[i] > mfi[i - 1] and chaikin[i] > 0
        # Hidden distribution: CMV flat, volume rising, MFI dropping, Chaikin negative
        hidden_sell = abs(cmv[i] - cmv[i - 1]) < 0.05 and volume[i] > volume[i - 1] and mfi[i] < mfi[i - 1] and chaikin[i] < 0

        if hidden_buy:
            absorption[i] = "🟩 Accumulation Zone (Smart Money Buy Defense)"
        elif hidden_sell:
            absorption[i] = "🟥 Distribution Zone (Smart Money Sell Defense)"

    df = df.with_columns(pl.Series("Absorption_Zone", absorption))
    return df


# ============================================================
# 🔍 Diagnostic Summary
# ============================================================
def summarize_absorption(df: pl.DataFrame) -> str:
    """Generate quick summary for absorption detection."""
    acc_count = (df["Absorption_Score"] > 0).sum()
    dist_count = (df["Absorption_Score"] < 0).sum()
    last_flag = str(df["Absorption_Flag"].drop_nulls()[-1])
    return f"Accumulations: {acc_count} | Distributions: {dist_count} | Last: {last_flag}"


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    np.random.seed(42)
    n = 200
    cmv = np.sin(np.linspace(0, 6, n)) * 0.1  # mostly flat
    volume = np.random.randint(1000, 5000, n)
    volume[100:110] *= 2  # spike region
    chaikin = np.random.normal(0, 500, n)
    chaikin[100:110] += 1500  # surge during accumulation
    mfi = np.linspace(40, 80, n) + np.random.normal(0, 5, n)

    df = pl.DataFrame({
        "CMV": cmv,
        "volume": volume,
        "Chaikin_Osc": chaikin,
        "MFI": mfi
    })

    df = detect_absorption_zones(df)
    print("✅ Absorption Diagnostic →", summarize_absorption(df))

    plt.figure(figsize=(10, 6))
    plt.plot(df["volume"], label="Volume", alpha=0.4)
    plt.plot(df["MFI"], label="MFI", color="orange")
    plt.title("Smart Money Absorption Zones")
    acc_idx = np.where(df["Absorption_Score"] > 0)[0]
    dist_idx = np.where(df["Absorption_Score"] < 0)[0]
    plt.scatter(acc_idx, df["volume"][acc_idx], color="green", label="Accumulation", zorder=5)
    plt.scatter(dist_idx, df["volume"][dist_idx], color="red", label="Distribution", zorder=5)
    plt.legend()
    plt.show()

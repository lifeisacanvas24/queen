# ============================================================
# quant/signals/tactical/tactical_liquidity_trap.py
# ------------------------------------------------------------
# ⚙️ Liquidity Trap & Absorption Candle Detection Engine
# Detects false breakouts and smart money absorption events
# ============================================================

import numpy as np
import polars as pl


# ============================================================
# 🧠 Core Detection Logic
# ============================================================
def detect_liquidity_trap(
    df: pl.DataFrame,
    cmv_col: str = "CMV",
    sps_col: str = "SPS",
    mfi_col: str = "MFI",
    chaikin_col: str = "Chaikin_Osc",
    threshold_sps: float = 0.85,
    vol_spike: float = 1.5,
    lookback: int = 5
) -> pl.DataFrame:
    """Detect potential liquidity traps and absorption candles using CMV, SPS, and volume-based metrics."""
    if cmv_col not in df.columns or sps_col not in df.columns:
        print("⚠️ [Liquidity Trap] Skipped: Missing CMV or SPS columns.")
        df = df.with_columns(pl.lit("➡️ Skipped").alias("Liquidity_Trap"))
        return df

    cmv = np.array(df[cmv_col])
    sps = np.array(df[sps_col])
    mfi = np.array(df[mfi_col]) if mfi_col in df.columns else np.zeros_like(cmv)
    chaikin = np.array(df[chaikin_col]) if chaikin_col in df.columns else np.zeros_like(cmv)

    traps = np.full(len(cmv), "➡️ Stable", dtype=object)

    for i in range(lookback, len(cmv)):
        cmv_flip = (cmv[i - 1] > 0 and cmv[i] < 0) or (cmv[i - 1] < 0 and cmv[i] > 0)
        sps_exhausted = sps[i - 1] > threshold_sps and sps[i] < sps[i - 1]
        vol_absorb = (chaikin[i] < 0 and mfi[i] < mfi[i - 1]) or (chaikin[i] > 0 and mfi[i] < 40)

        if cmv_flip and sps_exhausted and vol_absorb:
            traps[i] = "🟥 Bear Trap → Short Squeeze Setup" if cmv[i] < 0 else "🟩 Bull Trap → Long Liquidation Risk"

    df = df.with_columns(pl.Series("Liquidity_Trap", traps))
    return df


# ============================================================
# 🔍 Diagnostic Summary
# ============================================================
def summarize_liquidity_traps(df: pl.DataFrame) -> str:
    """Summarize liquidity traps found in DataFrame."""
    total_traps = (df["Liquidity_Trap"] != "➡️ Stable").sum()
    if total_traps == 0:
        return "No liquidity traps detected ⚪"
    last_trap = str(df["Liquidity_Trap"].drop_nulls()[-1])
    return f"Detected {total_traps} liquidity trap events | Last → {last_trap}"


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    np.random.seed(42)
    n = 200
    t = np.linspace(0, 6, n)
    cmv = np.sin(t) + np.random.normal(0, 0.15, n)
    sps = np.abs(np.sin(t)) * 0.9 + np.random.normal(0, 0.05, n)
    mfi = 50 + 20 * np.sin(t + 1)
    chaikin = np.cos(t) * 1000 + np.random.normal(0, 100, n)

    df = pl.DataFrame({
        "CMV": cmv,
        "SPS": sps,
        "MFI": mfi,
        "Chaikin_Osc": chaikin
    })

    df = detect_liquidity_traps(df)
    print("✅ Liquidity Trap Diagnostic →", summarize_liquidity_traps(df))

    plt.figure(figsize=(10, 6))
    plt.plot(df["CMV"], label="CMV", color="deepskyblue")
    plt.plot(df["SPS"], label="SPS", color="orange")
    plt.title("Liquidity Trap & Absorption Detection")
    trap_indices = np.where(df["Liquidity_Trap"] != "➡️ Stable")[0]
    for idx in trap_indices:
        plt.axvline(idx, color="red", linestyle="--", alpha=0.5)
    plt.legend()
    plt.show()

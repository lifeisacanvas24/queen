# ============================================================
# quant/signals/templates/indicator_template.py
# ------------------------------------------------------------
# 🧱 Headless Indicator Template — Quant-Core v4.x Standard
# ------------------------------------------------------------
# All indicators should follow this design pattern.
# ------------------------------------------------------------
# ✅ Config-driven (via indicators.json)
# ✅ NaN-safe computations
# ✅ Diagnostics through _log_indicator_warning()
# ✅ summarize() returns structured dicts
# ✅ Headless by default — optional visual debug block
# ============================================================

import numpy as np
import polars as pl
from quant.config import get_indicator_params
from quant.signals.utils_indicator_health import _log_indicator_warning


# ============================================================
# 🧠 Core Compute Function (Template)
# ============================================================
def compute_indicator(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Generic compute pattern for headless indicators.

    Steps:
        1. Fetch parameters from indicators.json.
        2. Validate required columns.
        3. Compute core metrics (NaN-safe).
        4. Return df with appended result columns.
    """
    # Load config section dynamically by name
    params = get_indicator_params("TEMPLATE_INDICATOR", context)
    lookback = params.get("lookback", 14)

    df = df.clone()

    # Example column requirement
    required_cols = ["close"]
    for col in required_cols:
        if col not in df.columns:
            _log_indicator_warning("TEMPLATE_INDICATOR", context, f"Missing '{col}' column — skipping computation.")
            return df

    # Example numeric conversion
    close = df["close"].to_numpy().astype(float, copy=False)
    if len(close) < lookback:
        _log_indicator_warning("TEMPLATE_INDICATOR", context, f"Insufficient data (<{lookback}) for computation.")
        return df.with_columns([pl.Series("template_value", np.zeros_like(close))])

    # --------------------------------------------------------
    # 🧩 Replace this section with your actual computation
    # --------------------------------------------------------
    # Example: rolling mean normalized output
    values = np.convolve(close, np.ones(lookback) / lookback, mode="same")
    values = np.nan_to_num(values, nan=0.0)
    norm = (values - np.min(values)) / (np.ptp(values) if np.ptp(values) != 0 else 1.0)

    return df.with_columns([
        pl.Series("template_value", values),
        pl.Series("template_norm", norm),
    ])


# ============================================================
# 📊 Summarizer
# ============================================================
def summarize_indicator(df: pl.DataFrame) -> dict:
    """Return lightweight summary stats (headless)."""
    if df.height == 0 or "template_value" not in df.columns:
        return {"status": "empty"}
    last_val = float(df["template_value"][-1])
    bias = "bullish" if last_val > 0 else "bearish"
    return {"value": last_val, "bias": bias}


# ============================================================
# 🧪 Local Dev Diagnostic (Headless by Default)
# ============================================================
if __name__ == "__main__":
    VISUAL_DEBUG = False

    n = 200
    np.random.seed(42)
    close = 100 + np.sin(np.linspace(0, 6 * np.pi, n)) * 5 + np.random.normal(0, 0.3, n)
    df = pl.DataFrame({"close": close})
    df = compute_indicator(df, context="default")

    summary = summarize_indicator(df)
    print("✅ Template Diagnostic →", summary)

    if VISUAL_DEBUG:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 5))
        plt.plot(df["close"], label="Close", alpha=0.4)
        plt.plot(df["template_value"], label="Template Value", color="gold")
        plt.title("Indicator Template Diagnostic")
        plt.legend()
        plt.show()

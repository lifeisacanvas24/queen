# ============================================================
# queen/technicals/indicators/breadth_cumulative.py
# ------------------------------------------------------------
# ⚙️ Cumulative Breadth & Persistence Engine (Headless, Polars)
# Settings-driven via indicator_policy.params_for
# ============================================================

from __future__ import annotations

import math

import polars as pl

# Canonical settings owner
from queen.settings.indicator_policy import params_for as _params_for


# ------------------------------------------------------------
# 🧠 Core Breadth Computation
# ------------------------------------------------------------


def compute_breadth(
    df: pl.DataFrame,
    context: str | None = None,  # kept for API uniformity
    **kwargs,
) -> pl.DataFrame:
    if df.is_empty():
        return df

    cols = df.columns
    src = "CMV" if "CMV" in cols else ("cmv" if "cmv" in cols else None)
    if src is None:
        return df  # no breadth source → passthrough

    s = df[src].cast(pl.Float64)
    cum = s.cum_sum()

    # scalar min/max on Series
    mn = float(cum.min() or 0.0)
    mx = float(cum.max() or 0.0)
    rng = mx - mn

    if abs(rng) < 1e-12:
        # flat → zeros
        cum_01 = pl.Series("breadth_cum_norm", [0.0] * df.height, dtype=pl.Float64)
        cum_pm1 = pl.Series("breadth_cum", [0.0] * df.height, dtype=pl.Float64)
    else:
        cum_01 = ((cum - mn) / rng).alias("breadth_cum_norm")  # [0, 1]
        cum_pm1 = (cum_01 * 2.0 - 1.0).alias("breadth_cum")  # [-1, 1]

    return df.with_columns([cum_pm1, cum_01])


# ------------------------------------------------------------
# 📊 Diagnostic Summary (Headless)
# ------------------------------------------------------------
def summarize_breadth(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if not isinstance(df, pl.DataFrame):
        return {"status": "empty"}

    if (
        df.is_empty()
        or "Breadth_Persistence" not in df.columns
        or "Breadth_Bias" not in df.columns
    ):
        return {"status": "empty"}

    last_persist = df["Breadth_Persistence"][-1]
    try:
        val = float(last_persist) if last_persist is not None else float("nan")
    except Exception:
        val = float("nan")

    bias = str(df["Breadth_Bias"][-1]) if "Breadth_Bias" in df.columns else "⚪ Neutral"

    strength = (
        "Strong"
        if (not math.isnan(val)) and abs(val) > 0.6
        else "Moderate"
        if (not math.isnan(val)) and abs(val) > 0.3
        else "Weak"
    )

    return {
        "status": "ok",
        "Breadth_Persistence": round(val, 3) if not math.isnan(val) else 0.0,
        "Bias": bias,
        "Strength": strength,
    }

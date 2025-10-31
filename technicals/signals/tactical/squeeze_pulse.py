# ============================================================
# queen/technicals/signals/tactical/squeeze_pulse.py
# ------------------------------------------------------------
# ⚙️ Squeeze Pulse — BB vs Keltner compression/expansion
# 100% Polars, consistent column names, safe fallbacks
# ============================================================

from __future__ import annotations

import polars as pl


def detect_squeeze_pulse(
    df: pl.DataFrame,
    *,
    bb_upper_col: str = "bb_upper",
    bb_lower_col: str = "bb_lower",
    keltner_upper_col: str = "keltner_upper",
    keltner_lower_col: str = "keltner_lower",
    squeeze_threshold: float = 0.015,
    out_col: str = "Squeeze_Signal",
) -> pl.DataFrame:
    """Flags:
    ⚡ Squeeze Ready  (BB inside Keltner)
    🚀 Squeeze Release (BB across/outside Keltner with width expansion)
    ➡️ Stable  (otherwise)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    req = [bb_upper_col, bb_lower_col, keltner_upper_col, keltner_lower_col]
    missing = [c for c in req if c not in df.columns]
    if missing:
        # Return a column that explicitly marks skipped
        return df.with_columns(pl.lit("➡️ Skipped").alias(out_col))

    bb_w = (pl.col(bb_upper_col) - pl.col(bb_lower_col)).alias("_bb_w")
    kt_w = (pl.col(keltner_upper_col) - pl.col(keltner_lower_col)).alias("_kt_w")

    inside = (pl.col(bb_upper_col) < pl.col(keltner_upper_col)) & (
        pl.col(bb_lower_col) > pl.col(keltner_lower_col)
    )
    across = (pl.col(bb_upper_col) > pl.col(keltner_upper_col)) & (
        pl.col(bb_lower_col) < pl.col(keltner_lower_col)
    )
    expanded = pl.col("_bb_w") > pl.col("_kt_w") * (1.0 + float(squeeze_threshold))

    signal = (
        pl.when(inside)
        .then(pl.lit("⚡ Squeeze Ready"))
        .when(across & expanded)
        .then(pl.lit("🚀 Squeeze Release"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias(out_col)
    )

    out = df.with_columns([bb_w, kt_w]).with_columns([signal]).drop(["_bb_w", "_kt_w"])
    return out


def summarize_squeeze(df: pl.DataFrame, col: str = "Squeeze_Signal") -> str:
    if col not in df.columns or df.is_empty():
        return "Squeeze Ready: 0 | Releases: 0 | Last: –"
    ready = (df[col] == "⚡ Squeeze Ready").sum()
    release = (df[col] == "🚀 Squeeze Release").sum()
    last = df[col].drop_nulls().tail(1).item() if df.height else "–"
    return f"Squeeze Ready: {ready} | Releases: {release} | Last: {last}"


# Registry export
EXPORTS = {"squeeze_pulse": detect_squeeze_pulse}

# Local smoke
if __name__ == "__main__":
    import numpy as np

    n = 200
    price = np.linspace(100, 120, n) + np.random.normal(0, 0.5, n)
    df = pl.DataFrame(
        {
            "bb_upper": price + np.random.uniform(1.5, 2.5, n),
            "bb_lower": price - np.random.uniform(1.5, 2.5, n),
            "keltner_upper": price + np.random.uniform(1.0, 1.5, n),
            "keltner_lower": price - np.random.uniform(1.0, 1.5, n),
        }
    )
    out = detect_squeeze_pulse(df)
    print("✅", summarize_squeeze(out))

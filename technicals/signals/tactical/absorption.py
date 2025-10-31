# ============================================================
# queen/technicals/signals/tactical/absorption.py
# ------------------------------------------------------------
# ⚙️ Smart Money Absorption (Polars-native, DRY)
# Outputs:
#   • Absorption_Score  ∈ [-1, +1]
#   • Absorption_Flag   ("🟩 Accumulation" | "🟥 Distribution" | "➡️ Stable")
#   • Absorption_Zone   (same as flag; friendly alias for dashboards)
# ============================================================

from __future__ import annotations
import polars as pl
from typing import Literal, Dict, Any


# -----------------------------
# Core
# -----------------------------
def detect_absorption_zones(
    df: pl.DataFrame,
    *,
    cmv_col: str = "CMV",
    volume_col: str = "volume",
    mfi_col: str = "MFI",
    chaikin_col: str = "Chaikin_Osc",
    flat_eps: float = 0.05,  # “flat CMV” tolerance
    v_trend_lb: int = 2,  # lookback for vol trend
    score_weights: Dict[str, float] | None = None,  # weights for components
) -> pl.DataFrame:
    """Polars-native absorption detector. No Python loops.

    Heuristic:
      • Hidden accumulation  : CMV ~ flat, Volume ↑,  MFI ↑,  Chaikin > 0  → +score
      • Hidden distribution : CMV ~ flat, Volume ↑,  MFI ↓,  Chaikin < 0  → -score
    """
    if df.is_empty():
        return df

    # ensure columns exist (fill zeros if missing)
    need = {cmv_col, volume_col, mfi_col, chaikin_col}
    patch_cols = [c for c in need if c not in df.columns]
    if patch_cols:
        df = df.with_columns([pl.lit(0.0).alias(c) for c in patch_cols])

    w = {"cmv": 1.0, "vol": 1.0, "mfi": 1.0, "chaikin": 1.0}
    if score_weights:
        w.update({k: float(v) for k, v in score_weights.items() if k in w})

    # diffs / trends
    cmv_diff = (pl.col(cmv_col) - pl.col(cmv_col).shift(1)).abs()
    vol_up = pl.col(volume_col) > pl.col(volume_col).shift(v_trend_lb)
    mfi_up = pl.col(mfi_col) > pl.col(mfi_col).shift(1)
    mfi_dn = pl.col(mfi_col) < pl.col(mfi_col).shift(1)
    ch_pos = pl.col(chaikin_col) > 0
    ch_neg = pl.col(chaikin_col) < 0

    cmv_flat = cmv_diff <= flat_eps

    # component scores in [-1, +1]
    s_vol = pl.when(vol_up).then(1.0).otherwise(0.0)
    s_mfi_acc = pl.when(mfi_up).then(1.0).otherwise(-1.0)
    s_mfi_dis = pl.when(mfi_dn).then(1.0).otherwise(-1.0)
    s_ch_pos = pl.when(ch_pos).then(1.0).otherwise(-1.0)
    s_ch_neg = pl.when(ch_neg).then(1.0).otherwise(-1.0)

    # accumulation and distribution raw scores
    acc_raw = (
        (pl.when(cmv_flat).then(1.0).otherwise(0.0) * w["cmv"])
        + (s_vol * w["vol"])
        + (s_mfi_acc * w["mfi"])
        + (s_ch_pos * w["chaikin"])
    ) / (w["cmv"] + w["vol"] + w["mfi"] + w["chaikin"])

    dis_raw = (
        (pl.when(cmv_flat).then(1.0).otherwise(0.0) * w["cmv"])
        + (s_vol * w["vol"])
        + (s_mfi_dis * w["mfi"])
        + (s_ch_neg * w["chaikin"])
    ) / (w["cmv"] + w["vol"] + w["mfi"] + w["chaikin"])

    # final signed score ∈ [-1, +1]
    score = (acc_raw - dis_raw).clip(-1.0, 1.0).alias("Absorption_Score")

    flag = (
        pl.when(score > 0.15)
        .then(pl.lit("🟩 Accumulation"))
        .when(score < -0.15)
        .then(pl.lit("🟥 Distribution"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias("Absorption_Flag")
    )

    zone = flag.alias("Absorption_Zone")

    return df.with_columns([score, flag, zone])


# -----------------------------
# Summary helper (optional)
# -----------------------------
def summarize_absorption(df: pl.DataFrame) -> str:
    if (
        not isinstance(df, pl.DataFrame)
        or df.is_empty()
        or "Absorption_Score" not in df.columns
    ):
        return "No absorption data."

    # eager aggregation (no Expr.collect())
    agg = df.select(
        (pl.col("Absorption_Score") > 0).sum().alias("acc"),
        (pl.col("Absorption_Score") < 0).sum().alias("dis"),
    ).to_dicts()[0]

    acc = int(agg.get("acc", 0) or 0)
    dis = int(agg.get("dis", 0) or 0)

    last_flag = "—"
    if "Absorption_Flag" in df.columns and df["Absorption_Flag"].len() > 0:
        s = df["Absorption_Flag"].drop_nulls()
        if s.len() > 0:
            last_flag = s[-1]

    return f"Accumulations: {acc} | Distributions: {dis} | Last: {last_flag}"


# -----------------------------
# Registry export for discovery
# -----------------------------
EXPORTS: Dict[str, Any] = {
    "detect_absorption_zones": detect_absorption_zones,
}

# ============================================================
# queen/technicals/signals/tactical/ai_recommender.py
# ------------------------------------------------------------
# 🧠 Tactical AI Recommender (Stats-Only, Settings-Driven Paths)
# - 100% Polars
# - No ML deps
# - Paths resolved via queen.settings.settings.PATHS with safe fallback
# ============================================================

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl
from queen.helpers.logger import log

# ── Settings-aware default paths ─────────────────────────────
try:
    from queen.settings import settings as SETTINGS  # has PATHS
except Exception:
    SETTINGS = None


def _default_event_log_path() -> Path:
    """Prefer SETTINGS.PATHS['LOGS']/tactical_event_log.csv; fallback to runtime/logs."""
    if SETTINGS:
        return SETTINGS.PATHS["LOGS"] / "tactical_event_log.csv"
    return Path("queen/data/runtime/logs") / "tactical_event_log.csv"


# ── Utils ───────────────────────────────────────────────────
def _norm01(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    a_min, a_max = np.nanmin(arr), np.nanmax(arr)
    if not np.isfinite(a_min) or not np.isfinite(a_max) or a_max == a_min:
        return np.zeros_like(arr)
    out = (arr - a_min) / (a_max - a_min)
    return np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0)


# ── Core ────────────────────────────────────────────────────
def analyze_event_log(log_path: str | os.PathLike | None = None) -> pl.DataFrame:
    """Compute historical stats per timeframe from settings-driven log path."""
    path = Path(log_path) if log_path else _default_event_log_path()
    if not path.exists():
        log.info(f"[AI-Reco] No event log at {path} — returning empty.")
        return pl.DataFrame()

    df = pl.read_csv(path, ignore_errors=True)
    if (
        df.is_empty()
        or "timeframe" not in df.columns
        or "Reversal_Alert" not in df.columns
    ):
        log.warning(
            "[AI-Reco] Log missing required columns (timeframe/Reversal_Alert)."
        )
        return pl.DataFrame()

    df = df.drop_nulls(["Reversal_Alert"]).filter(pl.col("Reversal_Alert") != "")

    agg = (
        df.group_by("timeframe")
        .agg(
            [
                pl.count().alias("Event_Count"),
                pl.col("Reversal_Alert").str.contains("BUY").sum().alias("BUY_Count"),
                pl.col("Reversal_Alert").str.contains("SELL").sum().alias("SELL_Count"),
                pl.col("Reversal_Score")
                .cast(pl.Float64, strict=False)
                .fill_null(0)
                .mean()
                .alias("Avg_Score"),
            ]
        )
        .with_columns(
            [
                (pl.col("BUY_Count") / pl.col("Event_Count")).alias("BUY_Ratio"),
                (pl.col("SELL_Count") / pl.col("Event_Count")).alias("SELL_Ratio"),
                (pl.col("BUY_Ratio") - pl.col("SELL_Ratio")).alias("Bias_Skew"),
            ]
        )
    )

    if agg.is_empty():
        return agg

    skew_norm = _norm01(agg["Bias_Skew"].to_numpy())
    count_norm = _norm01(agg["Event_Count"].to_numpy())
    conf = np.round(0.6 * skew_norm + 0.4 * count_norm, 2)

    return agg.with_columns(pl.Series("Confidence", conf))


def compute_forecast(df_stats: pl.DataFrame, *, margin: float = 0.10) -> pl.DataFrame:
    if df_stats.is_empty():
        return df_stats
    buy_dominant = pl.col("BUY_Ratio") > (pl.col("SELL_Ratio") + margin)
    sell_dominant = pl.col("SELL_Ratio") > (pl.col("BUY_Ratio") + margin)
    return df_stats.with_columns(
        pl.when(buy_dominant)
        .then(pl.lit("🟢 BUY Likely"))
        .when(sell_dominant)
        .then(pl.lit("🔴 SELL Likely"))
        .otherwise(pl.lit("⚪ Neutral"))
        .alias("Forecast")
    )


# Public entrypoint (settings-driven by default)
def recommend_from_log(log_path: str | os.PathLike | None = None) -> pl.DataFrame:
    stats = analyze_event_log(log_path)
    if stats.is_empty():
        return stats
    return compute_forecast(stats)

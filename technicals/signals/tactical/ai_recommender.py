# ============================================================
# quant/signals/tactical/tactical_ai_recommender.py
# ------------------------------------------------------------
# 🧠 Phase 5.0 — Tactical AI Recommender (Learning Engine Base)
# Learns from historical tactical events to forecast
# next likely bias and confidence for each timeframe.
# ============================================================

import os

import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()


# ============================================================
# ⚙️ Utility — Safe Normalization
# ============================================================
def normalize_series(series: np.ndarray) -> np.ndarray:
    """Normalize a series between 0 and 1."""
    if len(series) == 0:
        return np.array([])
    s_min, s_max = np.nanmin(series), np.nanmax(series)
    if s_max - s_min == 0:
        return np.zeros_like(series)
    return (series - s_min) / (s_max - s_min)


# ============================================================
# 🧩 Core Learner — Historical Context Stats
# ============================================================
def analyze_event_log(log_path: str = "quant/logs/tactical_event_log.csv") -> pl.DataFrame:
    """Compute historical statistics per timeframe."""
    if not os.path.exists(log_path):
        console.print(f"⚠️ No event log found at {log_path}")
        return pl.DataFrame()

    df = pl.read_csv(log_path)

    # Ensure required columns exist
    if "timeframe" not in df.columns or "Reversal_Alert" not in df.columns:
        console.print("⚠️ Log missing critical columns — cannot proceed.")
        return pl.DataFrame()

    # Clean + prepare
    df = df.drop_nulls(["Reversal_Alert"])
    df = df.filter(pl.col("Reversal_Alert") != "")

    # Aggregate signals by timeframe
    agg = (
        df.group_by("timeframe")
        .agg([
            pl.count().alias("Event_Count"),
            pl.col("Reversal_Alert").filter(pl.col("Reversal_Alert").str.contains("BUY")).count().alias("BUY_Count"),
            pl.col("Reversal_Alert").filter(pl.col("Reversal_Alert").str.contains("SELL")).count().alias("SELL_Count"),
            pl.col("Reversal_Score").fill_null(0).mean().alias("Avg_Score"),
        ])
        .with_columns([
            (pl.col("BUY_Count") / pl.col("Event_Count")).alias("BUY_Ratio"),
            (pl.col("SELL_Count") / pl.col("Event_Count")).alias("SELL_Ratio"),
        ])
        .with_columns([
            (pl.col("BUY_Ratio") - pl.col("SELL_Ratio")).alias("Bias_Skew"),
        ])
    )

    # Compute confidence score based on magnitude of skew and event volume
    skew_norm = normalize_series(agg["Bias_Skew"].to_numpy())
    count_norm = normalize_series(agg["Event_Count"].to_numpy())

    agg = agg.with_columns([
        pl.Series("Confidence", np.round((0.6 * skew_norm + 0.4 * count_norm), 2))
    ])

    return agg


# ============================================================
# 🧭 Forecast — Predict Next Likely Bias
# ============================================================
def compute_forecast(df_stats: pl.DataFrame) -> pl.DataFrame:
    """Classify next likely move (BUY / SELL / NEUTRAL) based on ratios."""
    if df_stats.is_empty():
        return df_stats

    forecast = []
    for i in range(len(df_stats)):
        buy_r, sell_r = df_stats["BUY_Ratio"][i], df_stats["SELL_Ratio"][i]
        if buy_r > sell_r + 0.1:
            forecast.append("🟢 BUY Likely")
        elif sell_r > buy_r + 0.1:
            forecast.append("🔴 SELL Likely")
        else:
            forecast.append("⚪ Neutral")

    return df_stats.with_columns(pl.Series("Forecast", forecast))


# ============================================================
# 📊 Render Summary — AI Recommender Dashboard
# ============================================================
def render_ai_recommender(log_path: str = "quant/logs/tactical_event_log.csv"):
    """Reads event log, analyzes bias distribution, and prints forecast summary."""
    df_stats = analyze_event_log(log_path)
    if df_stats.is_empty():
        console.print("⚠️ No data available for AI Recommender summary.")
        return None

    df_forecast = compute_forecast(df_stats)

    table = Table(
        title="🤖 Tactical AI Recommender — Bias Forecast (Phase 5.0)",
        header_style="bold green",
        expand=True,
    )
    for col in ["timeframe", "Event_Count", "BUY_Ratio", "SELL_Ratio", "Bias_Skew", "Confidence", "Forecast"]:
        table.add_column(col, justify="center")

    for row in df_forecast.iter_rows(named=True):
        table.add_row(*[str(v) for v in row.values()])

    console.print(table)
    return df_forecast


# ============================================================
# 🧪 Example Usage
# ============================================================
if __name__ == "__main__":
    render_ai_recommender()

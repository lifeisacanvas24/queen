# queen/technicals/signals/tactical/ai_recommender.py
from __future__ import annotations

import polars as pl
from quant import config
from quant.utils.logs import get_logger
from rich.console import Console
from rich.table import Table

log = get_logger("AI-Reco")
console = Console()


def _log_path() -> str:
    # settings-driven (no hardcoded paths)
    return str(config.get_path("paths.logs") / "tactical_event_log.csv")


def _ensure_ratios(df: pl.DataFrame) -> pl.DataFrame:
    have = set(df.columns)
    if {"BUY_Ratio", "SELL_Ratio"}.issubset(have):
        return df
    cols = {"Event_Count", "BUY_Count", "SELL_Count"}
    if not cols.issubset(have):
        return df
    return df.with_columns(
        [
            (
                pl.col("BUY_Count")
                / pl.max_horizontal(pl.lit(1), pl.col("Event_Count"))
            ).alias("BUY_Ratio"),
            (
                pl.col("SELL_Count")
                / pl.max_horizontal(pl.lit(1), pl.col("Event_Count"))
            ).alias("SELL_Ratio"),
        ]
    )


def analyze_event_log(log_path: str | None = None) -> pl.DataFrame:
    path = str(log_path) if log_path else _log_path()
    try:
        df = pl.read_csv(path)
    except FileNotFoundError:
        log.info(f"[AI-Reco] No event log at {path} — returning empty.")
        return pl.DataFrame()
    if "Reversal_Alert" in df.columns:
        df = df.filter(
            pl.col("Reversal_Alert").is_not_null() & (pl.col("Reversal_Alert") != "")
        )
    agg = df.group_by("timeframe").agg(
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
    agg = _ensure_ratios(agg).with_columns(
        [(pl.col("BUY_Ratio") - pl.col("SELL_Ratio")).alias("Bias_Skew")]
    )

    def _norm01(expr: pl.Expr) -> pl.Expr:
        # vector norm in Polars expr space (handles empty/range==0 safely)
        return (
            pl.when(pl.max(expr) - pl.min(expr) == 0)
            .then(0.0)
            .otherwise((expr - pl.min(expr)) / (pl.max(expr) - pl.min(expr)))
        )

    return agg.with_columns(
        [
            (
                0.6 * _norm01(pl.col("Bias_Skew").abs())
                + 0.4 * _norm01(pl.col("Event_Count"))
            )
            .round(2)
            .alias("Confidence")
        ]
    )


def compute_forecast(df_stats: pl.DataFrame) -> pl.DataFrame:
    if df_stats.is_empty():
        return df_stats
    return df_stats.with_columns(
        [
            pl.when(pl.col("BUY_Ratio") > pl.col("SELL_Ratio") + 0.10)
            .then("🟢 BUY Likely")
            .when(pl.col("SELL_Ratio") > pl.col("BUY_Ratio") + 0.10)
            .then("🔴 SELL Likely")
            .otherwise("⚪ Neutral")
            .alias("Forecast")
        ]
    )


def render_ai_recommender(log_path: str | None = None):
    stats = analyze_event_log(log_path)
    if stats.is_empty():
        console.print("⚠️ No data available for AI Recommender summary.")
        return None
    out = compute_forecast(stats)
    table = Table(
        title="🤖 Tactical AI Recommender — Bias Forecast",
        header_style="bold green",
        expand=True,
    )
    for col in [
        "timeframe",
        "Event_Count",
        "BUY_Ratio",
        "SELL_Ratio",
        "Bias_Skew",
        "Confidence",
        "Forecast",
    ]:
        if col in out.columns:
            table.add_column(col, justify="center")
    for row in out.iter_rows(named=True):
        table.add_row(*[str(row.get(c, "")) for c in table.columns])
    console.print(table)
    return out

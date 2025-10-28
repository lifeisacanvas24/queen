# ============================================================
# queen/technicals/signals/tactical/tactical_meta_introspector.py
# ------------------------------------------------------------
# 🧠 Phase 6.3 — Tactical Meta Introspector
# The self-analysis engine that replays memory snapshots,
# evaluates drift-impact relationships, and learns from its
# own performance evolution across time.
# ============================================================

import os

import plotly.graph_objects as go
import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# 🧩 Configuration (to later move into config.py)
# ============================================================
META_MEMORY_LOG = "quant/logs/meta_memory_log.csv"
DRIFT_LOG_PATH = "quant/logs/meta_drift_log.csv"
WEIGHTS_PATH = "quant/config/indicator_weights.json"


# ============================================================
# 📦 Load Data
# ============================================================
def load_memory_data():
    if not os.path.exists(META_MEMORY_LOG):
        console.print(f"⚠️ No meta memory log found at {META_MEMORY_LOG}")
        return pl.DataFrame()
    return pl.read_csv(META_MEMORY_LOG)


def load_drift_data():
    if not os.path.exists(DRIFT_LOG_PATH):
        console.print(f"⚠️ No drift log found at {DRIFT_LOG_PATH}")
        return pl.DataFrame()
    return pl.read_csv(DRIFT_LOG_PATH)


# ============================================================
# 📈 Correlate Drift vs Retraining Impact
# ============================================================
def analyze_drift_vs_retrain(memory_df: pl.DataFrame, drift_df: pl.DataFrame):
    """Correlate drift magnitude to retraining improvements."""
    if memory_df.is_empty() or drift_df.is_empty():
        console.print("⚪ Insufficient data for introspection.")
        return None

    # Convert timestamps
    memory_df = memory_df.with_columns(pl.col("timestamp").str.strptime(pl.Datetime))
    drift_df = drift_df.with_columns(pl.col("timestamp").str.strptime(pl.Datetime))

    # Merge nearest drift per memory snapshot
    joined = memory_df.join_asof(drift_df, on="timestamp", strategy="backward").rename(
        {"drift": "drift_before_retrain"}
    )

    joined = joined.with_columns(
        [
            (pl.col("top_weight").cast(float) * pl.col("drift_before_retrain")).alias(
                "adaptive_response"
            ),
            pl.when(pl.col("drift_before_retrain") > 0.1)
            .then("High Drift")
            .otherwise("Stable")
            .alias("drift_state"),
        ]
    )

    corr = joined["adaptive_response"].corr(joined["top_weight"])
    console.print(
        f"📊 Correlation between drift and weight adaptation: [cyan]{corr:.3f}[/cyan]"
    )

    # Visualization
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=joined["timestamp"].to_list(),
            y=joined["drift_before_retrain"].to_list(),
            name="Drift Magnitude",
            mode="lines+markers",
            line=dict(color="orange", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=joined["timestamp"].to_list(),
            y=joined["top_weight"].to_list(),
            name="Top Indicator Weight",
            mode="lines+markers",
            line=dict(color="green", width=2, dash="dot"),
        )
    )
    fig.update_layout(
        title="🧠 Drift vs Indicator Adaptation Timeline",
        template="plotly_dark",
        yaxis_title="Magnitude",
        height=420,
    )
    fig.show()

    return joined


# ============================================================
# 📊 Memory Evolution Analysis
# ============================================================
def analyze_memory_evolution(memory_df: pl.DataFrame):
    if memory_df.is_empty():
        console.print("⚪ No memory snapshots to analyze.")
        return

    # Compute time deltas
    df = memory_df.with_columns(
        [
            pl.col("timestamp").str.strptime(pl.Datetime).alias("ts"),
        ]
    )
    df = df.sort("ts")

    if "top_weight" in df.columns:
        avg_weight_change = float(df["top_weight"].diff().abs().mean())
        console.print(
            f"📈 Avg top-weight change per retrain: [green]{avg_weight_change:.3f}[/green]"
        )

    # Table summary
    table = Table(
        title="🧬 Meta-Introspective Summary",
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Timestamp")
    table.add_column("Top Feature")
    table.add_column("Top Weight")
    table.add_column("Drift Threshold")

    for row in df.tail(10).iter_rows(named=True):
        table.add_row(
            str(row.get("timestamp", "")),
            str(row.get("top_feature", "")),
            f"{row.get('top_weight', 0):.3f}" if row.get("top_weight") else "—",
            str(row.get("drift_threshold", "")),
        )

    console.print(table)
    console.print("[green]✅ Meta introspection analysis complete.[/green]")


# ============================================================
# 🚀 Main Entry
# ============================================================
def run_meta_introspector():
    console.rule("[bold cyan]🧠 Phase 6.3 — Tactical Meta Introspector")

    memory_df = load_memory_data()
    drift_df = load_drift_data()

    if not memory_df.is_empty():
        analyze_memory_evolution(memory_df)
    joined = analyze_drift_vs_retrain(memory_df, drift_df)
    return joined


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    run_meta_introspector()

# ============================================================
# quant/signals/tactical/tactical_meta_dashboard.py
# ------------------------------------------------------------
# 🎛️ Phase 6.1 — Tactical Meta Dashboard
# Interactive monitoring dashboard for AI health, drift,
# and indicator weight evolution (Plotly + Rich hybrid).
# ============================================================

import json
import os

import plotly.graph_objects as go
import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# 🧩 Paths
# ============================================================
CONFIG_PATH = "quant/config/meta_controller.json"
WEIGHTS_PATH = "quant/config/indicator_weights.json"
DRIFT_LOG_PATH = "quant/logs/meta_drift_log.csv"

# ============================================================
# 📊 Helper: Load Drift Log
# ============================================================
def load_drift_log() -> pl.DataFrame:
    if not os.path.exists(DRIFT_LOG_PATH):
        console.print(f"⚠️ No drift log found at {DRIFT_LOG_PATH}")
        return pl.DataFrame(schema={"timestamp": str, "drift": float})
    return pl.read_csv(DRIFT_LOG_PATH)

# ============================================================
# 📈 Plot Drift Over Time
# ============================================================
def plot_drift_timeline(df: pl.DataFrame):
    if df.is_empty():
        console.print("⚪ No drift history yet.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"].to_list(),
            y=df["drift"].to_list(),
            mode="lines+markers",
            name="Model Drift",
            line=dict(width=2)
        )
    )
    fig.update_layout(
        title="📉 Model Drift Over Time",
        xaxis_title="Timestamp (UTC)",
        yaxis_title="Drift Magnitude",
        template="plotly_dark",
        height=400,
    )
    fig.show()

# ============================================================
# 📊 Indicator Weight Table + Plot
# ============================================================
def render_indicator_weights():
    if not os.path.exists(WEIGHTS_PATH):
        console.print("⚠️ No indicator weight file found.")
        return

    with open(WEIGHTS_PATH) as f:
        weights = json.load(f)

    table = Table(
        title="🧬 Current Indicator Weights",
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Feature")
    table.add_column("Weight (%)")

    features, values = [], []
    for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        pct = f"{v * 100:.2f}%"
        table.add_row(k, pct)
        features.append(k)
        values.append(v * 100)

    console.print(table)

    # Plot bar chart
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=features,
            y=values,
            marker_color="lightgreen",
            name="Indicator Importance (%)"
        )
    )
    fig.update_layout(
        title="🧩 Indicator Weight Importance",
        xaxis_title="Indicators",
        yaxis_title="Weight (%)",
        template="plotly_dark",
        height=400,
    )
    fig.show()

# ============================================================
# 📋 Meta Configuration Summary
# ============================================================
def show_meta_config():
    if not os.path.exists(CONFIG_PATH):
        console.print(f"⚠️ Config file missing at {CONFIG_PATH}")
        return

    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    table = Table(title="🧠 Meta Controller Configuration", header_style="bold magenta")
    table.add_column("Parameter")
    table.add_column("Value")

    for k, v in cfg.items():
        table.add_row(k, str(v))
    console.print(table)

# ============================================================
# 🚀 Dashboard Entrypoint
# ============================================================
def render_meta_dashboard():
    console.rule("[bold green]🎛️ Phase 6.1 — Tactical Meta Dashboard")

    # Show meta-config info
    show_meta_config()

    # Drift monitoring
    console.print("\n📉 Model Drift History")
    df_drift = load_drift_log()
    plot_drift_timeline(df_drift)

    # Indicator weights overview
    console.print("\n🧬 Indicator Weight Evolution")
    render_indicator_weights()

    console.print("[green]✅ Meta Dashboard visualization complete.[/green]")


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    render_meta_dashboard()

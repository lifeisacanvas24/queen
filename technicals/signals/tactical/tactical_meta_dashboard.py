# queen/technicals/signals/tactical/meta_dashboard.py
from __future__ import annotations

import json
import os

import polars as pl
from quant import config
from quant.utils.logs import get_logger
from rich.console import Console
from rich.table import Table

log = get_logger("MetaDashboard")
console = Console()


def _paths() -> dict:
    logs = config.get_path("paths.logs")
    conf = config.get_path("paths.configs")
    return {
        "cfg": str(conf / "meta_controller.json"),
        "weights": str(conf / "indicator_weights.json"),
        "drift": str(logs / "meta_drift_log.csv"),
    }


def load_drift_log() -> pl.DataFrame:
    p = _paths()["drift"]
    if not os.path.exists(p):
        console.print(f"⚠️ No drift log found at {p}")
        return pl.DataFrame(schema={"timestamp": pl.Utf8, "drift": pl.Float64})
    return pl.read_csv(p)


def show_meta_config():
    p = _paths()["cfg"]
    if not os.path.exists(p):
        console.print(f"⚠️ Config missing at {p}")
        return
    with open(p) as f:
        cfg = json.load(f)
    table = Table(title="🧠 Meta Controller Configuration", header_style="bold magenta")
    table.add_column("Parameter")
    table.add_column("Value")
    for k, v in cfg.items():
        table.add_row(k, str(v))
    console.print(table)


def render_indicator_weights():
    p = _paths()["weights"]
    if not os.path.exists(p):
        console.print("⚠️ No indicator weight file found.")
        return
    with open(p) as f:
        weights = json.load(f)
    table = Table(title="🧬 Indicator Weights", header_style="bold cyan", expand=True)
    table.add_column("Feature")
    table.add_column("Weight (%)")
    for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        table.add_row(k, f"{v*100:.2f}%")
    console.print(table)


def plot_drift_timeline(df: pl.DataFrame):
    if df.is_empty():
        console.print("⚪ No drift history yet.")
        return
    try:
        import plotly.graph_objects as go
    except Exception:
        # graceful no-plotly mode
        console.print("ℹ️ Plotly not installed. Showing table view.")
        console.print(df.tail(20))
        return
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"].to_list(),
            y=df["drift"].to_list(),
            mode="lines+markers",
            name="Model Drift",
        )
    )
    fig.update_layout(
        title="📉 Model Drift Over Time", xaxis_title="UTC", yaxis_title="Drift"
    )
    fig.show()


def render_meta_dashboard():
    console.rule("[bold green]🎛️ Tactical Meta Dashboard")
    show_meta_config()
    console.print("\n📉 Model Drift History")
    plot_drift_timeline(load_drift_log())
    console.print("\n🧬 Indicator Weight Overview")
    render_indicator_weights()
    console.print("[green]✅ Meta Dashboard complete.[/green]")

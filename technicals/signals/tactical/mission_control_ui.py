# ============================================================
# queen/technicals/signals/tactical/mission_control_ui.py
# ------------------------------------------------------------
# 🧭 Phase 7.3 — Cockpit Mission Control UI
# Web + Terminal dashboard for supervising all Tactical Daemons,
# models, drift logs, and AI health in real time.
# ============================================================

import json
import os
from datetime import datetime
from typing import Dict, List

import plotly.graph_objects as go
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from rich.console import Console
from rich.table import Table

# Paths (move later to config.py)
HEALTH_LOG = "quant/logs/supervisor_health.json"
DRIFT_LOG = "quant/logs/meta_drift_log.csv"
WEIGHT_LOG = "quant/config/indicator_weights.json"

console = Console()
app = FastAPI(title="🛰️ Quant Cockpit Mission Control")


# ============================================================
# 🧩 Helper Functions
# ============================================================
def load_json(path: str) -> Dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_csv_lines(path: str, limit: int = 100) -> List[Dict]:
    if not os.path.exists(path):
        return []
    import csv

    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows[-limit:]


# ============================================================
# 🛰️ API Routes
# ============================================================
@app.get("/health", response_class=JSONResponse)
def get_health_status():
    """Return the latest supervisor health log."""
    return load_json(HEALTH_LOG)


@app.get("/weights", response_class=JSONResponse)
def get_weights():
    """Return the current indicator weights."""
    return load_json(WEIGHT_LOG)


@app.get("/drift", response_class=JSONResponse)
def get_drift_log():
    """Return drift log entries."""
    return load_csv_lines(DRIFT_LOG)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Render the main control dashboard with Plotly charts."""
    health = load_json(HEALTH_LOG)
    drift = load_csv_lines(DRIFT_LOG, limit=50)
    weights = load_json(WEIGHT_LOG)

    # --- Plotly: Drift Timeline Chart ---
    drift_chart = go.Figure()
    if drift:
        drift_chart.add_trace(
            go.Scatter(
                x=[d["timestamp"] for d in drift],
                y=[float(d.get("drift_score", 0)) for d in drift],
                mode="lines+markers",
                name="Drift Score",
            )
        )
        drift_chart.update_layout(
            title="Model Drift Over Time", xaxis_title="Time", yaxis_title="Drift Score"
        )

    drift_html = drift_chart.to_html(include_plotlyjs="cdn")

    # --- Weight Distribution Chart ---
    weight_chart = go.Figure()
    if weights:
        weight_chart.add_trace(
            go.Bar(
                x=list(weights.keys()),
                y=list(weights.values()),
                name="Indicator Weights",
            )
        )
        weight_chart.update_layout(title="Current Indicator Weights")

    weight_html = weight_chart.to_html(include_plotlyjs=False)

    # --- Health Summary ---
    health_table = f"""
    <table border='1' cellpadding='6'>
      <tr><th>Cycle</th><th>Healthy</th><th>Failed</th><th>Duration (min)</th></tr>
      <tr><td>{health.get("cycle", "–")}</td>
          <td>{health.get("healthy", 0)}</td>
          <td>{health.get("failed", 0)}</td>
          <td>{health.get("duration_min", 0)}</td></tr>
    </table>
    """

    html = f"""
    <html>
    <head><title>🛰️ Quant Cockpit Mission Control</title></head>
    <body style="font-family: sans-serif; background: #0e0e10; color: white;">
      <h1>🧭 Quant Cockpit Mission Control</h1>
      <h2>🚦 Live Supervisor Health</h2>
      {health_table}
      <h2>📊 Drift Analytics</h2>
      {drift_html}
      <h2>⚙️ Indicator Weights</h2>
      {weight_html}
      <footer style='margin-top:50px;'>
        <small>Updated: {datetime.utcnow().isoformat()} UTC</small>
      </footer>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ============================================================
# 🩺 Terminal Summary Renderer
# ============================================================
def render_terminal_summary():
    """Prints a Rich summary of system health."""
    health = load_json(HEALTH_LOG)
    weights = load_json(WEIGHT_LOG)
    drift = load_csv_lines(DRIFT_LOG, limit=10)

    console.rule("[bold magenta]🧭 Mission Control — Terminal Summary")
    table = Table(title="Supervisor Health", header_style="bold cyan")
    table.add_column("Cycle")
    table.add_column("Healthy")
    table.add_column("Failed")
    table.add_column("Duration (min)")
    table.add_row(
        str(health.get("cycle", "–")),
        str(health.get("healthy", "–")),
        str(health.get("failed", "–")),
        str(health.get("duration_min", "–")),
    )
    console.print(table)

    console.print("\n[bold green]Current Indicator Weights:[/bold green]")
    for k, v in weights.items():
        console.print(f"  • {k}: {v:.3f}")

    if drift:
        console.print("\n[bold yellow]Recent Drift Events:[/bold yellow]")
        for d in drift[-5:]:
            console.print(f"  - {d.get('timestamp', '')} → {d.get('drift_score', '0')}")


# ============================================================
# 🧪 Standalone Launch
# ============================================================
if __name__ == "__main__":
    import uvicorn

    render_terminal_summary()
    console.print(
        "[green]🚀 Starting Mission Control Web UI at http://127.0.0.1:8000[/green]"
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)

import datetime
import os

import polars as pl
from rich.console import Console

# ─── Fusion + Tactical
from quant.signals.fusion_cmv import compute_cmv
from quant.signals.indicators.breadth_cumulative import compute_breadth

# ─── Indicators
from quant.signals.indicators.momentum_macd import compute_macd
from quant.signals.indicators.trend_adx_dmi import compute_adx
from quant.signals.indicators.vol_keltner import compute_keltner
from quant.signals.indicators.volume_chaikin import compute_chaikin
from quant.signals.indicators.volume_mfi import compute_mfi
from quant.signals.tactical.tactical_absorption import detect_absorption_zones
from quant.signals.tactical.tactical_divergence import detect_divergence
from quant.signals.tactical.tactical_liquidity_trap import detect_liquidity_trap
from quant.signals.tactical.tactical_squeeze_pulse import detect_squeeze_pulse

# ─── Diagnostics
from quant.signals.utils_indicator_health import (
    indicator_health_report,
    summarize_health_across_timeframes,
)

console = Console()

# ──────────────────────────────────────────────────────────────────────────────
# 🧩 Mock Data Builder
# ──────────────────────────────────────────────────────────────────────────────
def build_mock_data(n: int = 100) -> pl.DataFrame:
    """Builds a mock OHLCV dataset for testing indicators."""
    import numpy as np

    # Ensure timestamps match price array length exactly
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(minutes=n - 1)

    ts = pl.datetime_range(start=start_time, end=end_time, interval="1m", eager=True)
    ts = ts[:n]  # explicitly trim to ensure same length as price arrays

    base_price = np.linspace(100, 110, n)
    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": base_price + np.random.normal(0, 0.2, n),
            "high": base_price + np.random.normal(0.3, 0.2, n),
            "low": base_price - np.random.normal(0.3, 0.2, n),
            "close": base_price + np.random.normal(0, 0.3, n),
            "volume": np.random.randint(1000, 5000, n),
        }
    )

# ──────────────────────────────────────────────────────────────────────────────
# ⚙️ Process Timeframe
# ──────────────────────────────────────────────────────────────────────────────
def process_timeframe(df: pl.DataFrame, tf_name: str) -> tuple[pl.DataFrame, list[str]]:
    df_tf = df.clone()

    # Indicators
    df_tf = compute_macd(df_tf)
    df_tf = compute_adx(df_tf)
    df_tf = compute_keltner(df_tf)
    df_tf = compute_mfi(df_tf)
    df_tf = compute_chaikin(df_tf)
    df_tf = compute_cmv(df_tf)
    df_tf = compute_breadth(df_tf)

    # Tactical systems
    df_tf = detect_liquidity_trap(df_tf)
    df_tf = detect_absorption_zones(df_tf)
    df_tf = detect_divergence(df_tf)
    df_tf = detect_squeeze_pulse(df_tf)

    # Indicator diagnostics
    health_lines = indicator_health_report(df_tf, tf_name)
    return df_tf, health_lines


# ──────────────────────────────────────────────────────────────────────────────
# 🩺 Health Logging
# ──────────────────────────────────────────────────────────────────────────────
def log_health_summary(global_health: dict):
    """Appends the summarized indicator health state to a CSV log."""
    log_dir = "quant/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "indicator_health_log.csv")

    file_exists = os.path.isfile(log_file)
    with open(log_file, "a") as f:
        if not file_exists:
            f.write("timestamp,timeframe,healthy,total,status\n")

        ts = datetime.datetime.utcnow().isoformat()
        for tf, checks in global_health.items():
            healthy = sum("✅" in c for c in checks)
            total = len(checks)
            ratio = healthy / total if total else 0
            status = (
                "HEALTHY" if ratio > 0.8 else "PARTIAL" if ratio > 0.5 else "WEAK"
            )
            f.write(f"{ts},{tf},{healthy},{total},{status}\n")

def render_health_trend(log_file: str = "quant/logs/indicator_health_log.csv", window: int = 10):
    """Render recent health trends (🟢🟡🔴 pulses) per timeframe.
    Reads the indicator_health_log.csv produced by test_composite.py.
    """
    try:
        df = pl.read_csv(log_file)
    except FileNotFoundError:
        console.print("[red]⚠️ No health log found — run cockpit at least once first.[/red]")
        return

    if df.is_empty():
        console.print("[yellow]⚠️ Empty health log — nothing to visualize yet.[/yellow]")
        return

    # ensure chronological order
    df = df.sort("timestamp")

    # map statuses → emojis
    status_map = {"HEALTHY": "🟢", "PARTIAL": "🟡", "WEAK": "🔴"}
    df = df.with_columns(
        pl.col("status").map_elements(lambda s: status_map.get(s, "⚫")).alias("emoji")
    )

    console.print("\n[bold cyan]📈 Health Trend (Last Runs)[/bold cyan]")
    console.print("─" * 80)

    # iterate each timeframe
    for tf in df["timeframe"].unique().to_list():
        sub = df.filter(pl.col("timeframe") == tf).tail(window)
        trend = "".join(sub["emoji"].to_list())
        last = sub["emoji"].to_list()[-1] if len(sub) > 0 else "⚫"

        if last == "🟢":
            arrow = "→ Stable"
        elif last == "🟡":
            arrow = "↗ Recovering"
        elif last == "🔴":
            arrow = "↘ Weakening"
        else:
            arrow = "• No Data"

        console.print(f"[white]{tf:<8}[/white] {trend:<15} {arrow}")

    console.print("─" * 80)

# ──────────────────────────────────────────────────────────────────────────────
# 🚀 Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    console.rule(
        "[bold cyan]🧭 Quant Cockpit — Composite Dashboard (Polars Build, Phases 1–4.4)"
    )

    # Define active timeframes (extendable)
    timeframes = ["5m", "15m", "1h", "daily"]
    df = build_mock_data(200)
    global_health = {}

    # Run each timeframe
    for tf in timeframes:
        console.print(f"\n⏱️ Evaluating timeframe: [yellow]{tf}[/yellow]")
        df_tf, report_lines = process_timeframe(df, tf)
        global_health[tf] = report_lines

    # Global summary + logging
    summarize_health_across_timeframes(global_health)
    log_health_summary(global_health)

    console.print("[green]✅ Composite Dashboard execution complete (Phases 1–4.4)[/green]")


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()

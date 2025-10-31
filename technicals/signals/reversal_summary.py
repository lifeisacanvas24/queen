# ============================================================
# queen/technicals/signals/reversal_summary.py
# ------------------------------------------------------------
# 🩺 Reversal Stack Summary Renderer (Phase 4.8.1)
# Displays color-coded confluence alerts across timeframes.
# ============================================================
from __future__ import annotations

import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()


def _safe_last(df: pl.DataFrame, col: str, default=None):
    if col not in df.columns or df.is_empty():
        return default
    s = df[col]
    # handle strings/numerics, nulls
    try:
        s = s.drop_nans().drop_nulls()
    except Exception:
        s = s.drop_nulls()
    if s.is_empty():
        return default
    return s[-1]  # polars Series supports negative indexing


def summarize_reversal_stacks(global_dfs: dict[str, pl.DataFrame]) -> None:
    """Render a Rich summary table of current Reversal Stack alerts.

    global_dfs: timeframe -> DataFrame (after compute_reversal_stack)
    Requires columns: 'Reversal_Stack_Alert', 'Reversal_Score'
    """
    table = Table(
        title="🔥 Reversal Stack Summary (Confluence Alerts)",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    table.add_column("Timeframe", justify="center", style="bold white")
    table.add_column("Last Signal", justify="center", style="bold")
    table.add_column("Score", justify="center", style="bold cyan")
    table.add_column("Confidence", justify="center", style="bold yellow")

    for tf, df in (global_dfs or {}).items():
        if not isinstance(df, pl.DataFrame) or df.is_empty():
            continue

        last_alert = _safe_last(df, "Reversal_Stack_Alert", default="—")
        last_score = _safe_last(df, "Reversal_Score", default=0.0)

        alert_str = str(last_alert) if last_alert is not None else "—"
        score_val = float(last_score) if last_score is not None else 0.0

        if "BUY" in alert_str:
            color, conf = "green", "HIGH"
        elif "SELL" in alert_str:
            color, conf = "red", "HIGH"
        elif "Potential" in alert_str:
            color, conf = "yellow", "MEDIUM"
        else:
            color, conf = "dim", "LOW"

        table.add_row(
            f"[white]{tf}[/white]",
            f"[bold {color}]{alert_str}[/bold {color}]",
            f"{score_val:.1f}",
            f"[{color}]{conf}[/{color}]",
        )

    console.print("\n")
    console.print(table)
    console.print("\n" + "─" * 80)


if __name__ == "__main__":
    # tiny demo
    import numpy as np

    demo = {
        "15m": pl.DataFrame(
            {
                "Reversal_Stack_Alert": ["—", "Potential BUY", "BUY"],
                "Reversal_Score": [0.2, 0.6, 0.9],
            }
        ),
        "1h": pl.DataFrame(
            {
                "Reversal_Stack_Alert": ["—", "Potential SELL", "SELL"],
                "Reversal_Score": [0.1, 0.55, 0.8],
            }
        ),
    }
    summarize_reversal_stacks(demo)

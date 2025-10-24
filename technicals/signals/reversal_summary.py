# ============================================================
# quant/signals/utils_reversal_summary.py
# ------------------------------------------------------------
# 🩺 Reversal Stack Summary Renderer (Phase 4.8.1)
# Displays color-coded confluence alerts across all timeframes.
# ============================================================

from rich.console import Console
from rich.table import Table

console = Console()


def summarize_reversal_stacks(global_dfs: dict):
    """Renders a Rich summary table of current Reversal Stack alerts.

    Parameters
    ----------
    global_dfs : dict[str, pl.DataFrame]
        Mapping of timeframe → DataFrame after compute_reversal_stack.

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

    for tf, df in global_dfs.items():
        if "Reversal_Stack_Alert" not in df.columns:
            continue

        last_alert = df["Reversal_Stack_Alert"][-1]
        last_score = float(df["Reversal_Score"][-1])

        if "BUY" in last_alert:
            color = "green"
            conf = "HIGH"
        elif "SELL" in last_alert:
            color = "red"
            conf = "HIGH"
        elif "Potential" in last_alert:
            color = "yellow"
            conf = "MEDIUM"
        else:
            color = "dim"
            conf = "LOW"

        table.add_row(
            f"[white]{tf}[/white]",
            f"[bold {color}]{last_alert}[/bold {color}]",
            f"{last_score:.1f}",
            f"[{color}]{conf}[/{color}]",
        )

    console.print("\n")
    console.print(table)
    console.print("\n" + "─" * 80)

# queen/technicals/signals/tactical/meta_introspector.py
from __future__ import annotations

import os

import polars as pl
from queen.helpers.common import parse_utc_expr
from rich.console import Console
from rich.table import Table

console = Console()

MEMORY_LOG = "queen/data/runtime/logs/meta_memory_log.csv"
DRIFT_LOG = "queen/data/runtime/logs/meta_drift_log.csv"


def _load_csv(path: str) -> pl.DataFrame:
    return pl.read_csv(path) if os.path.exists(path) else pl.DataFrame()


def _parse_ts(df: pl.DataFrame, col: str = "timestamp") -> pl.DataFrame:
    if col not in df.columns or df.is_empty():
        return df
    return df.with_columns(parse_utc_expr(pl.col(col)).alias(col))


def run_meta_introspector():
    console.rule("[bold cyan]🧠 Phase 6.3 — Tactical Meta Introspector")
    mem = _parse_ts(_load_csv(MEMORY_LOG))
    drift = _parse_ts(_load_csv(DRIFT_LOG))
    if mem.is_empty():
        console.print("[Introspect] no memory snapshots to analyze")
        return None

    tbl = Table(title="🧬 Meta Memory — Last 10", header_style="bold cyan")
    for c in (
        "timestamp",
        "model_version",
        "top_feature",
        "top_weight",
        "drift_threshold",
    ):
        if c in mem.columns:
            tbl.add_column(c)
    for row in mem.sort("timestamp").tail(10).iter_rows(named=True):
        tbl.add_row(*[str(row.get(c, "")) for c in tbl.columns])
    console.print(tbl)

    if not drift.is_empty() and "timestamp" in drift.columns:
        joined = mem.join_asof(drift, on="timestamp", strategy="backward")
        console.print("[green]✅ Introspection join complete[/green]")
        return joined
    return mem


if __name__ == "__main__":
    run_meta_introspector()

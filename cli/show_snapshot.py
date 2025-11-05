#!/usr/bin/env python3
# queen/cli/show_snapshot.py — view latest tactical snapshot
from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
from queen.helpers import io
from queen.settings import settings as SETTINGS
from rich.console import Console
from rich.table import Table

console = Console()


def _load_snapshot() -> pl.DataFrame:
    p = SETTINGS.PATHS["SNAPSHOTS"] / "tactical_snapshot.parquet"
    pl_df = io.read_parquet(p)
    if pl_df.is_empty():
        # try .latest pointer/copy (created by meta_strategy_cycle)
        latest = p.with_name("tactical_snapshot.latest.parquet")
        if latest.exists():
            return io.read_parquet(latest)
    return pl_df


def _fmt_row(row: dict) -> list[str]:
    return [
        row.get("symbol", ""),
        row.get("timeframe", ""),
        f"{row.get('Tactical_Index',0):.1f}",
        f"{row.get('strategy_score',0):.2f}",
        row.get("bias", ""),
        "✓" if row.get("entry_ok") else "—",
        "✓" if row.get("exit_ok") else "—",
        row.get("risk_band", ""),
        row.get("Regime_State", ""),
    ]


def main():
    ap = argparse.ArgumentParser(description="Tactical Snapshot viewer")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--sort", default=None)
    ap.add_argument("--desc", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    df = _load_snapshot()
    if df.is_empty():
        print("⚠️ No snapshot found yet. Run meta cycle first.")
        return

    if args.symbol:
        df = df.filter(pl.col("symbol") == args.symbol)

    if args.sort and args.sort in df.columns:
        df = df.sort(args.sort, descending=args.desc)

    if df.is_empty():
        msg = "⚠️ No rows match your filter"
        if args.symbol:
            msg += f" (symbol={args.symbol})"
        print(msg + ".")
        return

    # columns used in your screenshot
    cols = [
        "symbol",
        "timeframe",
        "Tactical_Index",
        "strategy_score",
        "bias",
        "entry_ok",
        "exit_ok",
        "risk_band",
        "Regime_State",
    ]
    cols = [c for c in cols if c in df.columns]
    df = df.select(cols).head(args.limit)

    # pretty table
    console = Console()
    table = Table(title="Tactical Snapshot")
    headers = {
        "symbol": "Symbol",
        "timeframe": "TF",
        "Tactical_Index": "TI",
        "strategy_score": "Score",
        "bias": "Bias",
        "entry_ok": "Entry",
        "exit_ok": "Exit",
        "risk_band": "Risk",
        "Regime_State": "Regime",
    }
    for c in cols:
        table.add_column(headers.get(c, c), justify="left", no_wrap=True)
    for row in df.iter_rows():
        table.add_row(
            *[
                (
                    "—"
                    if v in (None, "", False) and isinstance(v, bool)
                    else str(v).lower()
                    if isinstance(v, bool)
                    else str(v)
                )
                for v in row
            ]
        )
    console.print(table)


if __name__ == "__main__":
    main()

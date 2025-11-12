#!/usr/bin/env python3
# ============================================================
# queen/cli/show_snapshot.py — v1.1 (view latest tactical snapshot)
# ============================================================
from __future__ import annotations

import argparse

import polars as pl
from rich.console import Console
from rich.table import Table

from queen.helpers import io
from queen.settings import settings as SETTINGS

console = Console()


def _load_snapshot() -> pl.DataFrame:
    p = SETTINGS.PATHS["SNAPSHOTS"] / "tactical_snapshot.parquet"
    pl_df = io.read_parquet(p)
    if pl_df.is_empty():
        latest = p.with_name("tactical_snapshot.latest.parquet")
        if latest.exists():
            return io.read_parquet(latest)
    return pl_df


def main():
    ap = argparse.ArgumentParser(description="Tactical Snapshot viewer")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--sort", default=None)
    ap.add_argument("--desc", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    df = _load_snapshot()
    if df.is_empty():
        console.print("⚠️ No snapshot found yet. Run meta cycle first.")
        return

    if args.symbol:
        df = df.filter(pl.col("symbol") == args.symbol)

    if args.sort and args.sort in df.columns:
        df = df.sort(args.sort, descending=args.desc)

    if df.is_empty():
        msg = "⚠️ No rows match your filter"
        if args.symbol:
            msg += f" (symbol={args.symbol})"
        console.print(msg + ".")
        return

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

    table = Table(title="Tactical Snapshot", expand=True)
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
        pretty = []
        for v in row:
            if isinstance(v, bool):
                pretty.append("✓" if v else "—")
            elif v is None or v == "":
                pretty.append("—")
            else:
                pretty.append(str(v))
        table.add_row(*pretty)

    console.print(table)


if __name__ == "__main__":
    main()

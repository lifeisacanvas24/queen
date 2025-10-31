#!/usr/bin/env python3
# ============================================================
# queen/cli/list_master.py — Show/save the master index
# ============================================================
from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
from queen.technicals.master_index import master_index
from rich.console import Console
from rich.table import Table

console = Console()


def _print(df: pl.DataFrame, *, grep: str | None):
    view = df
    if grep:
        patt = grep.lower()
        view = view.filter(
            pl.any_horizontal(
                pl.col("kind").str.contains(patt),
                pl.col("name").str.contains(patt),
                pl.col("module").str.contains(patt),
            )
        )

    if view.is_empty():
        console.print("⚪ No entries.")
        return

    t = Table(
        title="📒 Master Index — Indicators / Signals / Patterns",
        header_style="bold cyan",
        expand=True,
    )
    for col in ["kind", "name", "module"]:
        t.add_column(col)
    for row in view.iter_rows(named=True):
        t.add_row(str(row["kind"]), str(row["name"]), str(row["module"]))
    console.print(t)
    console.print(f"Total: {view.height}")


def _save(df: pl.DataFrame, out: str):
    outp = Path(out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    if outp.suffix.lower() == ".csv":
        df.write_csv(outp)
    elif outp.suffix.lower() in (".parquet", ".pq"):
        df.write_parquet(outp)
    elif outp.suffix.lower() == ".json":
        df.write_json(outp)
    else:
        # plain text
        lines = ["KIND\tNAME\tMODULE"]
        for r in df.iter_rows(named=True):
            lines.append(f"{r['kind']}\t{r['name']}\t{r['module']}")
        outp.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"💾 Saved → {outp}")


def main():
    ap = argparse.ArgumentParser(description="List master index of technicals.")
    ap.add_argument("--grep", help="filter by substring", default=None)
    ap.add_argument(
        "--save", help="path to save (.csv/.json/.parquet or .txt)", default=None
    )
    ap.add_argument("--json", action="store_true", help="print JSON to stdout")
    args = ap.parse_args()

    df = master_index()
    if args.json:
        console.print(df.write_json(), soft_wrap=True)
        return

    _print(df, grep=args.grep)
    if args.save:
        _save(df, args.save)


if __name__ == "__main__":
    main()

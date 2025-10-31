#!/usr/bin/env python3
# ============================================================
# queen/cli/list_technicals.py — v1.0 (Master index CLI)
# ============================================================
from __future__ import annotations

import argparse
import json
import sys

from queen.technicals.master_index import build_master_index


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m queen.cli.list_technicals",
        description="List all discovered indicators, signals, and patterns.",
    )
    p.add_argument(
        "--kind",
        choices=["indicator", "signal", "pattern", "all"],
        default="all",
        help="Filter by kind.",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    p.add_argument(
        "--names", action="store_true", help="Print only names (one per line)."
    )
    return p.parse_args()


def main() -> int:
    df = build_master_index()
    if df.is_empty():
        print("⚠️ No technicals discovered.")
        return 0

    args = parse_args()
    out = df if args.kind == "all" else df.filter(df["kind"] == args.kind)

    if args.names:
        for n in out["name"].to_list():
            print(n)
        return 0

    if args.json:
        print(out.to_pandas().to_json(orient="records"))  # compact JSON
        return 0

    # Pretty table without external deps
    widths = {
        "kind": max(4, max(len(str(x)) for x in out["kind"])),
        "name": max(4, max(len(str(x)) for x in out["name"])),
        "module": max(6, max(len(str(x)) for x in out["module"])),
    }
    header = f"{'KIND'.ljust(widths['kind'])}  {'NAME'.ljust(widths['name'])}  MODULE"
    print(header)
    print("-" * len(header))
    for r in out.iter_rows(named=True):
        print(
            f"{str(r['kind']).ljust(widths['kind'])}  "
            f"{str(r['name']).ljust(widths['name'])}  "
            f"{str(r['module'])}"
        )
    print(f"\nTotal: {len(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

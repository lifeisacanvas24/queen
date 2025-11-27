#!/usr/bin/env python3
# ============================================================
# queen/cli/fundamentals_cli.py — v1.0
# CLI: print fundamentals + intrinsic score for a symbol
# ============================================================
from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from queen.helpers.logger import log
from queen.settings.settings import PATHS
from queen.technicals.fundamentals_score_engine import score_from_processed


def main():
    ap = argparse.ArgumentParser("queen fundamentals")
    ap.add_argument("symbol", help="NSE symbol (e.g., GROWW)")
    ap.add_argument("--processed-dir", default=str(PATHS["FETCH_OUTPUTS"] / "fundamentals"),
                    help="Directory containing processed fundamentals JSONs")
    args = ap.parse_args()

    processed_dir = Path(args.processed_dir)
    sym = args.symbol.upper().strip()

    if not processed_dir.exists():
        log(f"[FUND-CLI] processed dir missing: {processed_dir}", "ERROR")
        return

    df = score_from_processed(processed_dir)

    out = df.filter(pl.col("Symbol") == sym)
    if out.is_empty():
        print(f"❌ No fundamentals for {sym}")
        return

    print(out)


if __name__ == "__main__":
    main()

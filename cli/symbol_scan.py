#!/usr/bin/env python3
# ============================================================
# queen/cli/symbol_scan.py — v1.1 (Terminal/cron wrapper)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, List

from queen.alerts.rules import load_rules
from queen.helpers.logger import log
from queen.services.symbol_scan import run_symbol_scan


def _print_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("(no results)")
        return

    cols = ["SYMBOL", "TIMEFRAME", "RULE", "OK", "META"]
    widths = [10, 9, 35, 2, 69]
    headers = [f"{c:<{w}}" for c, w in zip(cols, widths)]
    print(" ".join(headers))
    print("-" * (sum(widths) + len(widths) - 1))

    for r in rows:
        line = [
            f"{str(r.get('symbol','')):<{widths[0]}}",
            f"{str(r.get('timeframe','')):<{widths[1]}}",
            f"{str(r.get('rule','')):<{widths[2]}}",
            f"{'✓' if r.get('ok') else '':<{widths[3]}}",
            f"{json.dumps(r.get('meta', {}), ensure_ascii=False)[:widths[4]]:<{widths[4]}}",
        ]
        print(" ".join(line))


async def _amain(args: argparse.Namespace) -> int:
    rules = load_rules(args.rules)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    # optional filter: only rules for those symbols
    rules = [r for r in rules if r.symbol in set(symbols)]

    results = await run_symbol_scan(symbols, rules, bars=args.bars)

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.format == "ndjson":
        for r in results:
            print(json.dumps(r, ensure_ascii=False))
    else:
        _print_table(results)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Symbol scanner (rules-driven, same core as server cockpit)."
    )
    p.add_argument("--rules", required=True, help="Path to YAML rules file")
    p.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated symbols (e.g., BSE,NETWEB,GODFRYPHLP)",
    )
    p.add_argument("--bars", type=int, default=150, help="Bars per TF (floor)")
    p.add_argument(
        "--format",
        choices=["table", "json", "ndjson"],
        default="table",
        help="Output format",
    )
    args = p.parse_args()

    try:
        raise SystemExit(asyncio.run(_amain(args)))
    except KeyboardInterrupt:
        log.info("Interrupted.")
        raise SystemExit(130)


if __name__ == "__main__":
    main()

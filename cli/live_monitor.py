#!/usr/bin/env python3
# ============================================================
# queen/cli/live_monitor.py — v1.0 (console live dashboard)
# ============================================================
from __future__ import annotations

import argparse
import asyncio

from queen.monitor.live_engine import MonitorConfig, run_live_console


def main():
    p = argparse.ArgumentParser(description="Live Intraday Monitor (console)")
    p.add_argument(
        "--symbols", nargs="+", required=True, help="e.g. NETWEB GODFRYPHLP FORCEMOT"
    )
    p.add_argument("--interval", type=int, default=15, help="minutes (default 15)")
    p.add_argument("--view", choices=["compact", "expanded", "both"], default="both")
    args = p.parse_args()
    cfg = MonitorConfig(
        symbols=args.symbols, interval_min=args.interval, view=args.view
    )
    asyncio.run(run_live_console(cfg))


if __name__ == "__main__":
    main()

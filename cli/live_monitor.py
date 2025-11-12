#!/usr/bin/env python3
# ============================================================
# queen/cli/live_monitor.py — v1.1 (Console Live Dashboard)
# ============================================================
from __future__ import annotations

import argparse
import asyncio

try:
    from queen.daemons.live_engine import MonitorConfig, run_live_console
except ImportError as e:
    print(f"[ImportError] Missing daemon dependency: {e}")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Live Intraday Monitor (console)")
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Symbols to monitor, e.g. NETWEB GODFRYPHLP FORCEMOT",
    )
    parser.add_argument("--interval", type=int, default=15, help="Interval in minutes (default: 15)")
    parser.add_argument("--view", choices=["compact", "expanded", "both"], default="both")
    args = parser.parse_args()

    cfg = MonitorConfig(symbols=args.symbols, interval_min=args.interval, view=args.view)
    asyncio.run(run_live_console(cfg))


if __name__ == "__main__":
    main()

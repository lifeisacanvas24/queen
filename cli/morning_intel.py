#!/usr/bin/env python3
# ============================================================
# queen/cli/morning_intel.py — v1.1 (Run next-session forecast once)
# ============================================================
from __future__ import annotations

import argparse
from datetime import date

try:
    from queen.daemons.morning_intel import run_cli
except ImportError as e:
    print(f"[ImportError] Missing daemon dependency: {e}")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Queen Next-Session Forecast (actionable)")
    parser.add_argument("--date", help="YYYY-MM-DD (next session). Default: tomorrow", default=None)
    args = parser.parse_args()

    next_d = date.fromisoformat(args.date) if args.date else None
    run_cli(next_d)
    print("✅ Morning Intelligence run completed.")


if __name__ == "__main__":
    main()

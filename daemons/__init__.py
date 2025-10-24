#!/usr/bin/env python3
# ============================================================
# queen/daemons/__init__.py — v3.0 (Subcommands Only)
# ============================================================
"""Queen Daemon Manager (forward-compatible)

Usage:
  python -m queen.daemons list
  python -m queen.daemons clock [clock-args...]
  python -m queen.daemons scheduler [scheduler-args...]
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
from typing import List

REGISTERED_DAEMONS = {
    "scheduler": "queen.daemons.scheduler",
    "clock": "queen.daemons.clock_daemon",
    "alert": "queen.daemons.alert_daemon",
}


def _list_daemons() -> None:
    print("📜 Available Queen Daemons:")
    for name in REGISTERED_DAEMONS:
        print(f"  • {name}")


def _run_child(modpath: str, child_argv: List[str]) -> None:
    mod = importlib.import_module(modpath)
    run_cli = getattr(mod, "run_cli", None)
    if callable(run_cli):
        sig = inspect.signature(run_cli)
        # If child accepts argv, pass it; else patch sys.argv temporarily
        if len(sig.parameters) == 1:
            return run_cli(child_argv)
        old = sys.argv[:]
        try:
            sys.argv = [modpath] + child_argv
            return run_cli()
        finally:
            sys.argv = old
    print(f"⚠️ Daemon module '{modpath}' has no run_cli()")
    sys.exit(1)


def run_cli(argv: list[str] | None = None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(description="Queen Daemon Manager", add_help=True)
    sub = parser.add_subparsers(dest="cmd", metavar="{list,clock,scheduler,alert}")

    sub.add_parser("list", help="List available daemons")
    sub.add_parser("clock", help="Run the market clock daemon")
    sub.add_parser("scheduler", help="Run the fetch scheduler daemon")
    sub.add_parser("alert", help="Run the alert daemon")

    # Forward unknown args to the child daemon
    args, unknown = parser.parse_known_args(argv)

    if args.cmd in (None, "list"):
        if args.cmd is None:
            parser.print_help()
        else:
            _list_daemons()
        return

    name = args.cmd
    modpath = REGISTERED_DAEMONS.get(name)
    if not modpath:
        parser.error(f"Unknown command: {name}")

    print(f"🚀 Launching Queen Daemon → {name}")
    _run_child(modpath, unknown)


if __name__ == "__main__":
    run_cli()

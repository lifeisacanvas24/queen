#!/usr/bin/env python3
# ============================================================
# queen/daemons/__init__.py — v3.1 (Subcommands + Aliases + Safe import)
# ============================================================
"""Queen Daemon Manager (forward-compatible)

Usage:
  python -m queen.daemons list
  python -m queen.daemons clock [clock-args...]
  python -m queen.daemons scheduler [scheduler-args...]
  python -m queen.daemons alert [alert-args...]
  python -m queen.daemons alert2 [alert_v2-args...]
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
from typing import Callable

# module path registry (add aliases here)
REGISTERED_DAEMONS: dict[str, str] = {
    "scheduler": "queen.daemons.scheduler",
    "clock": "queen.daemons.clock_daemon",
    "alert": "queen.daemons.alert_daemon",
    "alert2": "queen.daemons.alert_v2",  # ← v2 alerts engine
}

__version__ = "3.1.0"


def _list_daemons() -> None:
    print("📜 Available Queen Daemons:")
    for name, modpath in REGISTERED_DAEMONS.items():
        print(f"  • {name:<9} → {modpath}")


def _run_child(modpath: str, child_argv: list[str]) -> None:
    try:
        mod = importlib.import_module(modpath)
    except ModuleNotFoundError as e:
        print(f"❌ Cannot import '{modpath}' → {e}")
        sys.exit(2)

    run_cli: Callable[..., None] | None = getattr(mod, "run_cli", None)
    if not callable(run_cli):
        print(f"⚠️ Daemon module '{modpath}' has no run_cli()")
        sys.exit(1)

    sig = inspect.signature(run_cli)
    try:
        if len(sig.parameters) == 1:
            # child expects argv explicitly
            run_cli(child_argv)
        else:
            # child parses sys.argv itself
            old_argv = sys.argv[:]
            try:
                sys.argv = [modpath] + child_argv
                run_cli()
            finally:
                sys.argv = old_argv
    except SystemExit as e:
        # propagate child's exit code cleanly
        code = e.code if isinstance(e.code, int) else 0
        sys.exit(code)


def run_cli(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        description="Queen Daemon Manager",
        add_help=True,
        epilog="Examples:\n"
        "  python -m queen.daemons list\n"
        "  python -m queen.daemons clock --interval 1 --log\n"
        "  python -m queen.daemons scheduler --mode intraday --interval-minutes 5\n"
        "  python -m queen.daemons alert2 --rules rules.yml --debug",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    sub = parser.add_subparsers(
        dest="cmd", metavar="{list,clock,scheduler,alert,alert2}"
    )
    sub.add_parser("list", help="List available daemons")
    sub.add_parser("clock", help="Run the market clock daemon")
    sub.add_parser("scheduler", help="Run the fetch scheduler daemon")
    sub.add_parser("alert", help="Run the legacy alert daemon")
    sub.add_parser("alert2", help="Run the Alert V2 daemon")

    args, unknown = parser.parse_known_args(argv)

    if getattr(args, "version", False):
        print(__version__)
        return

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

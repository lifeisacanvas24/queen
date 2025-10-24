#!/usr/bin/env python3
# ============================================================
# queen/daemons/clock_daemon.py — Market Clock Daemon (v1.3)
# ============================================================
"""Continuously emits market ticks using queen.helpers.market.MarketClock.
✅ Supports --force-live (bypass holiday/weekend pause)
✅ JSONL tick logging (--log --log-file /path/to/file)
✅ Terminal dashboard (Rich)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import time
from pathlib import Path

from queen.helpers import market
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Queen Market Clock Daemon")
    p.add_argument("--interval", type=int, default=1, help="Clock interval in minutes")
    p.add_argument(
        "--force-live", action="store_true", help="Force run even on holidays/weekends"
    )
    p.add_argument("--log", action="store_true", help="Enable JSONL tick logging")
    p.add_argument(
        "--log-file",
        type=str,
        default="./clock_ticks.jsonl",
        help="Path to JSONL log file",
    )
    return p


def build_table(state, tick_count, runtime):
    table = Table(
        title="[green]Queen Market Clock Daemon[/green]",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Field", justify="left", style="bold cyan")
    table.add_column("Value", justify="right", style="bold white")

    table.add_row("🕒 Time", state.get("timestamp", "--:--:--"))
    gate = state.get("gate", "INIT")
    gate_display = (
        "[red]HOLIDAY[/red]"
        if "HOLIDAY" in gate
        else "[yellow]PRE[/yellow]"
        if "PRE" in gate
        else "[green]LIVE[/green]"
        if "LIVE" in gate
        else "[cyan]POST[/cyan]"
        if "POST" in gate
        else gate
    )
    table.add_row("📅 Gate", gate_display)
    table.add_row("📊 Session", state.get("session", "N/A"))
    table.add_row("📈 Market", "🟩 OPEN" if state.get("is_open") else "🔒 CLOSED")
    table.add_row("⏱️ Ticks", str(tick_count))
    table.add_row("🧭 Runtime", f"{int(runtime)}s")

    return Panel(table, border_style="cyan", expand=False)


async def run_daemon(args: argparse.Namespace):
    start_time = time.time()
    tick_count = 0
    state = {"gate": "INIT", "session": "N/A", "is_open": False}

    clock = market.MarketClock(
        interval=args.interval,
        name="ClockDaemon",
        verbose=False,
        auto_pause=not args.force_live,
    )
    queue = clock.subscribe("ClockDaemonUI")

    console.print(
        "\n[green]────────── 💹 Queen Market Clock Daemon Started ──────────[/green]"
    )
    console.print(
        f"[grey70]Interval:[/] {args.interval}m | "
        f"[grey70]Force-Live:[/] {'[green]True[/green]' if args.force_live else '[red]False[/red]'} | "
        f"[grey70]Log:[/] {'[green]True[/green]' if args.log else '[red]False[/red]'} | "
        f"[grey70]File:[/] {args.log_file if args.log else 'N/A'}"
    )

    log_path = Path(args.log_file)
    if args.log:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            log_path.write_text("")

    async def tick_listener(live: Live):
        nonlocal tick_count, state
        while True:
            tick = await queue.get()
            tick_count += 1
            now = dt.datetime.now(market.MARKET_TZ)
            state = market.get_market_state()
            runtime = time.time() - start_time
            live.update(build_table(state, tick_count, runtime))

            if args.log:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "timestamp": tick["timestamp"].isoformat(),
                                "gate": tick["gate"],
                                "session": tick["session"],
                                "is_open": tick["is_open"],
                            }
                        )
                        + "\n"
                    )

    with Live(build_table(state, 0, 0), refresh_per_second=1, console=console) as live:
        await asyncio.gather(clock.start(), tick_listener(live))


def run_cli(argv: list[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        asyncio.run(run_daemon(args))
    except KeyboardInterrupt:
        console.print("\n[red]🛑 Interrupted by user.[/red]")


if __name__ == "__main__":
    run_cli()

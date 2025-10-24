#!/usr/bin/env python3
# ============================================================
# queen/tests/market_playback.py — Simulated Market Day Playback (v1.7)
# ============================================================
"""Simulates a full market day (PRE → LIVE → POST) with CLI flags.
---------------------------------------------------------------
Now includes:
✅ --force-live   → Override holidays/weekends
✅ --no-clock     → Skip MarketClock for pure playback
✅ Live tick counter in footer
✅ Color-coded gate legend
✅ Column-aligned, terminal-polished output
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt

from queen.helpers import market
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


# ------------------------------------------------------------
# 🎬 CLI Argument Parser
# ------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="🎞️  Simulate a full NSE market day (PRE → LIVE → POST)"
    )
    parser.add_argument("--date", type=str, default=dt.date.today().isoformat())
    parser.add_argument(
        "--speed", type=int, default=2, help="Minutes per simulated step (default=2)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=1,
        help="MarketClock interval in minutes (default=1)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Accelerate playback (0.25s instead of 0.5s)",
    )
    parser.add_argument(
        "--force-live", action="store_true", help="Force market open (ignore holidays)"
    )
    parser.add_argument(
        "--no-clock",
        action="store_true",
        help="Skip MarketClock daemon for playback-only mode.",
    )
    return parser.parse_args()


# ------------------------------------------------------------
# 🎨 Colored UX Helpers
# ------------------------------------------------------------
def style_gate(gate: str) -> Text:
    if "HOLIDAY" in gate:
        return Text(gate, style="bold red")
    if "PRE" in gate:
        return Text(gate, style="bold yellow")
    if "LIVE" in gate:
        return Text(gate, style="bold green")
    if "POST" in gate:
        return Text(gate, style="bold cyan")
    return Text(gate, style="dim white")


def show_legend():
    table = Table(show_header=False, box=None)
    table.add_row(
        Text("🟥  HOLIDAY", style="red"),
        Text("🟨  PRE-MARKET", style="yellow"),
        Text("🟩  LIVE", style="green"),
        Text("🩵  POST", style="cyan"),
    )
    console.print(
        Panel(table, title="[bold]Legend[/]", expand=False, border_style="dim")
    )


# ------------------------------------------------------------
# 🕰️ Simulated Market Playback
# ------------------------------------------------------------
def print_state(now: dt.datetime, force_live: bool):
    """Render playback state line with aligned columns."""
    gate = market.get_gate(now)
    is_open = market.is_market_open(now)
    session = market.current_session(now)

    if force_live:
        gate = "LIVE / WORKING"
        is_open = True

    note = (
        "📈 Market LIVE"
        if is_open
        else ("⏳ Awaiting open" if "PRE" in gate else "🔒 Market Closed")
    )

    # Alignment
    time_str = now.strftime("%H:%M")
    gate_str = gate.ljust(15)
    session_str = session.ljust(12)

    console.print(
        f"[{time_str}] ",
        style_gate(gate_str),
        f"| Session: {Text(session_str, style='cyan')} | State: {note}",
        sep="",
    )


async def simulate_day_playback(
    sim_date: dt.date, step_minutes: int, fast: bool, force_live: bool
):
    """Simulate full trading day transitions."""
    start = dt.datetime.combine(sim_date, dt.time(8, 55))
    end = dt.datetime.combine(sim_date, dt.time(15, 45))
    step = dt.timedelta(minutes=step_minutes)
    delay = 0.25 if fast else 0.5

    console.print("\n🎞️  [bold cyan]Simulated Market Day Playback[/]")
    console.print("------------------------------------------------------------")
    console.print(
        f"Simulated Date: {sim_date} | Step: {step_minutes}m | Delay: {delay}s\n"
    )
    show_legend()

    tick_counter = 0
    now = start
    while now <= end:
        print_state(now, force_live)
        now += step
        tick_counter += 1
        await asyncio.sleep(delay)

    console.print(
        f"\n✅ [bold green]Simulation complete — {tick_counter} steps covered.[/]"
    )


# ------------------------------------------------------------
# ⚡ Combined Async Test (MarketClock + Playback)
# ------------------------------------------------------------
async def run_combined_playback(
    sim_date: dt.date,
    step: int,
    interval: int,
    fast: bool,
    force_live: bool,
    no_clock: bool,
):
    """Run MarketClock and playback together."""
    tick_count = 0
    clock = None

    if not no_clock:
        clock = market.MarketClock(
            interval=interval, name="PlaybackClock", verbose=False
        )
        queue = clock.subscribe("SimFetcher")

        async def tick_listener():
            nonlocal tick_count
            while True:
                tick = await queue.get()
                tick_count += 1
                ts = tick["timestamp"].strftime("%H:%M:%S")
                session = tick["session"]
                console.print(f"   ⏱️ [bold blue]Tick[/] → {ts} | Session={session}")

        await asyncio.gather(
            clock.start(),
            tick_listener(),
            simulate_day_playback(sim_date, step, fast, force_live),
        )
    else:
        await simulate_day_playback(sim_date, step, fast, force_live)

    console.print(f"\n🕒 [bold cyan]Total ticks processed:[/] {tick_count}")


# ------------------------------------------------------------
# 🧠 Entry Point
# ------------------------------------------------------------
if __name__ == "__main__":
    args = parse_args()
    sim_date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()

    console.print("[bold magenta]🧩 Queen Market Playback — CLI Mode[/]")
    console.print("[dim]============================================[/]")
    console.print(f"[cyan]Date:[/] {sim_date}")
    console.print(
        f"[cyan]Speed:[/] {args.speed}m per step | "
        f"[cyan]Clock Interval:[/] {args.interval}m | "
        f"[cyan]Fast:[/] {args.fast} | "
        f"[cyan]Force-Live:[/] {args.force_live} | "
        f"[cyan]No-Clock:[/] {args.no_clock}"
    )
    console.print("[dim]============================================[/]\n")

    try:
        asyncio.run(
            run_combined_playback(
                sim_date,
                args.speed,
                args.interval,
                args.fast,
                args.force_live,
                args.no_clock,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[bold red][🛑] Interrupted by user.[/]")

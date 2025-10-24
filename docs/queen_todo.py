#!/usr/bin/env python3
# ============================================================
# Queen Quant — Project Roadmap Tracker (v1.2)
# ============================================================
"""A standalone executable roadmap tracker for the Queen Quant stack.
✅ Prints active and planned tasks in colorized Rich tables.
✅ Exports to JSON / Markdown for persistence.
✅ Keeps a single source of truth for all modules (settings, market, daemons, regimes, utils).
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ------------------------------------------------------------
# 🧭 “Sprint” snapshot (today vs tomorrow)
# ------------------------------------------------------------
TODAY_DONE = [
    "Upstox fetcher v9.6 — full timeframe support (schema-driven) + DEFAULT_INTERVALS",
    "Schema adapter — settings TZ in _safe_parse; interval introspection + validate_interval()",
    "market.py v9.2 — parameterized market_gate, accurate session flags, current_historical_service_day()",
    "fetch_router — logs effective historical service day; honors BATCH_SIZE/EXPORT_FORMAT",
    "Alerting v1 — alert daemon + FastAPI SSE + Bulma UI; live card verified",
    "CLI guard — same-day EOD warning for daily fetches",
]

TOMORROW_PLAN = [
    "Alert daemon v2 — YAML/JSON rules, SMA/RSI/VWAP, cooldown/state, JSONL rotation",
    "Config cleanup — map WEEKLY/PORTFOLIO/APPROVED to monthly instruments; clear instrument cache once",
    "Scheduler/Router smoke — --once and --auto runs; import shim sanity",
    "MarketClock UX — summary footer (uptime, ticks, phases) on exit",
    "Legacy utils audit — prune/merge remaining helpers into queen/helpers",
]

# ------------------------------------------------------------
# 🧭 ROADMAP DEFINITION (status-refreshed)
# ------------------------------------------------------------
ROADMAP = {
    "Environment & Settings System": {
        "status": "🟦 Planned",
        "goal": "Integrate global DotDict proxy and environment awareness.",
        "tasks": [
            "Integrate settings_proxy into queen.settings for dot-access.",
            "Auto-detect active environment (dev/staging/prod).",
            "Prepare for optional live reload on config changes.",
        ],
        "deliverable": "SETTINGS proxy fully live across daemons.",
        "next": "Tactical Regime Integration",
    },
    "Market System": {
        "status": "🟢 In Progress",
        "goal": "Finalize MarketClock Daemon (v1.2) and extend visual + logging features.",
        "tasks": [
            "Integrate Force-Live fix (disable auto-pause). ✅ via parameterized market_gate",
            "Add JSONL logging per tick (--log --log-file). ✅ (present in daemon logs)",
            "Display runtime + tick count in Rich table. ✅",
            "Add summary output on exit (uptime, ticks, session coverage). ⏳",
            "Add colored session/gate states (🟥 HOLIDAY, 🟩 LIVE, 🟨 PRE). ✅",
        ],
        "enhancements": [
            {
                "version": "v1.2",
                "title": "Enhanced Daemon Output",
                "items": [
                    "Add summary footer below stop event with uptime/ticks/phases. ⏳",
                    "Improve live colorization for gate/session fields. ✅",
                ],
                "status": "🟡 Queued",
                "target": "Next minor release",
            }
        ],
        "deliverable": "clock_daemon.py v1.2 — colorized, summarized, production heartbeat daemon.",
        "next": "settings_proxy integration",
    },
    "Regime Layer": {
        "status": "🟢 In Progress",
        "goal": "Adaptive tactical blending (RScore / VolX / LBX) via tactical_regime_adapter.",
        "tasks": [
            "Implement tactical_regime_adapter.py (✅ Done).",
            "Load regimes from regimes.py instead of JSON (✅ Done).",
            "Add auto-regime switching using live metrics (Next v1.2).",
            "Integrate with model runners for dynamic scaling.",
        ],
        "deliverable": "queen/helpers/tactical_regime_adapter.py",
        "next": "Integration Layer",
    },
    "Fetcher & Utils Refactor": {
        "status": "🟢 In Progress",
        "goal": "Refactor and unify quant/utils into the DRY Polars-based helpers stack.",
        "tasks": [
            "Merge schema.py + dataframe.py + api_schema.py → schema_adapter.py. ✅",
            "Implement instruments.py (foundation for Fetcher subsystem). ✅",
            "Audit legacy utils: logs/io/scheduler/rate_limiter/path_manager/config_proxy/config_watcher/cache/common. ⏳",
            "Eliminate redundancy; keep DRY + settings-driven + Polars-only utilities. ⏳",
            "Migrate validated utils into queen/helpers/ with clear names. ⏳",
        ],
        "notes": "Core fetcher/helpers are consolidated; remaining utils slated for pruning.",
        "deliverable": "Unified utils refactor — ready for data fetcher integration.",
        "next": "Fetcher subsystem polishing",
    },
    "Fetcher Subsystem (Upstox)": {
        "status": "🟢 Complete (v9.6)",
        "goal": "Schema-driven, multi-timeframe Upstox fetcher with strict validation.",
        "tasks": [
            "Full timeframe support (minutes/hours/days/weeks/months). ✅",
            "Schema-only base URL + error mapping. ✅",
            "Interval validation against supported_timelines. ✅",
            "Router logging of effective historical service day. ✅",
        ],
        "deliverable": "queen/fetchers/upstox_fetcher.py (v9.6) + fetch_router integration",
        "next": "Indicator-aware fetch (optional precompute)",
    },
    "Alerting & UI": {
        "status": "🟢 Complete (v1)",
        "goal": "Real-time alerts via daemon → JSONL → SSE → Bulma UI.",
        "tasks": [
            "Alert daemon v1 with simple price rules + JSONL sink. ✅",
            "FastAPI/SSE stream + Bulma UI page. ✅",
            "Live verification with PGIL card. ✅",
            "Webhook/WS optional sinks. ⏳ (deferred to v2)",
        ],
        "deliverable": "queen/daemons/alert.py + queen/server (SSE) + Bulma UI",
        "next": "Alert v2 (multi-rule + indicators + cooldown)",
    },
    "Integration & Dashboard": {
        "status": "🔵 Queued",
        "goal": "Unify all daemons + display dashboard in real time.",
        "tasks": [
            "Integrate MarketClock feed across daemons. ✅",
            "Add dashboard mode (--dashboard) using rich.live. ⏳",
            "Implement regime timeline visualization. ⏳",
        ],
        "deliverable": "Queen Market Console v2.0 — live quant terminal.",
        "next": "Daemon Registry",
    },
}


# ------------------------------------------------------------
# 📁 STATUS MAP HELPER
# ------------------------------------------------------------
def get_task_status_map():
    """Return a {filename: status_icon} dict for visualization."""
    task_map = {}
    for section, meta in ROADMAP.items():
        deliverable = meta.get("deliverable", "")
        if deliverable:
            filename = deliverable.split()[-1]
            task_map[filename] = meta.get("status", "⚪")
        for task in meta.get("tasks", []):
            if ".py" in task:
                filename = task.split()[-1]
                task_map[filename] = meta.get("status", "⚪")
    return task_map


# ------------------------------------------------------------
# 📊 DISPLAY HELPERS
# ------------------------------------------------------------
def _print_sprint_snapshot():
    tbl = Table(show_header=False, expand=False, box=None)
    tbl.add_row(
        "[bold green]✅ Today[/bold green]", "\n".join(f"• {t}" for t in TODAY_DONE)
    )
    tbl.add_row(
        "[bold yellow]🗓️  Tomorrow[/bold yellow]",
        "\n".join(f"• {t}" for t in TOMORROW_PLAN),
    )
    console.print(Panel(tbl, title="[magenta]Sprint Snapshot[/magenta]", expand=False))
    console.print("")


def print_roadmap():
    console.print(
        "\n[bold magenta]👑 Queen Quant Project — Consolidated TODO Roadmap[/bold magenta]\n"
    )
    _print_sprint_snapshot()
    for section, details in ROADMAP.items():
        table = Table(show_header=False, expand=False, box=None)
        table.add_row("📂 [cyan]Section[/cyan]", f"[bold white]{section}[/bold white]")
        table.add_row("🏁 [cyan]Goal[/cyan]", details["goal"])
        table.add_row("📈 [cyan]Status[/cyan]", details["status"])
        table.add_row("🧩 [cyan]Next[/cyan]", details["next"])
        table.add_row("📦 [cyan]Deliverable[/cyan]", details["deliverable"])
        table.add_row(
            "🪶 [cyan]Tasks[/cyan]", "\n".join(f"• {t}" for t in details["tasks"])
        )
        console.print(Panel(table, title=f"[green]{section}[/green]", expand=False))
        console.print("")
    console.print(
        "[yellow]Tip:[/] Run 'python queen/docs/queen_todo.py --export' to save this as roadmap.json.\n"
    )


def export_roadmap():
    out_json = Path("queen/docs/roadmap.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(ROADMAP, indent=2, ensure_ascii=False))
    console.print(f"[green]✅ Exported roadmap to:[/] {out_json.resolve()}")


# ------------------------------------------------------------
# 🧠 ENTRY
# ------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Queen Quant Roadmap Tracker")
    parser.add_argument(
        "--export", action="store_true", help="Export roadmap to JSON file"
    )
    args = parser.parse_args()
    print_roadmap()
    if args.export:
        export_roadmap()

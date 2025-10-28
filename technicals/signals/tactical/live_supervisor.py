# ============================================================
# queen/technicals/signals/tactical/live_supervisor.py
# ------------------------------------------------------------
# 🛰️ Phase 7.2 — Tactical Live Supervisor
# Manages multiple Tactical Live Daemons concurrently with
# health checks, scheduling, metrics, and alert routing.
# ============================================================

import asyncio
import json
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from quant.signals.tactical.tactical_live_daemon import (
    run_daemon,
    save_checkpoint,
    send_alert,
)
from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# 🧩 Config (to later move into config.py)
# ============================================================
SUPERVISOR_CONFIG = "quant/config/supervisor_config.json"
HEALTHCHECK_LOG = "quant/logs/supervisor_health.json"

DEFAULT_CONFIG = {
    "symbols": ["AAPL", "NVDA", "BTCUSD", "ETHUSD"],
    "timeframes": ["5m", "15m", "1h"],
    "max_concurrent": 3,
    "interval_sec": 60 * 60 * 6,  # every 6 hours
    "healthcheck_interval": 60 * 10,  # 10 minutes
    "prometheus_enabled": False,
    "alert_enabled": True,
}


# ============================================================
# 🧩 Load / Save Config
# ============================================================
def load_supervisor_config():
    if os.path.exists(SUPERVISOR_CONFIG):
        with open(SUPERVISOR_CONFIG) as f:
            return json.load(f)
    return DEFAULT_CONFIG


def save_health_status(status: dict):
    os.makedirs(os.path.dirname(HEALTHCHECK_LOG), exist_ok=True)
    with open(HEALTHCHECK_LOG, "w") as f:
        json.dump(status, f, indent=2)


# ============================================================
# 🧠 Supervisor Tasks
# ============================================================
async def run_daemon_task(symbol: str, tf: str, interval: int):
    """Wrap the daemon runner in an async task with supervision."""
    ts = datetime.now(timezone.utc).isoformat()
    console.print(
        f"🚀 Launching daemon for [yellow]{symbol}[/yellow] @ [cyan]{tf}[/cyan]"
    )
    try:
        run_daemon(interval=interval)
        save_checkpoint("success", f"{symbol}:{tf} run completed at {ts}")
        return {"symbol": symbol, "tf": tf, "status": "success", "timestamp": ts}
    except Exception as e:
        err = str(e)
        console.print(f"⚠️ [red]{symbol}:{tf}[/red] failed — {err}")
        send_alert(f"Daemon failure: {symbol}:{tf} — {err}")
        save_checkpoint("failed", err)
        return {
            "symbol": symbol,
            "tf": tf,
            "status": "failed",
            "timestamp": ts,
            "error": err,
        }


# ============================================================
# 🧭 Supervisor Loop
# ============================================================
async def run_supervisor():
    cfg = load_supervisor_config()
    symbols = cfg["symbols"]
    tfs = cfg["timeframes"]
    interval = cfg["interval_sec"]
    max_workers = cfg["max_concurrent"]

    console.rule("[bold magenta]🛰️ Tactical Live Supervisor — Launching Fleet")

    executor = ThreadPoolExecutor(max_workers=max_workers)
    running = True
    cycle = 0

    def handle_sigint(sig, frame):
        nonlocal running
        console.print("\n🛑 SIGINT received — halting supervisor gracefully.")
        running = False

    signal.signal(signal.SIGINT, handle_sigint)

    while running:
        cycle += 1
        console.rule(
            f"[bold cyan]Cycle #{cycle} — {datetime.now(timezone.utc).isoformat()}[/bold cyan]"
        )

        tasks = []
        start_time = time.time()

        # Schedule each daemon run concurrently
        for symbol in symbols:
            for tf in tfs:
                tasks.append(run_daemon_task(symbol, tf, interval))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Record health
        healthy = [
            r for r in results if isinstance(r, dict) and r.get("status") == "success"
        ]
        failed = [
            r for r in results if isinstance(r, dict) and r.get("status") != "success"
        ]

        health_summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": cycle,
            "healthy": len(healthy),
            "failed": len(failed),
            "symbols": len(symbols),
            "timeframes": len(tfs),
            "duration_min": round((time.time() - start_time) / 60, 2),
        }
        save_health_status(health_summary)

        # Display Rich table
        table = Table(
            title="🧩 Supervisor Health Summary", header_style="bold cyan", expand=True
        )
        table.add_column("Symbol")
        table.add_column("TF")
        table.add_column("Status")
        table.add_column("Timestamp")
        for res in results:
            if isinstance(res, dict):
                table.add_row(
                    res.get("symbol", "—"),
                    res.get("tf", "—"),
                    res.get("status", "—"),
                    res.get("timestamp", "—"),
                )
        console.print(table)

        console.print(
            f"💤 Sleeping for {cfg['healthcheck_interval']/60:.1f} min before next supervision check...\n"
        )
        await asyncio.sleep(cfg["healthcheck_interval"])

    console.print("[green]✅ Supervisor stopped gracefully.[/green]")


# ============================================================
# 🧪 Stand-alone Entry
# ============================================================
if __name__ == "__main__":
    try:
        asyncio.run(run_supervisor())
    except KeyboardInterrupt:
        console.print("🛑 Interrupted manually.")

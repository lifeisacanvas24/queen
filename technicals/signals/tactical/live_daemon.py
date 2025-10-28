# ============================================================
# queen/technicals/signals/tactical/live_daemon.py
# ------------------------------------------------------------
# 🧩 Phase 7.1 — Tactical Live Daemon
# Background process that runs the Cognitive Orchestrator
# continuously with resilience, retry logic, and alerts.
# ============================================================

import json
import os
import signal
import time
import traceback
from datetime import datetime, timezone

from quant.signals.tactical.tactical_cognitive_orchestrator import run_cognitive_cycle
from rich.console import Console

console = Console()

# ============================================================
# 🧩 Config (later to move into config.py)
# ============================================================
DAEMON_STATE_FILE = "quant/logs/daemon_state.json"
MAX_RETRIES = 3
RETRY_DELAY = 60 * 5  # 5 min
CHECKPOINT_INTERVAL = 60 * 60 * 6  # every 6 h
ALERT_CHANNEL = None  # placeholder for Slack/email in future


# ============================================================
# 💾 Checkpoint & Alert Helpers
# ============================================================
def save_checkpoint(status: str, details: str = ""):
    os.makedirs(os.path.dirname(DAEMON_STATE_FILE), exist_ok=True)
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "details": details,
    }
    with open(DAEMON_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    console.print(f"🧭 [green]Checkpoint saved:[/green] {status}")


def send_alert(message: str):
    # Hook for integration with Slack/email
    console.print(f"🚨 [red]ALERT:[/red] {message}")
    # (Extendable: push to alerting service)


# ============================================================
# 🔁 Daemon Loop
# ============================================================
def run_daemon(global_health_dfs=None, interval=CHECKPOINT_INTERVAL):
    console.rule("[bold magenta]🛰️ Tactical Live Daemon — Starting")
    running = True
    retry_count = 0

    def handle_sigint(sig, frame):
        nonlocal running
        console.print(
            "\n🛑 [yellow]SIGINT received — shutting down gracefully...[/yellow]"
        )
        save_checkpoint("terminated", "manual stop")
        running = False

    signal.signal(signal.SIGINT, handle_sigint)

    while running:
        try:
            ts = datetime.now(timezone.utc).isoformat()
            console.print(f"\n🚀 [cyan]Cycle start:[/cyan] {ts}")

            run_cognitive_cycle(global_health_dfs)
            save_checkpoint("success", f"Cycle completed at {ts}")
            retry_count = 0

            console.print(
                f"💤 Sleeping for {interval/3600:.1f} h before next cycle...\n"
            )
            time.sleep(interval)

        except Exception as e:
            retry_count += 1
            error_msg = f"Cycle failed (attempt {retry_count}/{MAX_RETRIES}): {e}"
            console.print(f"⚠️ {error_msg}")
            console.print(traceback.format_exc())
            send_alert(error_msg)
            save_checkpoint("error", str(e))

            if retry_count >= MAX_RETRIES:
                send_alert("🚨 Daemon entered fail-safe stop — max retries reached.")
                save_checkpoint("failed", "max retries reached")
                break
            console.print(f"🔁 Retrying in {RETRY_DELAY/60:.1f} min...")
            time.sleep(RETRY_DELAY)

    console.print("🧘 [green]Daemon stopped gracefully.[/green]")


# ============================================================
# 🧪 Stand-alone entry
# ============================================================
if __name__ == "__main__":
    run_daemon()

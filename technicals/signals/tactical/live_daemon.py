#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/live_daemon.py
# ------------------------------------------------------------
# 🛰️ Tactical Live Daemon — settings-driven, resilient runner
# Runs the Cognitive Orchestrator with retries + checkpoints.
# ============================================================

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

import polars as pl  # not strictly needed, but fine to keep for parity

from queen.helpers.logger import log

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None

# --- Settings-driven paths & timing ------------------------------------------
LOG_DIR = (
    SETTINGS.PATHS["LOGS"]
    if SETTINGS
    else os.path.join("queen", "data", "runtime", "logs")
)
os.makedirs(LOG_DIR, exist_ok=True)

DAEMON_STATE_FILE = os.path.join(LOG_DIR, "daemon_state.json")

CFG = (getattr(SETTINGS, "DAEMON", {}) if SETTINGS else {}) or {}
INTERVAL_SEC = int(CFG.get("interval_sec", 6 * 60 * 60))  # default 6h
MAX_RETRIES = int(CFG.get("max_retries", 3))
RETRY_DELAY_SEC = int(CFG.get("retry_delay_sec", 5 * 60))  # default 5m

# Import your orchestrator (new path)
from queen.technicals.signals.tactical.cognitive_orchestrator import run_cognitive_cycle


# --- Helpers -----------------------------------------------------------------
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_checkpoint(status: str, details: str = "") -> None:
    state = {"timestamp": _utc_now(), "status": status, "details": details}
    try:
        with open(DAEMON_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        log.info(
            f"[Daemon] 🧭 Checkpoint saved → {DAEMON_STATE_FILE}",
            extra={"extra": state},
        )
    except Exception as e:
        log.warning(f"[Daemon] Failed to write checkpoint → {e}")


def send_alert(message: str) -> None:
    # Hook for Slack/email in future
    log.error(f"[Daemon][ALERT] {message}")


# --- Core single-cycle runner ------------------------------------------------
def run_daemon_once(global_health_dfs: Dict[str, pl.DataFrame] | None = None) -> bool:
    """Run exactly one cognition cycle; return True on success."""
    ts = _utc_now()
    try:
        log.info(f"[Daemon] 🚀 Cycle start @ {ts}")
        run_cognitive_cycle(global_health_dfs)
        save_checkpoint("success", f"cycle completed at {ts}")
        return True
    except Exception as e:
        err = f"cycle failed: {e}"
        log.error(f"[Daemon] {err}")
        log.error(traceback.format_exc())
        save_checkpoint("error", err)
        send_alert(err)
        return False


# --- Looping daemon ----------------------------------------------------------
def run_daemon(
    global_health_dfs: Dict[str, pl.DataFrame] | None = None,
    interval_sec: int | None = None,
    once: bool = False,
) -> None:
    """Run cognition cycles forever (or once if `once=True`)."""
    interval = int(interval_sec or INTERVAL_SEC)
    retries = 0

    if once:
        run_daemon_once(global_health_dfs)
        return

    log.info("[Daemon] 🛰️ Tactical Live Daemon — starting")
    while True:
        ok = run_daemon_once(global_health_dfs)
        if ok:
            retries = 0
            log.info(f"[Daemon] 💤 Sleeping {interval/3600:.1f} h before next cycle…")
            time.sleep(interval)
            continue

        # Failure handling
        retries += 1
        if retries >= MAX_RETRIES:
            msg = "🚨 Daemon entering fail-safe stop — max retries reached."
            send_alert(msg)
            save_checkpoint("failed", msg)
            break
        backoff = RETRY_DELAY_SEC
        log.warning(
            f"[Daemon] 🔁 Retry {retries}/{MAX_RETRIES} in {backoff/60:.1f} min…"
        )
        time.sleep(backoff)


if __name__ == "__main__":
    # In production: just run_daemon()
    # In tests: run_daemon(once=True)
    run_daemon(once=True)

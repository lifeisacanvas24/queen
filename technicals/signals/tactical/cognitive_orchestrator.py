# ============================================================
# queen/technicals/signals/tactical/cognitive_orchestrator.py
# ------------------------------------------------------------
# 🧠 Tactical Cognitive Orchestrator (Minimal, Forward-Compatible)
# - No legacy quant.* imports
# - Soft-calls our refactored trainers/inference if present
# - Settings-free (can wire later to SETTINGS)
#

"""Contract: single-cycle runner
-----------------------------
`run_cognitive_cycle(...)` MUST perform exactly one cognition pass and return.
It must NOT loop, sleep, or block. Looping/scheduling/backoff belong in:
  • `tactical/live_daemon.py`  → retry + checkpoints (can run once or loop)
  • `tactical/live_supervisor.py` → concurrent single-cycle fan-out

This separation prevents nested sleep-loops and keeps tests deterministic.
"""
#
#
#
# ============================================================

from __future__ import annotations

from datetime import datetime, timezone
from time import sleep

from rich.console import Console

console = Console()


# Soft import helpers
def _maybe(fn):
    try:
        return fn()
    except Exception:
        return None


def _import_inference():
    from queen.technicals.signals.tactical.ai_inference import run_ai_inference

    return run_ai_inference


def _import_trainer():
    from queen.technicals.signals.tactical.ai_trainer import run_training

    return run_training


def _import_recommender():
    from queen.technicals.signals.tactical.ai_recommender import recommend_from_log

    return recommend_from_log


def _safe_run(label: str, f, *args, **kwargs):
    try:
        console.rule(f"[bold cyan]{label}")
        out = f(*args, **kwargs)
        console.print(f"✅ {label} completed\n")
        return out
    except Exception as e:
        console.print(f"⚠️ [{label}] Skipped: {e}\n")
        return None


# ── One cycle ───────────────────────────────────────────────
def run_cognitive_cycle(
    df_live: dict[str, pl.DataFrame] | None = None, *, do_train: bool = True
):
    """Run a lightweight cognition pass:
    1) (optional) Train model from event log
    2) Run AI inference on provided live frames (per timeframe)
    3) Compute stats-based recommender from log
    """
    ts = datetime.now(timezone.utc).isoformat()
    console.rule("[bold yellow]🧠 Tactical Cognitive Cycle")

    if do_train:
        run_training = _maybe(_import_trainer)
        if run_training:
            _safe_run("AI Trainer", run_training)

    run_ai_inference = _maybe(_import_inference)
    if run_ai_inference and df_live:
        _safe_run("AI Inference", run_ai_inference, df_live)

    recommend_from_log = _maybe(_import_recommender)
    if recommend_from_log:
        _safe_run("AI Recommender (stats)", recommend_from_log)

    console.print(f"🧭 Completed cycle at [cyan]{ts}[/cyan]")


# ── Loop mode (optional) ────────────────────────────────────
def run_autonomous_loop(
    *, interval_sec: int = 6 * 60 * 60, df_live: dict[str, pl.DataFrame] | None = None
):
    console.rule("[bold magenta]🤖 Cognitive Orchestrator — Loop")
    cycle = 0
    while True:
        cycle += 1
        console.print(f"\n🌀 Cycle #{cycle}")
        run_cognitive_cycle(df_live=df_live, do_train=True)
        console.print(f"💤 Sleeping for {interval_sec/3600:.1f} hours …")
        sleep(interval_sec)


# ── Smoke (optional) ────────────────────────────────────────
if __name__ == "__main__":
    run_cognitive_cycle(df_live=None, do_train=False)

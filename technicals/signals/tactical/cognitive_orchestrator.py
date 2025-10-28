# ============================================================
# queen/technicals/signals/tactical/cognitive_orchestrator.py
# ------------------------------------------------------------
# 🧠 Phase 7.0 — Tactical Cognitive Orchestrator
# Unifies perception → learning → optimization → reflection
# into one continuous self-adaptive intelligence loop.
# ============================================================

import time
import traceback
from datetime import datetime, timezone

from quant.signals.tactical.tactical_ai_inference import run_ai_inference
from quant.signals.tactical.tactical_ai_optimizer import optimize_indicator_weights
from quant.signals.tactical.tactical_ai_trainer import train_tactical_ai

# Orchestration submodules (each safe-imported)
from quant.signals.tactical.tactical_event_log import log_tactical_events
from quant.signals.tactical.tactical_meta_controller import run_meta_controller
from quant.signals.tactical.tactical_meta_dashboard import render_meta_dashboard
from quant.signals.tactical.tactical_meta_introspector import run_meta_introspector
from quant.signals.tactical.tactical_meta_memory import record_meta_memory
from rich.console import Console

console = Console()

# ============================================================
# ⚙️ Configuration (to later move into config.py)
# ============================================================
COGNITIVE_LOOP_INTERVAL = 60 * 60 * 6  # every 6 hours by default
ENABLE_INTROSPECTION = True
ENABLE_OPTIMIZATION = True
ENABLE_DASHBOARD = True


# ============================================================
# 🧩 Safe execution wrapper
# ============================================================
def _safe_run(func, label, *args, **kwargs):
    """Run a cognitive phase safely with logging."""
    try:
        console.rule(f"[bold cyan]{label}")
        result = func(*args, **kwargs)
        console.print(f"✅ [green]{label} completed[/green]\n")
        return result
    except Exception as e:
        console.print(f"⚠️ [{label}] Skipped: {e}")
        console.print(traceback.format_exc())
        return None


# ============================================================
# 🚀 Cognitive Loop
# ============================================================
def run_cognitive_cycle(global_health_dfs=None):
    """Executes one full cognition cycle:
    1. Logs tactical events
    2. Trains AI
    3. Runs inference
    4. Optimizes weights
    5. Updates meta controller + memory
    6. Introspects and visualizes dashboard
    """
    console.rule("[bold yellow]🧠 Phase 7.0 — Tactical Cognitive Orchestrator")

    ts_start = datetime.now(timezone.utc).isoformat()

    # 1️⃣ Log tactical events
    _safe_run(log_tactical_events, "Event Log Collector", global_health_dfs)

    # 2️⃣ Train AI model
    _safe_run(train_tactical_ai, "AI Trainer")

    # 3️⃣ Run inference (forecast)
    _safe_run(run_ai_inference, "AI Inference")

    # 4️⃣ Optimize weights dynamically
    if ENABLE_OPTIMIZATION:
        _safe_run(optimize_indicator_weights, "AI Optimizer")

    # 5️⃣ Meta controller + memory update
    _safe_run(run_meta_controller, "Meta Controller")
    _safe_run(record_meta_memory, "Meta Memory Recorder")

    # 6️⃣ Introspection + dashboard
    if ENABLE_INTROSPECTION:
        _safe_run(run_meta_introspector, "Meta Introspector")
    if ENABLE_DASHBOARD:
        _safe_run(render_meta_dashboard, "Meta Dashboard")

    console.print(f"🧭 Completed cognitive cycle at [cyan]{ts_start}[/cyan]")


# ============================================================
# 🔁 Continuous Daemon Mode
# ============================================================
def run_autonomous_loop(global_health_dfs=None, interval=COGNITIVE_LOOP_INTERVAL):
    """Continuously run cognitive cycles forever."""
    console.rule("[bold magenta]🤖 Cognitive Orchestrator — Autonomous Loop")
    cycle = 0
    while True:
        cycle += 1
        console.print(f"\n🌀 Starting Cycle #{cycle}")
        run_cognitive_cycle(global_health_dfs)
        console.print(
            f"💤 Sleeping for {interval/3600:.1f} hours before next cycle ..."
        )
        time.sleep(interval)


# ============================================================
# 🧪 Stand-alone test
# ============================================================
if __name__ == "__main__":
    run_cognitive_cycle()

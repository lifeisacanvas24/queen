# ============================================================
# quant/signals/tactical/tactical_meta_memory.py
# ------------------------------------------------------------
# 🧠 Phase 6.2 — Tactical Meta Memory
# Persistent quant "brain" that logs model evolution, drift,
# and optimization history for long-term adaptive intelligence.
# ============================================================

import json
import os
from datetime import datetime

import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# 🧩 Configuration (to later move into config.py)
# ============================================================
META_MEMORY_LOG = "quant/logs/meta_memory_log.csv"
WEIGHTS_PATH = "quant/config/indicator_weights.json"
META_CONFIG = "quant/config/meta_controller.json"
MODEL_PATH = "quant/models/tactical_ai_model.pkl"


# ============================================================
# 📦 Utility Functions
# ============================================================
def safe_load_json(path, default=None):
    if not os.path.exists(path):
        return default or {}
    with open(path) as f:
        return json.load(f)


def append_to_memory_log(record: dict):
    """Append a new memory record to the meta memory log CSV."""
    os.makedirs(os.path.dirname(META_MEMORY_LOG), exist_ok=True)

    df_new = pl.DataFrame([record])
    if os.path.exists(META_MEMORY_LOG):
        df_old = pl.read_csv(META_MEMORY_LOG)
        df_all = pl.concat([df_old, df_new])
    else:
        df_all = df_new

    df_all.write_csv(META_MEMORY_LOG)
    console.print(f"🧠 Appended meta-memory record → [cyan]{META_MEMORY_LOG}[/cyan]")


# ============================================================
# 🧬 Capture System State Snapshot
# ============================================================
def capture_system_snapshot():
    """Capture the current AI, meta, and weight configuration."""
    weights = safe_load_json(WEIGHTS_PATH, {})
    meta_cfg = safe_load_json(META_CONFIG, {})
    timestamp = datetime.utcnow().isoformat()

    record = {
        "timestamp": timestamp,
        "model_version": os.path.basename(MODEL_PATH),
        "last_retrain": meta_cfg.get("last_retrain_ts"),
        "drift_threshold": meta_cfg.get("drift_threshold"),
        "retrain_interval_hours": meta_cfg.get("retrain_interval_hours"),
        "total_indicators": len(weights),
        "top_feature": max(weights, key=weights.get) if weights else None,
        "top_weight": max(weights.values()) if weights else None,
    }

    append_to_memory_log(record)
    return record


# ============================================================
# 📊 Visualize Memory Timeline
# ============================================================
def show_memory_timeline():
    if not os.path.exists(META_MEMORY_LOG):
        console.print(f"⚠️ No meta memory log found at {META_MEMORY_LOG}")
        return

    df = pl.read_csv(META_MEMORY_LOG)
    if df.is_empty():
        console.print("⚪ Meta memory log is empty.")
        return

    table = Table(
        title="🧠 Meta Memory — Evolution Timeline",
        header_style="bold magenta",
        expand=True,
    )
    for col in ["timestamp", "model_version", "last_retrain", "top_feature", "top_weight"]:
        if col in df.columns:
            table.add_column(col)

    for row in df.tail(10).iter_rows(named=True):
        table.add_row(*[str(row.get(c, "")) for c in table.columns])

    console.print(table)
    console.print("[green]✅ Meta memory snapshot rendered.[/green]")


# ============================================================
# 🚀 Main Entry
# ============================================================
def record_meta_memory():
    console.rule("[bold yellow]🧠 Phase 6.2 — Tactical Meta Memory")
    record = capture_system_snapshot()
    show_memory_timeline()
    return record


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    record_meta_memory()

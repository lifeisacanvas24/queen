# ============================================================
# queen/technicals/signals/tactical/tactical_meta_controller.py
# ------------------------------------------------------------
# 🧠 Phase 6.0 — Tactical Meta Controller
# The adaptive orchestration layer that supervises the AI engine
# and automatically retrains, reweights, or recalibrates as needed.
# ============================================================

import json
import os
from datetime import datetime

from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# 📦 Configuration
# ============================================================
CONFIG_PATH = "quant/config/meta_controller.json"
DEFAULT_CONFIG = {
    "model_path": "quant/models/tactical_ai_model.pkl",
    "log_path": "quant/logs/tactical_event_log.csv",
    "weights_path": "quant/config/indicator_weights.json",
    "retrain_interval_hours": 24,
    "drift_threshold": 0.1,
    "last_retrain_ts": None,
}


# ============================================================
# 🧩 Helpers
# ============================================================
def load_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def hours_since(timestamp_str):
    if not timestamp_str:
        return 999
    try:
        ts = datetime.fromisoformat(timestamp_str)
        delta = datetime.utcnow() - ts
        return delta.total_seconds() / 3600
    except Exception:
        return 999


# ============================================================
# 📊 Performance Drift Detection
# ============================================================
def detect_performance_drift(
    model_path: str, event_log_path: str, drift_threshold: float
):
    """Evaluates model drift by comparing current vs historical accuracy."""
    if not os.path.exists(event_log_path) or not os.path.exists(model_path):
        console.print("⚠️ Missing log or model for drift detection.")
        return False, 0.0

    from quant.signals.tactical.tactical_ai_trainer import (
        load_event_log,
        preprocess,
    )

    df = load_event_log(event_log_path)
    X, y = preprocess(df)
    if X is None or len(X) < 50:
        return False, 0.0

    from joblib import load

    data = load(model_path)
    model = data["model"]
    scaler = data["scaler"]

    from sklearn.metrics import accuracy_score

    y_pred = model.predict(scaler.transform(X))
    acc_current = accuracy_score(y, y_pred)
    acc_historical = model.score(scaler.transform(X), y)

    drift = abs(acc_historical - acc_current)
    return drift > drift_threshold, drift


# ============================================================
# 🤖 Meta-Control Routine
# ============================================================
def meta_controller_run():
    """Main orchestration logic for adaptive retraining & reweighting."""
    cfg = load_config()

    console.rule("[bold magenta]🧠 Phase 6.0 — Tactical Meta Controller")
    console.print("📅 Checking model lifecycle...")

    hours_elapsed = hours_since(cfg["last_retrain_ts"])
    retrain_due = hours_elapsed > cfg["retrain_interval_hours"]

    drift_flag, drift_value = detect_performance_drift(
        cfg["model_path"], cfg["log_path"], cfg["drift_threshold"]
    )

    decisions = []

    if retrain_due:
        decisions.append("⏳ Retraining due (interval exceeded)")
    if drift_flag:
        decisions.append(f"📉 Performance drift detected ({drift_value:.3f})")

    if not decisions:
        decisions.append("✅ Model stable and up-to-date")

    # --- Render decision table ---
    table = Table(
        title="🧠 Meta Controller — Decisions", header_style="bold cyan", expand=True
    )
    table.add_column("Condition")
    table.add_column("Action")
    for d in decisions:
        action = "Re-train Model" if "Retraining" in d or "drift" in d else "None"
        table.add_row(d, action)
    console.print(table)

    # --- Execute actions ---
    if any("Re-train" in a or "drift" in a for a in decisions):
        try:
            from quant.signals.tactical.tactical_ai_trainer import main as train_model

            console.print("🚀 Triggering model retraining...")
            train_model()
            cfg["last_retrain_ts"] = datetime.utcnow().isoformat()
            save_config(cfg)

            # Re-run optimizer after retraining
            from quant.signals.tactical.tactical_ai_optimizer import (
                optimize_indicator_weights,
            )

            optimize_indicator_weights(cfg["model_path"])
        except Exception as e:
            console.print(f"⚠️ [Meta Controller] Retraining failed: {e}")

    console.print("🏁 Meta-controller cycle complete.")
    return cfg


# ============================================================
# 🧪 Standalone Entry
# ============================================================
if __name__ == "__main__":
    meta_controller_run()

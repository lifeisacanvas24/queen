# queen/technicals/signals/tactical/meta_controller.py
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Any

import polars as pl
from queen.helpers.common import utc_now_iso
from queen.helpers.logger import log

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None


# Optional weights module (code-based, not JSON)
def _load_weights_dict() -> dict:
    try:
        from queen.settings import weights as W

        # support either INDICATOR_WEIGHTS or WEIGHTS
        return getattr(W, "INDICATOR_WEIGHTS", getattr(W, "WEIGHTS", {})) or {}
    except Exception:
        return {}


# ------- effective paths (settings-driven + state file) -------
def _P() -> Dict[str, Path]:
    if SETTINGS:
        paths = SETTINGS.PATHS
        logs = Path(paths["LOGS"])
        models_root = Path(paths.get("MODELS", paths.get("CACHE", paths["RUNTIME"])))
    else:
        root = Path("queen/data/runtime")
        logs = root / "logs"
        models_root = root / "cache"
    models = models_root / "models"
    logs.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    return {
        "logs": logs,
        "models": models,
        "event_log": logs / "tactical_event_log.csv",
        "meta_memory": logs / "meta_memory_log.csv",
        "drift_log": logs / "meta_drift_log.csv",
        "state_json": logs / "meta_controller_state.json",  # ← replaces meta_cfg_json
        "model_pkl": models / "tactical_ai_model.pkl",
    }


# ------- defaults kept in-code (no external config file) -------
DEFAULTS = {
    "retrain_interval_hours": 24,
    "drift_threshold": 0.10,
    "last_retrain_ts": None,
}


def _load_state() -> Dict[str, Any]:
    P = _P()
    if not P["state_json"].exists():
        P["state_json"].write_text(json.dumps(DEFAULTS, indent=2))
        return DEFAULTS.copy()
    try:
        base = json.loads(P["state_json"].read_text() or "{}")
    except Exception:
        base = {}
    merged = {**DEFAULTS, **base}
    if merged != base:
        P["state_json"].write_text(json.dumps(merged, indent=2))
    return merged


def _save_state(st: Dict[str, Any]) -> None:
    _P()["state_json"].write_text(json.dumps(st, indent=2))


def _hours_since(ts: str | None) -> float:
    if not ts:
        return 10_000.0
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (
            datetime.now(timezone.utc) - t.astimezone(timezone.utc)
        ).total_seconds() / 3600.0
    except Exception:
        return 10_000.0


# ------- drift check (skips if model/log missing) -------
def _detect_drift(
    model_path: Path, event_log_path: Path, drift_threshold: float
) -> Tuple[bool, float]:
    if not (model_path.exists() and event_log_path.exists()):
        log.info("[Meta] Drift check skipped (missing model/log).")
        return False, 0.0
    df = pl.read_csv(event_log_path)
    if df.height < 50 or "Reversal_Alert" not in df.columns:
        return False, 0.0

    cols = [
        c
        for c in (
            "CMV",
            "Reversal_Score",
            "Confidence",
            "ATR_Ratio",
            "BUY_Ratio",
            "SELL_Ratio",
        )
        if c in df.columns
    ]
    if not cols:
        return False, 0.0

    X = df.select(cols).fill_null(0.0).to_numpy()
    y = (
        df["Reversal_Alert"]
        .fill_null("")
        .map_elements(lambda s: 1 if "BUY" in s else (-1 if "SELL" in s else 0))
        .to_numpy()
    )

    try:
        import joblib
        from sklearn.metrics import accuracy_score

        data = joblib.load(model_path)
        model, scaler = data.get("model"), data.get("scaler")
        y_pred = model.predict(scaler.transform(X))
        acc_current = float(accuracy_score(y, y_pred))
        acc_ref = float(getattr(model, "acc_ref_", acc_current))
        drift = abs(acc_ref - acc_current)
        return (drift > float(drift_threshold)), drift
    except Exception as e:
        log.warning(f"[Meta] Drift check failed: {e}")
        return False, 0.0


# ------- merged meta-memory snapshot (uses settings/weights.py) -------
def _append_meta_memory_row(state: Dict[str, Any]) -> None:
    P = _P()
    weights = _load_weights_dict()
    top_feat, top_w = (None, None)
    if weights:
        top_feat = max(weights, key=weights.get)
        top_w = float(weights[top_feat])

    row = {
        "timestamp": utc_now_iso(),  # Z-UTC; tests can parse
        "model_version": P["model_pkl"].name,
        "last_retrain": state.get("last_retrain_ts"),
        "drift_threshold": state.get("drift_threshold"),
        "retrain_interval_hours": state.get("retrain_interval_hours"),
        "total_indicators": len(weights),
        "top_feature": top_feat,
        "top_weight": top_w,
    }
    df_new = pl.DataFrame([row])
    if P["meta_memory"].exists():
        df_old = pl.read_csv(P["meta_memory"])
        df_all = pl.concat([df_old, df_new], how="vertical_relaxed")
    else:
        df_all = df_new
    df_all.write_csv(P["meta_memory"])
    log.info(f"[Meta] memory snapshot appended → {P['meta_memory']}")


# ------- training trigger -------
def _maybe_retrain(state: Dict[str, Any], drift_flag: bool) -> bool:
    P = _P()
    elapsed = _hours_since(state.get("last_retrain_ts"))
    due = elapsed > float(state["retrain_interval_hours"])
    actions = []
    if due:
        actions.append("interval_due")
    if drift_flag:
        actions.append("drift")

    if not actions:
        log.info("[Meta] model stable; no action.")
        return False

    log.info(f"[Meta] actions={actions}")
    try:
        from queen.technicals.signals.tactical.ai_trainer import run_training

        bundle = run_training(model_path=P["model_pkl"])
        if bundle:
            state["last_retrain_ts"] = utc_now_iso()
            _save_state(state)
            try:
                from queen.technicals.signals.tactical.ai_optimizer import (
                    optimize_indicator_weights,
                )

                optimize_indicator_weights(P["model_pkl"])
            except Exception as e:
                log.warning(f"[Meta] weight optimization skipped: {e}")
            _append_meta_memory_row(state)  # ← merged memory write here
        return True
    except Exception as e:
        log.warning(f"[Meta] retrain failed: {e}")
        return False


# ------- public API -------
def meta_controller_run() -> Dict[str, Any]:
    log.info("[Meta] cycle begin")
    P = _P()
    st = _load_state()
    drift_flag, drift_val = _detect_drift(
        P["model_pkl"], P["event_log"], st["drift_threshold"]
    )
    _maybe_retrain(st, drift_flag)
    log.info("[Meta] cycle complete")
    return st


if __name__ == "__main__":
    meta_controller_run()

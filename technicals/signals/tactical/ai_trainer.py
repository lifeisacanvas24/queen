# ============================================================
# queen/technicals/signals/tactical/ai_trainer.py
# ------------------------------------------------------------
# 🤖 Tactical AI Trainer (Settings-Driven Paths, Optional Deps)
# - sklearn/joblib imported inside funcs only
# - paths from SETTINGS.PATHS with safe fallbacks
# ============================================================

from __future__ import annotations
import os
from pathlib import Path
import numpy as np
import pl as _ignore  # avoid name shadowing if user aliases polars as pl elsewhere
import polars as pl
from queen.helpers.logger import log
from rich.console import Console

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None

console = Console()


def _default_event_log_path() -> Path:
    if SETTINGS:
        return SETTINGS.PATHS["LOGS"] / "tactical_event_log.csv"
    return Path("queen/data/runtime/logs") / "tactical_event_log.csv"


def _default_model_path() -> Path:
    # Choose CACHE/models as durable cross-env location
    if SETTINGS:
        base = SETTINGS.PATHS.get("CACHE", SETTINGS.PATHS["RUNTIME"])
        return base / "models" / "tactical_ai_model.pkl"
    return Path("queen/data/runtime/cache/models/tactical_ai_model.pkl")


# ── Data IO ─────────────────────────────────────────────────
def load_event_log(path: str | os.PathLike | None = None) -> pl.DataFrame:
    p = Path(path) if path else _default_event_log_path()
    if not p.exists():
        log.info(f"[AI-Trainer] No event log at {p}")
        return pl.DataFrame()
    df = pl.read_csv(p, ignore_errors=True)
    return (
        df.drop_nulls(["Reversal_Alert"])
        if "Reversal_Alert" in df.columns
        else pl.DataFrame()
    )


# change load_model signature & default:
def load_model(model_path: str | os.PathLike | None = None):
    path = Path(model_path) if model_path else _default_model_path()
    if not path.exists():
        console.print(f"⚠️ No AI model found at [red]{path}[/red]")
        return None, None
    try:
        import joblib
    except Exception:
        console.print("⚠️ joblib not available; skipping model load.")
        return None, None
    data = joblib.load(path)
    return data.get("model"), data.get("scaler")


def preprocess(df: pl.DataFrame):
    if df.is_empty():
        return None, None
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
        log.warning("[AI-Trainer] No numeric feature columns found.")
        return None, None
    X = np.nan_to_num(df.select(cols).to_numpy(), nan=0.0)

    labels = []
    for v in df["Reversal_Alert"]:
        if isinstance(v, str) and "BUY" in v:
            labels.append(1)
        elif isinstance(v, str) and "SELL" in v:
            labels.append(-1)
        else:
            labels.append(0)
    y = np.asarray(labels, dtype=int)
    return X, y


# ── Training (optional deps inside) ─────────────────────────
def train_model(X, y):
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except Exception as e:
        log.warning(f"[AI-Trainer] sklearn not available → {e}")
        return None

    if X is None or len(X) == 0:
        log.warning("[AI-Trainer] No training data.")
        return None

    strat = y if len(set(y)) > 1 else None
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=strat
    )

    scaler = StandardScaler()
    Xtr = scaler.fit_transform(Xtr)
    Xte = scaler.transform(Xte)

    model = LogisticRegression(max_iter=1000)
    model.fit(Xtr, ytr)
    from numpy import round as npround

    acc = float(npround(((model.predict(Xte) == yte).sum() / max(len(yte), 1)), 3))
    log.info(f"[AI-Trainer] Model trained. Accuracy={acc:.3f}")
    return {"model": model, "scaler": scaler, "accuracy": acc}


def save_model(bundle, path: str | os.PathLike | None = None):
    if bundle is None:
        return
    try:
        import joblib
    except Exception as e:
        log.warning(f"[AI-Trainer] joblib not available → {e}")
        return
    p = Path(path) if path else _default_model_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": bundle["model"], "scaler": bundle["scaler"]}, p)
    log.info(f"[AI-Trainer] Model saved → {p}")


# ── One-shot entry ──────────────────────────────────────────
def run_training(
    log_path: str | os.PathLike | None = None,
    model_path: str | os.PathLike | None = None,
):
    df = load_event_log(log_path)
    X, y = preprocess(df)
    bundle = train_model(X, y)
    save_model(bundle, model_path)
    return bundle

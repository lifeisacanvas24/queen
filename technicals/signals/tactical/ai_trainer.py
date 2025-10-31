# queen/technicals/signals/tactical/ai_trainer.py
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from quant import config
from queen.helpers.logger import log
from rich.console import Console

console = Console()


def _event_log_path() -> Path:
    return config.get_path("paths.logs") / "tactical_event_log.csv"


def _model_path() -> Path:
    base = config.get_path("paths.models", fallback=config.get_path("paths.cache"))
    return base / "tactical_ai_model.pkl"


def load_event_log(path: str | Path | None = None) -> pl.DataFrame:
    p = Path(path) if path else _event_log_path()
    if not p.exists():
        log.info(f"[AI-Trainer] No event log at {p}")
        return pl.DataFrame()
    df = pl.read_csv(p, ignore_errors=True)
    if "Reversal_Alert" in df.columns:
        return df.drop_nulls(["Reversal_Alert"])
    return pl.DataFrame()


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
    y = np.array(
        [
            1
            if isinstance(v, str) and "BUY" in v
            else (-1 if isinstance(v, str) and "SELL" in v else 0)
            for v in df.get_column("Reversal_Alert")
        ],
        dtype=int,
    )
    return X, y


def train_model(X, y):
    try:
        from sklearn.linear_model import LogisticRegression
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
    model = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    acc = float((model.predict(Xte) == yte).sum() / max(len(yte), 1))
    log.info(f"[AI-Trainer] Model trained. Accuracy={acc:.3f}")
    return {"model": model, "scaler": scaler, "accuracy": acc}


def save_model(bundle, path: str | Path | None = None):
    if bundle is None:
        return
    try:
        import joblib
    except Exception as e:
        log.warning(f"[AI-Trainer] joblib not available → {e}")
        return
    p = Path(path) if path else _model_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": bundle["model"], "scaler": bundle["scaler"]}, p)
    log.info(f"[AI-Trainer] Model saved → {p}")


def run_training(
    log_path: str | Path | None = None, model_path: str | Path | None = None
):
    df = load_event_log(log_path)
    X, y = preprocess(df)
    bundle = train_model(X, y)
    save_model(bundle, model_path)
    return bundle

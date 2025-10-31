#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/ai_inference.py
# ------------------------------------------------------------
# 🤖 Tactical AI Inference (optional)
# Loads a trained model (e.g., logistic regression) and infers
# BUY/SELL probabilities per timeframe.
# - No hard dependency on joblib (safe fallback).
# - Pure Polars feature extraction; numpy only for model I/O.
# ============================================================
from __future__ import annotations

import os
from typing import Dict

import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()

# Optional import (kept lazy-safe)
try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover
    joblib = None


# ------------------------------------------------------------
# Model I/O
# ------------------------------------------------------------
def load_model(model_path: str = "quant/models/tactical_ai_model.pkl"):
    """Return (model, scaler) if available; else (None, None)."""
    if joblib is None:
        console.print("⚠️ joblib not available; skipping model load.")
        return None, None
    if not os.path.exists(model_path):
        console.print(f"⚠️ No AI model found at [red]{model_path}[/red]")
        return None, None
    try:
        data = joblib.load(model_path)
        model = data.get("model")
        scaler = data.get("scaler")
        console.print(f"📦 Loaded AI model from [green]{model_path}[/green]")
        return model, scaler
    except Exception as e:  # pragma: no cover
        console.print(f"⚠️ Failed to load model: {e}")
        return None, None


# ------------------------------------------------------------
# Feature prep
# ------------------------------------------------------------
DEFAULT_FEATURES = [
    "CMV",
    "Reversal_Score",
    "Confidence",
    "ATR_Ratio",
    "BUY_Ratio",
    "SELL_Ratio",
]


def prepare_features(
    df: pl.DataFrame, features: list[str] | None = None
) -> np.ndarray | None:
    feats = features or DEFAULT_FEATURES
    avail = [c for c in feats if c in df.columns]
    if not avail:
        return None
    row = df.select(avail).tail(1)  # 1×k
    arr = row.to_numpy()
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


# ------------------------------------------------------------
# Inference
# ------------------------------------------------------------
def predict_next_move(
    model,
    scaler,
    df_live: Dict[str, pl.DataFrame],
    *,
    features: list[str] | None = None,
    buy_threshold: float = 0.60,
    sell_threshold: float = 0.60,
) -> pl.DataFrame:
    """Return a Polars DF with BUY/SELL probabilities per timeframe."""
    results: list[tuple[str, float, float, str]] = []

    for tf, df in df_live.items():
        X = prepare_features(df, features)
        if X is None:
            results.append((tf, 0.0, 0.0, "⚪ No Data"))
            continue

        if (model is None) or (scaler is None):
            results.append((tf, 0.0, 0.0, "⚪ Model Missing"))
            continue

        try:
            Xs = scaler.transform(X)
            probs = model.predict_proba(Xs)[0]
            # Expecting classes like [-1, 0, 1] → (sell, neutral, buy)
            # If different, adjust indices externally or train consistently.
            prob_sell = float(probs[0])
            prob_buy = float(probs[-1])
        except Exception:  # pragma: no cover
            results.append((tf, 0.0, 0.0, "⚪ Inference Error"))
            continue

        bias = (
            "🟢 BUY Likely"
            if prob_buy >= buy_threshold
            else "🔴 SELL Likely"
            if prob_sell >= sell_threshold
            else "⚪ Neutral"
        )
        results.append((tf, prob_buy, prob_sell, bias))

    return pl.DataFrame(
        results,
        schema=["timeframe", "BUY_Prob", "SELL_Prob", "Forecast"],
        orient="row",
    )


# ------------------------------------------------------------
# Render helper (optional)
# ------------------------------------------------------------
def render_ai_forecast(df_out: pl.DataFrame):
    if df_out.is_empty():
        console.print("⚪ No AI forecast data available.")
        return
    t = Table(
        title="🤖 Tactical AI Inference — Reversal Forecasts",
        header_style="bold green",
        expand=True,
    )
    for c in df_out.columns:
        t.add_column(c, justify="center")
    for row in df_out.iter_rows(named=True):
        t.add_row(*[str(v) for v in row.values()])
    console.print(t)


# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
def run_ai_inference(
    df_live: Dict[str, pl.DataFrame],
    *,
    model_path: str = "quant/models/tactical_ai_model.pkl",
    features: list[str] | None = None,
) -> pl.DataFrame:
    model, scaler = load_model(model_path)
    df_out = predict_next_move(model, scaler, df_live, features=features)
    render_ai_forecast(df_out)
    return df_out

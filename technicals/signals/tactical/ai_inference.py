# queen/technicals/signals/tactical/ai_inference.py
from __future__ import annotations

import os
from typing import Dict

import numpy as np
import polars as pl
from quant import config
from rich.console import Console
from rich.table import Table

console = Console()


def _model_path_default() -> str:
    models = config.get_path("paths.models", fallback=config.get_path("paths.cache"))
    return str(models / "tactical_ai_model.pkl")


def load_model(model_path: str | None = None):
    path = str(model_path) if model_path else _model_path_default()
    try:
        import joblib  # optional
    except Exception:
        console.print("⚠️ joblib not available; skipping model load.")
        return None, None
    if not os.path.exists(path):
        console.print(f"⚠️ No AI model found at [red]{path}[/red]")
        return None, None
    try:
        data = joblib.load(path)
        return data.get("model"), data.get("scaler")
    except Exception as e:
        console.print(f"⚠️ Failed to load model: {e}")
        return None, None


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
    arr = df.select(avail).tail(1).to_numpy()
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


def predict_next_move(
    model,
    scaler,
    df_live: Dict[str, pl.DataFrame],
    *,
    features: list[str] | None = None,
    buy_threshold: float = 0.60,
    sell_threshold: float = 0.60,
) -> pl.DataFrame:
    results: list[tuple[str, float, float, str]] = []
    for tf, df in df_live.items():
        X = prepare_features(df, features)
        if X is None or (model is None) or (scaler is None):
            results.append((tf, 0.0, 0.0, "⚪ No Model/Data"))
            continue
        try:
            Xs = scaler.transform(X)
            probs = model.predict_proba(Xs)[0]
            prob_sell, prob_buy = (
                float(probs[0]),
                float(probs[-1]),
            )  # assume classes [-1,0,1]
        except Exception:
            results.append((tf, 0.0, 0.0, "⚪ Inference Error"))
            continue
        bias = (
            "🟢 BUY Likely"
            if prob_buy >= buy_threshold
            else ("🔴 SELL Likely" if prob_sell >= sell_threshold else "⚪ Neutral")
        )
        results.append((tf, prob_buy, prob_sell, bias))
    return pl.DataFrame(
        results, schema=["timeframe", "BUY_Prob", "SELL_Prob", "Forecast"], orient="row"
    )


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


def run_ai_inference(
    df_live: Dict[str, pl.DataFrame],
    *,
    model_path: str | None = None,
    features: list[str] | None = None,
) -> pl.DataFrame:
    model, scaler = load_model(model_path or _model_path_default())
    out = predict_next_move(model, scaler, df_live, features=features)
    render_ai_forecast(out)
    return out

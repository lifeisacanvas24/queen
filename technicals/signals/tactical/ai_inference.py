# ============================================================
# quant/signals/tactical/tactical_ai_inference.py
# ------------------------------------------------------------
# 🤖 Phase 5.2 — Tactical AI Inference Engine
# Loads the trained AI model (Phase 5.1) and
# predicts BUY/SELL probabilities for each timeframe.
# ============================================================

import os

import joblib
import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()


# ============================================================
# 🧩 Load Trained Model
# ============================================================
def load_model(model_path: str = "quant/models/tactical_ai_model.pkl"):
    """Load the trained logistic regression model + scaler."""
    if not os.path.exists(model_path):
        console.print(f"⚠️ No AI model found at [red]{model_path}[/red]")
        return None, None
    data = joblib.load(model_path)
    model = data.get("model")
    scaler = data.get("scaler")
    console.print(f"📦 Loaded AI model from [green]{model_path}[/green]")
    return model, scaler


# ============================================================
# 🧠 Prepare Live Features
# ============================================================
def prepare_features(df: pl.DataFrame):
    """Extract numeric features from the most recent bar."""
    features = [
        "CMV", "Reversal_Score", "Confidence",
        "ATR_Ratio", "BUY_Ratio", "SELL_Ratio"
    ]
    existing = [c for c in features if c in df.columns]
    if not existing:
        return None

    # take latest row as inference sample
    latest = df.select(existing).tail(1).to_numpy()
    return np.nan_to_num(latest, nan=0.0)


# ============================================================
# 🔮 Predict Probabilities
# ============================================================
def predict_next_move(model, scaler, df_live: dict[str, pl.DataFrame]):
    """Runs inference per timeframe."""
    if model is None or scaler is None:
        console.print("⚠️ Model not loaded; skipping inference.")
        return pl.DataFrame()

    results = []
    for tf, df in df_live.items():
        X = prepare_features(df)
        if X is None:
            results.append((tf, 0.0, 0.0, "⚪ No Data"))
            continue

        X_scaled = scaler.transform(X)
        probs = model.predict_proba(X_scaled)[0]

        # class order: [-1, 0, 1] → SELL, NEUTRAL, BUY
        prob_sell = float(probs[0])
        prob_buy = float(probs[-1])

        # simple bias determination
        bias = (
            "🟢 BUY Likely" if prob_buy > 0.6
            else "🔴 SELL Likely" if prob_sell > 0.6
            else "⚪ Neutral"
        )

        results.append((tf, prob_buy, prob_sell, bias))

    df_out = pl.DataFrame(
        results,
        schema=["timeframe", "BUY_Prob", "SELL_Prob", "Forecast"]
    )
    return df_out


# ============================================================
# 🎨 Render AI Forecast Table
# ============================================================
def render_ai_forecast(df_out: pl.DataFrame):
    if df_out.is_empty():
        console.print("⚪ No AI forecast data available.")
        return

    table = Table(
        title="🤖 Tactical AI Inference — Reversal Forecasts",
        header_style="bold green",
        expand=True,
    )
    for col in df_out.columns:
        table.add_column(col, justify="center")

    for row in df_out.iter_rows(named=True):
        table.add_row(*[str(v) for v in row.values()])
    console.print(table)


# ============================================================
# 🚀 Main Inference Entrypoint
# ============================================================
def run_ai_inference(df_live: dict[str, pl.DataFrame], model_path: str = "quant/models/tactical_ai_model.pkl"):
    """Convenience wrapper to load, infer, and render."""
    model, scaler = load_model(model_path)
    df_out = predict_next_move(model, scaler, df_live)
    render_ai_forecast(df_out)
    return df_out


# ============================================================
# 🧪 Standalone Test
# ============================================================
if __name__ == "__main__":
    # Mock single timeframe for demo
    n = 100
    df = pl.DataFrame({
        "CMV": np.random.uniform(-1, 1, n),
        "Reversal_Score": np.random.uniform(0, 5, n),
        "Confidence": np.random.uniform(0.5, 1.0, n),
        "ATR_Ratio": np.random.uniform(0.8, 1.4, n),
        "BUY_Ratio": np.random.uniform(0.0, 1.0, n),
        "SELL_Ratio": np.random.uniform(0.0, 1.0, n),
    })

    df_live = {"5m": df, "15m": df, "1h": df}
    run_ai_inference(df_live)

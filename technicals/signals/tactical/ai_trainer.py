# ============================================================
# quant/signals/tactical/tactical_ai_trainer.py
# ------------------------------------------------------------
# 🤖 Phase 5.1 — Tactical AI Trainer
# Learns from historical tactical_event_log.csv
# and builds a lightweight predictive model
# ============================================================

import os

import joblib
import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

console = Console()

# ============================================================
# ⚙️ Load & Prepare Data
# ============================================================
def load_event_log(path: str = "quant/logs/tactical_event_log.csv") -> pl.DataFrame:
    if not os.path.exists(path):
        console.print(f"⚠️ No event log found at {path}")
        return pl.DataFrame()
    df = pl.read_csv(path)
    # Drop obviously empty rows
    df = df.drop_nulls(["Reversal_Alert"])
    return df


def preprocess(df: pl.DataFrame):
    """Extract numeric features + encoded label."""
    if df.is_empty():
        return None, None

    # Feature engineering (choose any subset that exists)
    cols = [c for c in [
        "CMV", "Reversal_Score", "Confidence",
        "ATR_Ratio", "BUY_Ratio", "SELL_Ratio"
    ] if c in df.columns]

    if not cols:
        console.print("⚠️ No numeric columns found to train on.")
        return None, None

    X = np.nan_to_num(df.select(cols).to_numpy(), nan=0.0)

    # Label encoding
    labels = []
    for v in df["Reversal_Alert"]:
        if isinstance(v, str) and "BUY" in v:
            labels.append(1)
        elif isinstance(v, str) and "SELL" in v:
            labels.append(-1)
        else:
            labels.append(0)
    y = np.array(labels, dtype=int)

    return X, y


# ============================================================
# 🧠 Train Model
# ============================================================
def train_model(X: np.ndarray, y: np.ndarray):
    """Train logistic regression classifier."""
    if X is None or len(X) == 0:
        console.print("⚠️ No training data available.")
        return None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if len(set(y)) > 1 else None
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    console.print(f"✅ Model trained | Accuracy: [bold green]{acc:.3f}[/bold green]")
    console.print(classification_report(y_test, y_pred, digits=3))

    return model, scaler


# ============================================================
# 💾 Save Model
# ============================================================
def save_model(model, scaler, path: str = "quant/models/tactical_ai_model.pkl"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump({"model": model, "scaler": scaler}, path)
    console.print(f"💾 Model saved to [cyan]{path}[/cyan]")


# ============================================================
# 📊 Render Summary
# ============================================================
def render_training_summary(model, acc: float):
    table = Table(title="🤖 Tactical AI Trainer — Summary", header_style="bold blue", expand=True)
    table.add_column("Model")
    table.add_column("Accuracy")
    table.add_column("Notes")
    table.add_row("LogisticRegression", f"{acc:.3f}", "Baseline classifier for reversals")
    console.print(table)


# ============================================================
# 🧪 Entry
# ============================================================
def main():
    df = load_event_log()
    X, y = preprocess(df)
    model_data = train_model(X, y)
    if model_data is None:
        return
    model, scaler = model_data
    save_model(model, scaler)
    render_training_summary(model, acc=model.score(StandardScaler().fit_transform(X), y))


if __name__ == "__main__":
    main()

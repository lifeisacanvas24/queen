# queen/technicals/signals/tactical/ai_optimizer.py
from __future__ import annotations

import json
from pathlib import Path

from quant import config
from queen.helpers.logger import log


def _model_path() -> Path:
    base = config.get_path("paths.models", fallback=config.get_path("paths.cache"))
    return base / "tactical_ai_model.pkl"


def _weights_out_path() -> Path:
    # keep alongside model artifacts
    base = config.get_path("paths.models", fallback=config.get_path("paths.cache"))
    return base / "indicator_weights.json"


def _feature_names_default() -> list[str]:
    # Must match training features order
    return [
        "CMV",
        "Reversal_Score",
        "Confidence",
        "ATR_Ratio",
        "BUY_Ratio",
        "SELL_Ratio",
    ]


def optimize_indicator_weights(
    model_path: str | None = None,
    out_path: str | None = None,
    feature_names: list[str] | None = None,
) -> Path | None:
    path = Path(model_path) if model_path else _model_path()
    try:
        import joblib
    except Exception as e:
        log.warning(f"[AI-Opt] joblib not available → {e}")
        return None
    if not path.exists():
        log.warning(f"[AI-Opt] model not found at {path}")
        return None

    data = joblib.load(path)
    model = data.get("model")
    if model is None:
        log.warning("[AI-Opt] model missing in bundle")
        return None

    # Try to extract linear coefficients; fallback to equal weights
    names = feature_names or _feature_names_default()
    try:
        import numpy as np

        coef = getattr(model, "coef_", None)
        if coef is None:
            weights = {n: 1.0 / len(names) for n in names}
        else:
            vec = np.mean(np.abs(coef), axis=0).ravel()  # shape (k,)
            s = float(vec.sum()) or 1.0
            weights = {n: float(v / s) for n, v in zip(names, vec)}
    except Exception as e:
        log.warning(f"[AI-Opt] failed to derive weights → {e}")
        weights = {n: 1.0 / len(names) for n in names}

    out = Path(out_path) if out_path else _weights_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(weights, f, indent=2)
    log.info(f"[AI-Opt] indicator weights saved → {out}")
    return out

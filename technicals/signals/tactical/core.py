#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/core.py
# Tactical Fusion Engine — v3.0 (Bible v10.5+)
# ============================================================
"""Adaptive Tactical Fusion Engine — blends regime (RScore), volatility (VolX),
liquidity (LBX), and pattern context (PatternScore) into a unified Tactical Index.

✅ Settings-driven via queen.settings.weights (no JSON files)
✅ Uses component weights from tactical_component_weights()
✅ Uses ENTRY/EXIT thresholds from get_thresholds()
✅ Emits regime classification (Bullish / Neutral / Bearish)
✅ Accepts dict or Polars DataFrame as input
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import polars as pl

from queen.helpers.logger import log
from queen.settings.weights import (
    get_thresholds,
    tactical_component_weights,
    tactical_normalization,
)

# --------------------------- Utils ---------------------------


def _zscore(values: Dict[str, float]) -> Dict[str, float]:
    arr = np.array(list(values.values()), dtype=float)
    if arr.size == 0:
        return {k: 0.0 for k in values}
    mean = float(arr.mean())
    std = float(arr.std()) or 1.0
    return {k: (float(v) - mean) / std for k, v in values.items()}


def _minmax(values: Dict[str, float]) -> Dict[str, float]:
    arr = np.array(list(values.values()), dtype=float)
    if arr.size == 0:
        return {k: 0.0 for k in values}
    lo, hi = float(arr.min()), float(arr.max())
    rng = (hi - lo) or 1.0
    return {k: (float(v) - lo) / rng for k, v in values.items()}


# ------------------------ Main API --------------------------


def compute_tactical_index(
    metrics: Dict[str, Any] | pl.DataFrame,
    *,
    interval: str = "15m",
) -> Dict[str, Any]:
    """Blend RScore, VolX, LBX, and PatternScore into a normalized Tactical Index.

    Args:
        metrics:
            • dict with scalar values (e.g. {'RScore_norm': 0.8, 'VolX_norm': 0.6, ...})
            • or Polars DataFrame with columns for each source field.
        interval:
            • timeframe token like '5m', '15m', '1h', '1d'
            • only used for threshold lookup and metadata.

    """
    # 1) Settings: component weights + normalization config
    comp_weights = tactical_component_weights()         # e.g. {'RScore':0.4, ...}
    norm_cfg = tactical_normalization()                 # {'method': 'minmax', 'clip': (0,1)}
    method = (norm_cfg.get("method") or "minmax").lower()
    clip_lo, clip_hi = norm_cfg.get("clip", (0.0, 1.0))

    # 2) Thresholds (use ENTRY/EXIT as bullish/bearish)
    #    get_thresholds may later be per-context; for now we pass interval as-is.
    th = get_thresholds(interval)
    bear_th = float(th.get("EXIT", 0.30))
    bull_th = float(th.get("ENTRY", 0.70))

    # 3) Define logical inputs → source field names
    #    (keys here must match comp_weights keys)
    inputs = {
        "RScore": {"source": "RScore_norm"},
        "VolX": {"source": "VolX_norm"},
        "LBX": {"source": "LBX_norm"},
        # PatternScore is assumed to be PatternComponent in the incoming metrics
        "PatternScore": {"source": "PatternComponent"},
    }

    # 4) Extract raw metric values (strict: all components in comp_weights must be present)
    raw: Dict[str, float] = {}
    missing: list[str] = []

    def _extract(src_key: str) -> float | None:
        if isinstance(metrics, dict):
            return metrics.get(src_key)
        if isinstance(metrics, pl.DataFrame) and src_key in metrics.columns:
            # Use mean as a stable scalar; change to last() if you prefer last-bar behavior
            return float(pl.Series(metrics[src_key]).mean())
        return None

    for key, meta in inputs.items():
        if key not in comp_weights:
            # weight not configured → skip entirely
            continue
        src = meta.get("source", key)
        val = _extract(src)
        if val is None:
            missing.append(f"{key} (source={src})")
        else:
            raw[key] = float(val)

    if missing:
        raise ValueError(
            f"compute_tactical_index: missing required inputs from metrics: {missing}"
        )

    # 5) Normalize component scores
    if method == "zscore":
        normed = _zscore(raw)
    else:
        normed = _minmax(raw)

    # 6) Weight & fuse
    weighted: Dict[str, float] = {}
    total_w = 0.0
    for key, val in normed.items():
        w = float(comp_weights.get(key, 0.0))
        if w <= 0.0:
            continue
        weighted[key] = val * w
        total_w += w

    fused = sum(weighted.values()) / (total_w or 1.0)

    # 7) Clip & round Tactical Index
    fused = max(min(fused, float(clip_hi)), float(clip_lo))
    fused = round(fused, 3)

    # 8) Regime classification (bearish / neutral / bullish)
    if fused < bear_th:
        regime_name = "bearish"
    elif fused < bull_th:
        regime_name = "neutral"
    else:
        regime_name = "bullish"

    # Simple default labels/colors; can be later extended via settings if needed
    default_labels = {
        "bearish": "Bearish",
        "neutral": "Neutral",
        "bullish": "Bullish",
    }
    default_colors = {
        "bearish": "#ef4444",  # red
        "neutral": "#9ca3af",  # grey
        "bullish": "#3b82f6",  # blue
    }

    out = {
        # Expose normalized components used inside fusion
        "RScore_norm": round(normed.get("RScore", 0.0), 3),
        "VolX_norm": round(normed.get("VolX", 0.0), 3),
        "LBX_norm": round(normed.get("LBX", 0.0), 3),
        "PatternScore_norm": round(normed.get("PatternScore", 0.0), 3),
        # Tactical Index
        "Tactical_Index": fused,
        # Regime metadata
        "regime": {
            "name": regime_name.capitalize(),
            "label": default_labels.get(regime_name, regime_name.capitalize()),
            "color": default_colors.get(regime_name, "#3b82f6"),
        },
        "_meta": {
            "interval": interval,
            "method": method,
            "missing_inputs": [],   # strict mode raised earlier if missing
            "weights": comp_weights,
        },
    }

    log.info(f"[TacticalCore] Tactical Index={fused} ({regime_name.upper()}, {interval})")
    return out


# Registry export (for queen.cli.list_signals)
EXPORTS = {"tactical_index": compute_tactical_index}

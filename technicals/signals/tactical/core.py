#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/core.py — Tactical Fusion Engine (v2.1)
# ============================================================
"""Adaptive Tactical Fusion Engine — blends regime (RScore), volatility (VolX),
and liquidity (LBX) metrics into a unified Tactical Index.

✅ Settings-driven (queen.settings.settings)
✅ Dynamically re-weights based on timeframe (weights.json)
✅ Emits regime classification (Bullish / Neutral / Bearish)
✅ Pure Polars where DF is used; otherwise dict-friendly
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import polars as pl
from queen.helpers.logger import log

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None


# --------------------------- Utils ---------------------------


def _safe_read_json(path: Path | str, fallback: dict = None) -> dict:
    try:
        p = Path(path)
        if not p.exists():
            return fallback or {}
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"[TacticalCore] Could not read {path}: {e}")
        return fallback or {}


def _zscore(values: Dict[str, float]) -> Dict[str, float]:
    arr = np.array(list(values.values()), dtype=float)
    mean = float(arr.mean()) if arr.size else 0.0
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
    """Blend RScore, VolX, and LBX into a normalized Tactical Index (settings-driven)."""
    # 1) Resolve config paths from SETTINGS
    if SETTINGS:
        cfg_dir = SETTINGS.PATHS["CONFIGS"]
        tac_cfg_path = SETTINGS.PATHS["CONFIGS"] / "tactical.json"
        w_cfg_path = SETTINGS.PATHS["CONFIGS"] / "weights.json"
    else:
        cfg_dir = Path("./configs")
        tac_cfg_path = cfg_dir / "tactical.json"
        w_cfg_path = cfg_dir / "weights.json"

    # 2) Load configs
    tac_cfg = _safe_read_json(
        tac_cfg_path,
        fallback={
            "inputs": {
                "RScore": {"weight": 0.5, "source": "RScore_norm"},
                "VolX": {"weight": 0.25, "source": "VolX_norm"},
                "LBX": {"weight": 0.25, "source": "LBX_norm"},
            },
            "normalization": {"method": "minmax", "clip": [0, 1]},
            "regimes": {"bearish": 0.3, "neutral": 0.7, "labels": {}, "colors": {}},
            "output": {"name": "Tactical_Index", "rounding": 3},
        },
    )
    weights_cfg = _safe_read_json(w_cfg_path, fallback={})

    # 3) Timeframe key → adaptive weights (optional)
    tf_key = (
        f"intraday_{interval}"
        if interval.endswith("m")
        else f"hourly_{interval}"
        if "h" in interval.lower()
        else interval.lower()
    )
    adaptive_weights = (
        weights_cfg.get("timeframes", {}).get(tf_key, {}).get("meta_layers", {}) or {}
    )

    # 4) Extract raw metric values (dict or DF)
    inputs: Dict[str, dict] = tac_cfg.get("inputs", {})
    raw: Dict[str, float] = {}
    missing: list[str] = []

    def _extract(src_key: str) -> float | None:
        if isinstance(metrics, dict):
            return metrics.get(src_key)
        if isinstance(metrics, pl.DataFrame) and src_key in metrics.columns:
            # Mean of the series as a stable scalar (can be changed to last() if desired)
            return float(pl.Series(metrics[src_key]).mean())
        return None

    for key, meta in inputs.items():
        src = meta.get("source", key)
        val = _extract(src)
        if val is None:
            missing.append(key)
            val = 0.0
        raw[key] = float(val)

    if missing:
        log.warning(f"[TacticalCore] Missing inputs: {missing} — defaulting to 0.0")

    # 5) Normalize
    norm_cfg = tac_cfg.get("normalization", {})
    method = (norm_cfg.get("method", "minmax") or "minmax").lower()
    normed = _zscore(raw) if method == "zscore" else _minmax(raw)

    # 6) Weight & fuse (base * adaptive)
    weighted: Dict[str, float] = {}
    total_w = 0.0
    for key, val in normed.items():
        base_w = float(inputs.get(key, {}).get("weight", 1.0))
        adapt_w = (
            float(adaptive_weights.get(key.upper(), 1.0)) if adaptive_weights else 1.0
        )
        w = base_w * adapt_w
        weighted[key] = val * w
        total_w += w

    fused = sum(weighted.values()) / (total_w or 1.0)

    # 7) Clip & round
    lo, hi = norm_cfg.get("clip", [0, 1])
    fused = max(min(fused, float(hi)), float(lo))
    fused = round(fused, int(tac_cfg.get("output", {}).get("rounding", 3)))

    # 8) Regime classification
    regimes = tac_cfg.get("regimes", {})
    bear_th = float(regimes.get("bearish", 0.3))
    neut_th = float(regimes.get("neutral", 0.7))
    labels = regimes.get("labels", {})
    colors = regimes.get("colors", {})

    if fused < bear_th:
        regime = "bearish"
    elif fused < neut_th:
        regime = "neutral"
    else:
        regime = "bullish"

    out = {
        "RScore_norm": round(normed.get("RScore", 0.0), 3),
        "VolX_norm": round(normed.get("VolX", 0.0), 3),
        "LBX_norm": round(normed.get("LBX", 0.0), 3),
        tac_cfg.get("output", {}).get("name", "Tactical_Index"): fused,
        "regime": {
            "name": regime.capitalize(),
            "label": labels.get(regime, regime.capitalize()),
            "color": colors.get(regime, "#3b82f6"),
        },
        "_meta": {
            "interval": interval,
            "adaptive_weights": adaptive_weights,
            "method": method,
            "missing_inputs": missing,
        },
    }

    log.info(f"[TacticalCore] Tactical Index={fused} ({regime.upper()}, {interval})")
    return out


# Registry export (for queen.cli.list_signals)
EXPORTS = {"tactical_index": compute_tactical_index}

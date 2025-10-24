# ============================================================
# quant/tactical/core.py — Tactical Fusion Engine (v2.0)
# ============================================================
"""Adaptive Tactical Fusion Engine — blends regime (RScore), volatility (VolX),
and liquidity (LBX) metrics into a unified Tactical Index.

✅ Dynamically re-weights based on timeframe from weights.json
✅ Emits regime classification (Bullish / Neutral / Bearish)
✅ Config-driven thresholds + colors from tactical.json
"""

from __future__ import annotations

import numpy as np
import polars as pl
from quant import config
from quant.utils.logs import get_logger

logger = get_logger("TacticalCore")


# ------------------------------------------------------------
# 🧩 Normalization helpers
# ------------------------------------------------------------
def _zscore(values: dict[str, float]) -> dict[str, float]:
    arr = np.array(list(values.values()), dtype=float)
    mean, std = np.mean(arr), np.std(arr) or 1
    return {k: (v - mean) / std for k, v in values.items()}


def _minmax(values: dict[str, float]) -> dict[str, float]:
    arr = np.array(list(values.values()), dtype=float)
    lo, hi = np.min(arr), np.max(arr)
    rng = (hi - lo) or 1
    return {k: (v - lo) / rng for k, v in values.items()}


# ------------------------------------------------------------
# 🧠 Tactical Fusion Core
# ------------------------------------------------------------
def compute_tactical_index(metrics: dict | pl.DataFrame, interval: str = "15m") -> dict:
    """Blend RScore, VolX, and LBX into a normalized Tactical Index (adaptive by timeframe)."""
    try:
        # ------------------------------------------------------------
        # 1️⃣ Load Tactical Fusion Config
        # ------------------------------------------------------------
        tac_cfg_path = config.get_path(
            "paths.tactical_config", fallback="./configs/tactical.json"
        )
        tac_cfg = config.load_json(tac_cfg_path)
        inputs = tac_cfg.get("inputs", {})
        norm_cfg = tac_cfg.get("normalization", {})
        output_cfg = tac_cfg.get("output", {})

        # ------------------------------------------------------------
        # 2️⃣ Load Adaptive Weights (if available)
        # ------------------------------------------------------------
        adaptive_weights = {}
        try:
            weights_cfg = config.load_json(
                config.get_path(
                    "paths.weights_config", fallback="./configs/weights.json"
                )
            )
            tf_key = (
                f"intraday_{interval}"
                if interval.endswith("m")
                else f"hourly_{interval}"
                if "h" in interval.lower()
                else interval.lower()
            )
            adaptive_weights = (
                weights_cfg.get("timeframes", {}).get(tf_key, {}).get("meta_layers", {})
                or {}
            )
            if adaptive_weights:
                logger.debug(
                    f"[Tactical] Adaptive weights for {tf_key}: {adaptive_weights}"
                )
        except Exception as e:
            logger.warning(f"[Tactical] Failed to load adaptive weights: {e}")

        # ------------------------------------------------------------
        # 3️⃣ Extract raw metric values with safe fallbacks
        # ------------------------------------------------------------
        raw, missing_keys = {}, []

        for key, meta in inputs.items():
            src_key = meta.get("source", key)
            val = None
            if isinstance(metrics, dict):
                val = metrics.get(src_key) or metrics.get(key)
            elif isinstance(metrics, pl.DataFrame) and src_key in metrics.columns:
                val = float(metrics[src_key].mean())

            if val is None:
                missing_keys.append(key)
                val = 0.0  # graceful fallback
            raw[key] = float(val)

        if missing_keys:
            logger.warning(
                f"[TacticalCore] ⚠️ Missing tactical inputs: {missing_keys} — using zeros for now."
            )

        # ------------------------------------------------------------
        # 4️⃣ Normalization
        # ------------------------------------------------------------
        method = norm_cfg.get("method", "zscore").lower()
        normed = _zscore(raw) if method == "zscore" else _minmax(raw)

        # ------------------------------------------------------------
        # 5️⃣ Weighting (fusion + adaptive scaling)
        # ------------------------------------------------------------
        weighted, total_weight = {}, 0.0

        for key, val in normed.items():
            base_w = inputs.get(key, {}).get("weight", 1.0)
            adapt_w = (
                adaptive_weights.get(key.upper(), 1.0) if adaptive_weights else 1.0
            )
            w = base_w * adapt_w
            weighted[key] = val * w
            total_weight += w

        fused_val = sum(weighted.values()) / (total_weight or 1)

        # ------------------------------------------------------------
        # 6️⃣ Clipping + rounding
        # ------------------------------------------------------------
        clip = norm_cfg.get("clip", [0, 1])
        fused_val = max(min(fused_val, clip[1]), clip[0])
        fused_val = round(fused_val, int(output_cfg.get("rounding", 3)))

        # ------------------------------------------------------------
        # 7️⃣ Regime Classification
        # ------------------------------------------------------------
        regimes = tac_cfg.get("regimes", {})
        bear_th = regimes.get("bearish", 0.3)
        neut_th = regimes.get("neutral", 0.7)
        labels = regimes.get("labels", {})
        colors = regimes.get("colors", {})

        if fused_val < bear_th:
            regime = "bearish"
        elif fused_val < neut_th:
            regime = "neutral"
        else:
            regime = "bullish"

        # ------------------------------------------------------------
        # 8️⃣ Output structure
        # ------------------------------------------------------------
        out = {
            "RScore_norm": round(normed.get("RScore", 0), 3),
            "VolX_norm": round(normed.get("VolX", 0), 3),
            "LBX_norm": round(normed.get("LBX", 0), 3),
            output_cfg.get("name", "Tactical_Index"): fused_val,
            "regime": {
                "name": regime.capitalize(),
                "label": labels.get(regime, regime.capitalize()),
                "color": colors.get(regime, "#3b82f6"),
            },
            "_meta": {
                "interval": interval,
                "adaptive_weights": adaptive_weights,
                "method": method,
                "missing_inputs": missing_keys,
            },
        }

        logger.info(
            f"[TacticalCore] ✅ Tactical Index={fused_val} ({regime.upper()} regime, adaptive weights for {interval})"
        )
        return out

    except Exception as e:
        logger.error(f"[TacticalCore] ❌ Failed to compute Tactical Index: {e}")
        return {}

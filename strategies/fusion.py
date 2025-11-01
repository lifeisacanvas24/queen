#!/usr/bin/env python3
# ============================================================
# queen/strategies/fusion.py — v10.1 (Multi-TF Strategy Fusion)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

import polars as pl

# Prefer settings/weights.py for fusion weights + thresholds
try:
    from queen.settings import (
        weights as W,  # exposes fusion_weights_for(), get_thresholds()
    )
except Exception:
    W = None  # graceful fallback


# ---------- tiny helpers ----------
def _last_float(df: pl.DataFrame, col: str, default: float = 0.0) -> float:
    if col not in df.columns or df.is_empty():
        return default
    try:
        return float(df.get_column(col).cast(pl.Float64).tail(1).item())
    except Exception:
        return default


def _last_str(df: pl.DataFrame, col: str, default: str = "") -> str:
    if col not in df.columns or df.is_empty():
        return default
    try:
        v = df.get_column(col).cast(pl.Utf8).tail(1).item()
        return "" if v is None else str(v)
    except Exception:
        return default


def _regime_to_unit(reg: str) -> float:
    r = (reg or "").upper()
    if r == "TREND":
        return 1.0
    if r == "RANGE":
        return 0.55
    if r == "VOLATILE":
        return 0.45
    if r == "NEUTRAL":
        return 0.50
    return 0.50


def _risk_band(atr_ratio: float) -> str:
    if atr_ratio >= 1.40:
        return "high"
    if atr_ratio >= 1.15:
        return "medium"
    return "low"


# ---------- core API ----------
def run_strategy(
    symbol: str,
    frames: Dict[str, pl.DataFrame],
    *,
    tf_weights: Dict[str, float] | None = None,
) -> Dict[str, Any]:
    """Inputs per TF (if present): SPS, Regime_State, ATR_Ratio, (optional CPS/VDU/etc.)
    Output structure:
      {
        'symbol': str,
        'per_tf': { tf: { strategy_score, bias, entry_ok, exit_ok, hold_reason, risk_band }, ... },
        'fused':  { score, bias, entry_ok, exit_ok, risk_band }
      }
    """
    if not frames:
        return {
            "symbol": symbol,
            "per_tf": {},
            "fused": {
                "score": 0.0,
                "bias": "neutral",
                "entry_ok": False,
                "exit_ok": False,
                "risk_band": "low",
            },
        }

    # 1) per-TF evaluation
    per_tf: Dict[str, Dict[str, Any]] = {}
    for tf, df in frames.items():
        sps = max(0.0, min(1.0, _last_float(df, "SPS", 0.50)))
        regime_unit = _regime_to_unit(_last_str(df, "Regime_State", "NEUTRAL"))
        atr_r = _last_float(df, "ATR_Ratio", 1.00)
        atr_unit = max(0.0, min(1.0, atr_r / 1.25))  # neutralization pivot ~1.25

        # simple normalized blend (tunable; can move to settings later)
        score = max(
            0.0, min(1.0, round(0.55 * sps + 0.30 * regime_unit + 0.15 * atr_unit, 3))
        )

        # thresholds (prefer settings)
        if W and hasattr(W, "get_thresholds"):
            th = W.get_thresholds(tf)
            entry_thr = float(th.get("ENTRY", 0.70))
            exit_thr = float(th.get("EXIT", 0.30))
        else:
            entry_thr, exit_thr = 0.70, 0.30

        entry_ok = score >= entry_thr
        exit_ok = score <= exit_thr
        bias = (
            "bullish"
            if score >= (entry_thr - 0.04)
            else ("bearish" if score <= (exit_thr + 0.04) else "neutral")
        )

        per_tf[tf] = {
            "strategy_score": score,
            "bias": bias,
            "entry_ok": entry_ok,
            "exit_ok": exit_ok,
            "hold_reason": "regime carry" if (not entry_ok and not exit_ok) else "",
            "risk_band": _risk_band(atr_r),
        }

    # 2) fusion weights
    if tf_weights is not None:
        weights = {tf: float(tf_weights.get(tf, 0.0)) for tf in frames}
    elif W and hasattr(W, "fusion_weights_for"):
        weights = W.fusion_weights_for(list(frames.keys()))
    else:
        eq = 1.0 / max(1, len(frames))
        weights = {tf: eq for tf in frames}

    # 3) fused thresholds (strict entry, early exit across TFs)
    if W and hasattr(W, "get_thresholds"):
        thr_list = [W.get_thresholds(tf) for tf in frames]
        entry_thr = max((float(t.get("ENTRY", 0.70)) for t in thr_list), default=0.70)
        exit_thr = min((float(t.get("EXIT", 0.30)) for t in thr_list), default=0.30)
    else:
        entry_thr, exit_thr = 0.70, 0.30

    # 4) fuse
    fused_score = round(
        sum(
            per_tf[tf]["strategy_score"] * float(weights.get(tf, 0.0)) for tf in frames
        ),
        3,
    )
    fused_bias = (
        "bullish"
        if fused_score >= (entry_thr - 0.04)
        else ("bearish" if fused_score <= (exit_thr + 0.04) else "neutral")
    )
    fused_entry = fused_score >= entry_thr
    fused_exit = fused_score <= exit_thr

    # fused risk band = max of TF bands
    band_rank = {"low": 0, "medium": 1, "high": 2}
    fused_band = max(
        (band_rank.get(per_tf[tf]["risk_band"], 0) for tf in frames), default=0
    )
    inv_rank = {v: k for k, v in band_rank.items()}

    return {
        "symbol": symbol,
        "per_tf": per_tf,
        "fused": {
            "score": fused_score,
            "bias": fused_bias,
            "entry_ok": fused_entry,
            "exit_ok": fused_exit,
            "risk_band": inv_rank.get(fused_band, "low"),
        },
    }

#!/usr/bin/env python3
# ============================================================
# queen/settings/weights.py — Multi-Timeframe Weight Map (v8.1)
# Adds validation + optional normalization helpers
# ============================================================
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Tuple

# ------------------------------------------------------------
# ⏱️ Timeframe-Based Weight Definitions (your current values)
# ------------------------------------------------------------
TIMEFRAMES: Dict[str, Dict[str, Any]] = {
    "intraday_5m": {
        "indicators": {
            "CPR": 0.2,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.2, "MCS": 0.15, "CPS": 0.1, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.05},
        "_note": "Intraday weights favor dynamic state layers (SPS, MCS).",
    },
    "intraday_15m": {
        "indicators": {
            "CPR": 0.2,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.25, "MCS": 0.2, "CPS": 0.1, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.05},
        "_note": "15m is primary execution — higher SPS/MCS.",
    },
    "intraday_30m": {
        "indicators": {
            "CPR": 0.2,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.2, "MCS": 0.2, "CPS": 0.1, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.1},
        "_note": "30m balances patterns with continuation.",
    },
    "hourly_1h": {
        "indicators": {
            "CPR": 0.15,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.2, "MCS": 0.2, "CPS": 0.15, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.1},
        "_note": "Hourly confirms intraday — CPS gains weight.",
    },
    "daily": {
        "indicators": {
            "CPR": 0.15,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.15, "MCS": 0.2, "CPS": 0.2, "RPS": 0.15},
        "patterns": {"japanese": 0.1, "cumulative": 0.1},
        "_note": "Daily emphasizes CPS/RPS for macro validation.",
    },
    "weekly": {
        "indicators": {
            "CPR": 0.1,
            "VWAP": 0.1,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.1, "MCS": 0.15, "CPS": 0.2, "RPS": 0.2},
        "patterns": {"japanese": 0.1, "cumulative": 0.15},
        "_note": "Weekly: larger CPS/RPS formations dominate.",
    },
    "monthly": {
        "indicators": {
            "CPR": 0.1,
            "VWAP": 0.1,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.05,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.05, "MCS": 0.1, "CPS": 0.25, "RPS": 0.25},
        "patterns": {"japanese": 0.05, "cumulative": 0.2},
        "_note": "Monthly dominated by CPS (trend) and RPS (macro reversals).",
    },
}

# ------------------------------------------------------------
# 🧠 Global Notes
# ------------------------------------------------------------
GLOBAL_NOTES: Dict[str, str] = {
    "1": "All weights are relative — target per timeframe ≈ 1.0.",
    "2": "You can auto-normalize at read time to avoid manual edits.",
    "3": "Pattern scores feed through CPS/RPS; indicators affect SPS/MCS.",
}

# ------------------------------------------------------------
# ⚖️ Validation / Normalization
# ------------------------------------------------------------
_TARGET = 1.0
_TOL = 0.25  # allow ±0.25 for warnings


def _sum_leaf_weights(block: Dict[str, Any]) -> float:
    total = 0.0
    for k, v in block.items():
        if k.startswith("_"):  # skip notes
            continue
        if isinstance(v, dict):
            total += _sum_leaf_weights(v)
        elif isinstance(v, (int, float)):
            total += float(v)
        # else ignore non-numeric leaves
    return total


def _collect_leaf_paths(
    block: Dict[str, Any], prefix: Tuple[str, ...] = ()
) -> list[Tuple[Tuple[str, ...], float]]:
    out = []
    for k, v in block.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            out.extend(_collect_leaf_paths(v, prefix + (k,)))
        elif isinstance(v, (int, float)):
            out.append((prefix + (k,), float(v)))
    return out


def validate_weights(strict: bool = False) -> Dict[str, float]:
    """Return raw sums per timeframe and warn if outside tolerance.
    If strict=True, raise AssertionError on any OOB sum.
    """
    sums = {}
    for tf, conf in TIMEFRAMES.items():
        s = _sum_leaf_weights(conf)
        sums[tf] = round(s, 6)
        if abs(s - _TARGET) > _TOL:
            print(f"[weights] warn: {tf} sums to {s} (±{_TOL} tol)")
            if strict:
                raise AssertionError(
                    f"{tf} weight sum {s} outside ±{_TOL} of {_TARGET}"
                )
    return sums


def normalized_view(target: float = _TARGET) -> Dict[str, Dict[str, Any]]:
    """Return a deep-copied view where all numeric leaves are scaled so the total equals `target`.
    Keeps relative proportions intact.
    """
    out = deepcopy(TIMEFRAMES)
    for tf, conf in out.items():
        s = _sum_leaf_weights(conf)
        if s <= 0:
            continue
        k = target / s
        for path, val in _collect_leaf_paths(conf):
            # mutate the deep copy along the path
            cur = conf
            for seg in path[:-1]:
                cur = cur[seg]
            cur[path[-1]] = round(val * k, 6)
    return out


# ------------------------------------------------------------
# 🧩 Public API
# ------------------------------------------------------------
def get_weights(timeframe: str, normalized: bool = True) -> Dict[str, Any]:
    """Retrieve weights for a specific timeframe.
    If normalized=True, return an auto-normalized view for that timeframe.
    """
    tf = str(timeframe)
    if normalized:
        norm = normalized_view()
        return norm.get(tf, {})
    return TIMEFRAMES.get(tf, {})


def available_timeframes() -> list[str]:
    return list(TIMEFRAMES.keys())


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Weights Settings — validation")
    pprint(validate_weights())
    print("\n🔧 Normalized demo (intraday_15m):")
    pprint(get_weights("intraday_15m", normalized=True))

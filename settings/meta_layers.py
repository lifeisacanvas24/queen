#!/usr/bin/env python3
# ============================================================
# queen/settings/meta_layers.py — Market State Meta-Layer Config (v9.1)
# Forward-only, TF-owned parsing/validation, DRY window math
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from queen.settings import timeframes as TF  # single owner of TF logic ✅

# ------------------------------------------------------------
# 🧩 Meta-Layer Configuration
# ------------------------------------------------------------
META_LAYERS: Dict[str, Dict[str, Any]] = {
    # ========================================================
    # SPS — Setup Pressure Score
    # ========================================================
    "SPS": {
        "description": (
            "Setup Pressure Score — measures coil/compression before breakout "
            "using CPR, ATR, and volume dry-up signals."
        ),
        "contexts": {
            "intraday_5m": {
                "timeframe": "5m",
                "lookback": 60,
                "min_cpr_compressions": 4,
                "volume_factor": 0.8,
            },
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 40,
                "min_cpr_compressions": 3,
                "volume_factor": 0.8,
            },
            "intraday_30m": {
                "timeframe": "30m",
                "lookback": 30,
                "min_cpr_compressions": 2,
                "volume_factor": 0.75,
            },
            "hourly_1h": {
                "timeframe": "1h",
                "lookback": 30,
                "min_cpr_compressions": 2,
                "volume_factor": 0.7,
            },
            "daily": {
                "timeframe": "1d",
                "lookback": 20,
                "min_cpr_compressions": 2,
                "volume_factor": 0.7,
            },
        },
        "_note": "SPS is elevated when CPR width < 0.3×avg width and volume < 0.8×10-bar average.",
    },
    # ========================================================
    # MCS — Momentum Continuation Score
    # ========================================================
    "MCS": {
        "description": (
            "Momentum Continuation Score — quantifies post-breakout strength "
            "using WRB count, RSI slope, and OBV alignment."
        ),
        "contexts": {
            "intraday_5m": {
                "timeframe": "5m",
                "lookback": 25,
                "min_wrbs": 3,
                "rsi_window": 14,
                "obv_window": 20,
            },
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 20,
                "min_wrbs": 2,
                "rsi_window": 14,
                "obv_window": 20,
            },
            "hourly_1h": {
                "timeframe": "1h",
                "lookback": 15,
                "min_wrbs": 1,
                "rsi_window": 14,
                "obv_window": 20,
            },
            "daily": {
                "timeframe": "1d",
                "lookback": 10,
                "min_wrbs": 1,
                "rsi_window": 14,
                "obv_window": 20,
            },
        },
        "_note": "MCS > 1.0 when WRBs appear with RSI > 55 and OBV > 5-bar average.",
    },
    # ========================================================
    # CPS — Continuation Pattern Strength
    # ========================================================
    "CPS": {
        "description": "Continuation Pattern Strength — persistence of structural patterns in recent windows.",
        "contexts": {
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 60,
                "pattern_count_window": 20,
                "min_repeat_patterns": 3,
            },
            "hourly_1h": {
                "timeframe": "1h",
                "lookback": 60,
                "pattern_count_window": 20,
                "min_repeat_patterns": 2,
            },
            "daily": {
                "timeframe": "1d",
                "lookback": 60,
                "pattern_count_window": 20,
                "min_repeat_patterns": 2,
            },
            "weekly": {
                "timeframe": "1w",
                "lookback": 26,
                "pattern_count_window": 12,
                "min_repeat_patterns": 1,
            },
        },
        "_note": "CPS increases when similar bullish/bearish patterns reappear with rising OBV.",
    },
    # ========================================================
    # RPS — Reversal Pressure Score
    # ========================================================
    "RPS": {
        "description": "Reversal Pressure Score — anticipates exhaustion via RSI divergence, volume spike, CPR rejection.",
        "contexts": {
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 40,
                "divergence_window": 10,
                "rsi_threshold": 65,
                "volume_spike_factor": 1.3,
            },
            "daily": {
                "timeframe": "1d",
                "lookback": 20,
                "divergence_window": 7,
                "rsi_threshold": 70,
                "volume_spike_factor": 1.4,
            },
            "weekly": {
                "timeframe": "1w",
                "lookback": 12,
                "divergence_window": 4,
                "rsi_threshold": 75,
                "volume_spike_factor": 1.5,
            },
        },
        "_note": "RPS > 1.0 when RSI divergence + volume spike near CPR R2/S2 zones.",
    },
}


# ------------------------------------------------------------
# 🧠 Helpers
# ------------------------------------------------------------
def get_meta_layer(name: str) -> Dict[str, Any]:
    """Return a meta-layer block (case-insensitive by key)."""
    return META_LAYERS.get((name or "").upper(), {})


def required_bars_for_days(name: str, days: int, timeframe_token: str) -> int:
    """How many bars cover `days` of history at `timeframe_token` for meta-layer `name`.
    Delegates to the canonical owner in timeframes.py for DRY.
    """
    TF.validate_token(timeframe_token)
    return TF.bars_for_days(timeframe_token, days)


def list_meta_layers() -> list[str]:
    return list(META_LAYERS.keys())


def required_lookback(name: str, timeframe_token: str) -> int:
    """Return lookback bars required for (meta-layer, timeframe_token)."""
    ml = get_meta_layer(name)
    ctxs = ml.get("contexts", {}) if ml else {}
    tf = TF.normalize_tf(timeframe_token)
    for _, ctx in ctxs.items():
        if TF.normalize_tf(ctx.get("timeframe", "")) == tf:
            lb = ctx.get("lookback", 0)
            return int(lb) if isinstance(lb, int) and lb > 0 else 0
    return 0


def window_days_for_context(name: str, bars: int, timeframe_token: str) -> int:
    """Days of data needed for `bars` @ `timeframe_token` (meta-layer aware)."""
    TF.validate_token(timeframe_token)
    return TF.window_days_for_tf(timeframe_token, bars)


def validate() -> dict:
    """Strict schema & token checks (forward-only)."""
    errs: list[str] = []
    for lname, block in META_LAYERS.items():
        if not isinstance(block, dict):
            errs.append(f"{lname}: block must be dict")
            continue
        if "contexts" not in block or not isinstance(block["contexts"], dict):
            errs.append(f"{lname}: missing/invalid 'contexts'")
            continue
        for ctx_key, ctx in block["contexts"].items():
            if not isinstance(ctx, dict):
                errs.append(f"{lname}.{ctx_key}: context must be dict")
                continue
            tf = ctx.get("timeframe")
            try:
                TF.validate_token(tf)
            except Exception as e:
                errs.append(f"{lname}.{ctx_key}: bad timeframe '{tf}' → {e}")
            lb = ctx.get("lookback", 0)
            if not isinstance(lb, int) or lb <= 0:
                errs.append(f"{lname}.{ctx_key}: 'lookback' must be positive int")
    return {"ok": len(errs) == 0, "errors": errs, "count": len(META_LAYERS)}


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Meta-Layer Configuration")
    pprint(list_meta_layers())
    print("SPS 15m lookback →", required_lookback("SPS", "15m"))
    print("RPS weekly 12 bars ≈ days →", window_days_for_context("RPS", 12, "1w"))
    pprint(validate())

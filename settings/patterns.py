#!/usr/bin/env python3
# ============================================================
# queen/settings/patterns.py — Pattern Recognition Config (v10.5)
# Canonical definitions + safe helpers + validation (forward-only)
#
# Bible v10.5 alignment:
#   • Japanese primitives: hammer, shooting_star, doji,
#       bullish_engulfing, bearish_engulfing (+ inside_bar, stars)
#   • Structural / cumulative bases and triangles intact
#   • Each pattern tagged with:
#       - role: "REVERSAL" | "CONTINUATION" | "STRUCTURAL" | "INDECISION" | "CONSOLIDATION"
#       - bias: "bullish" | "bearish" | "neutral"
#   • Contexts use context_key → timeframe_token (5m, 15m, 1d, 1w, ...)
#   • required_lookback() is the single source of truth for lookback bars.
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from queen.settings import timeframes as TF  # single owner of TF logic

__all__ = [
    "JAPANESE",
    "CUMULATIVE",
    "get_pattern",
    "list_patterns",
    "required_candles",
    "required_lookback",
    "contexts_for",
    "role_for",
    "validate",
]

# ------------------------------------------------------------
# 🕯️ Japanese Candlestick Patterns (Bible v10.5)
# ------------------------------------------------------------
JAPANESE: Dict[str, Dict[str, Any]] = {
    # --- 1-bar primitives (umbrella lines + doji) ---
    "hammer": {
        "role": "REVERSAL",        # used by Reversal Stack / Bible
        "bias": "bullish",
        "candles_required": 1,
        "contexts": {
            # intraday reversal candidate near CPR / supports
            "intraday_5m":  {"timeframe": "5m",  "lookback": 40},
            "intraday_15m": {"timeframe": "15m", "lookback": 40},
            # swing reversal on dailies
            "daily":        {"timeframe": "1d",  "lookback": 15},
        },
        "_note": "Hammer: Bullish reversal; long lower wick; strongest near CPR/S1 with volume/OBV uptick.",
    },
    "shooting_star": {
        "role": "REVERSAL",
        "bias": "bearish",
        "candles_required": 1,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 40},
            "daily":        {"timeframe": "1d",  "lookback": 15},
        },
        "_note": "Shooting Star: Bearish reversal; long upper wick; strongest near CPR/R1–R2 with OBV divergence.",
    },
    "doji": {
        "role": "INDECISION",      # treated as candidate, not standalone signal
        "bias": "neutral",
        "candles_required": 1,
        "contexts": {
            "intraday_5m":  {"timeframe": "5m",  "lookback": 25},
            "intraday_15m": {"timeframe": "15m", "lookback": 25},
            "daily":        {"timeframe": "1d",  "lookback": 10},
        },
        "_note": "Doji: Indecision marker; requires confirmation from next candle body + context (RSI/CPR/volume).",
    },

    # --- 2-bar engulfing & consolidation ---
    "bullish_engulfing": {
        "role": "REVERSAL",
        "bias": "bullish",
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 30},
            "hourly_1h":    {"timeframe": "1h",  "lookback": 25},
            "daily":        {"timeframe": "1d",  "lookback": 15},
            "weekly":       {"timeframe": "1w",  "lookback": 8},
        },
        "_note": "Bullish Engulfing: Full-body bullish reversal after decline; OBV uptick + RSI < 50 → 50+ strengthens.",
    },
    "bearish_engulfing": {
        "role": "REVERSAL",
        "bias": "bearish",
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 30},
            "hourly_1h":    {"timeframe": "1h",  "lookback": 25},
            "daily":        {"timeframe": "1d",  "lookback": 15},
            "weekly":       {"timeframe": "1w",  "lookback": 8},
        },
        "_note": "Bearish Engulfing: Exhaustion after rally; strongest with RSI > 60 rolling down and OBV contraction.",
    },
    "inside_bar": {
        "role": "CONSOLIDATION",   # used for SPS / squeeze setups
        "bias": "neutral",
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 35},
            "daily":        {"timeframe": "1d",  "lookback": 20},
        },
        "_note": "Inside Bar: Range contraction before expansion; strong precursor for SPS/VCP-style breakouts.",
    },

    # --- 3-bar star patterns (handled by patterns/composite) ---
    "morning_star": {
        "role": "REVERSAL",
        "bias": "bullish",
        "candles_required": 3,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 50},
            "daily":        {"timeframe": "1d",  "lookback": 25},
        },
        "_note": "Morning Star: 3-bar bullish reversal; ideal near lower CPR / prior demand with RSI from oversold.",
    },
    "evening_star": {
        "role": "REVERSAL",
        "bias": "bearish",
        "candles_required": 3,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 50},
            "daily":        {"timeframe": "1d",  "lookback": 25},
        },
        "_note": "Evening Star: 3-bar bearish reversal; strongest near CPR/R1–R2 with RSI > 65 rolling back sub-50.",
    },
    # NOTE:
    # Other composite patterns like Harami, Piercing Line, Dark Cloud Cover,
    # Three Soldiers/Crows, Tweezers are detected in patterns/composite.py.
    # They may reuse these roles/biases via fusion-level mapping rather than
    # needing explicit entries here (keeps registry lean).
}

# ------------------------------------------------------------
# 📈 Cumulative / Structural Patterns (Bases, Triangles, VCP)
# ------------------------------------------------------------
CUMULATIVE: Dict[str, Dict[str, Any]] = {
    "double_bottom": {
        "role": "STRUCTURAL",
        "bias": "bullish",
        "candles_required": 30,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 120},
            "hourly_1h":    {"timeframe": "1h",  "lookback": 60},
            "daily":        {"timeframe": "1d",  "lookback": 50},
            "weekly":       {"timeframe": "1w",  "lookback": 26},
        },
        "_note": "Double Bottom: Mid/long-term accumulation base; confirms with OBV breakout + CPR expansion.",
    },
    "double_top": {
        "role": "STRUCTURAL",
        "bias": "bearish",
        "candles_required": 30,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 120},
            "hourly_1h":    {"timeframe": "1h",  "lookback": 60},
            "daily":        {"timeframe": "1d",  "lookback": 50},
            "weekly":       {"timeframe": "1w",  "lookback": 26},
        },
        "_note": "Double Top: Distribution zone; aligns with extended RPS strength and weakening OBV.",
    },
    "cup_handle": {
        "role": "STRUCTURAL",
        "bias": "bullish",
        "candles_required": 60,
        "contexts": {
            "hourly_1h": {"timeframe": "1h", "lookback": 90},
            "daily":     {"timeframe": "1d", "lookback": 90},
            "weekly":    {"timeframe": "1w", "lookback": 52},
        },
        "_note": "Cup & Handle: Classic breakout structure; strongest when SPS > 1.0 and MCS > 0.5 near breakout.",
    },
    "head_shoulders": {
        "role": "STRUCTURAL",
        "bias": "bearish",
        "candles_required": 40,
        "contexts": {
            "hourly_1h": {"timeframe": "1h", "lookback": 80},
            "daily":     {"timeframe": "1d", "lookback": 60},
            "weekly":    {"timeframe": "1w", "lookback": 26},
        },
        "_note": "Head & Shoulders: Major bearish reversal; confirm with RPS > 1.0 then breaking neckline with volume.",
    },
    "inverse_head_shoulders": {
        "role": "STRUCTURAL",
        "bias": "bullish",
        "candles_required": 40,
        "contexts": {
            "hourly_1h": {"timeframe": "1h", "lookback": 80},
            "daily":     {"timeframe": "1d", "lookback": 60},
            "weekly":    {"timeframe": "1w", "lookback": 26},
        },
        "_note": "Inverse H&S: Bullish reversal; OBV rising and CPR breakout above neckline improve odds.",
    },
    "ascending_triangle": {
        "role": "CONTINUATION",
        "bias": "bullish",
        "candles_required": 25,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 60},
            "daily":        {"timeframe": "1d",  "lookback": 30},
            "weekly":       {"timeframe": "1w",  "lookback": 15},
        },
        "_note": "Ascending Triangle: Bullish continuation; often forms during SPS buildup in strong leaders.",
    },
    "descending_triangle": {
        "role": "CONTINUATION",
        "bias": "bearish",
        "candles_required": 25,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 60},
            "daily":        {"timeframe": "1d",  "lookback": 30},
            "weekly":       {"timeframe": "1w",  "lookback": 15},
        },
        "_note": "Descending Triangle: Bearish continuation; confirms with volume on breakdown + elevated RPS.",
    },
    "vcp": {
        "role": "STRUCTURAL",
        "bias": "bullish",
        "candles_required": 40,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 80},
            "daily":        {"timeframe": "1d",  "lookback": 40},
            "weekly":       {"timeframe": "1w",  "lookback": 20},
        },
        "_note": "VCP (Volatility Contraction Pattern): Bullish breakout setup; OBV rising, CPR tightening, volume dry-ups.",
    },
    # NOTE: Bible “base > 3 weeks” is typically implemented as
    # part of VCP/base detection logic. Config here is enough;
    # detector implementation can live in technicals/state.py or
    # patterns/core_structural.py later without changing this contract.
}

# ------------------------------------------------------------
# 🧠 Helpers (safe accessors)
# ------------------------------------------------------------
_VALID_CONTEXTS = {
    "intraday_5m",
    "intraday_15m",
    "hourly_1h",
    "daily",
    "weekly",
    "monthly",
}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _group_dict(group: str) -> Dict[str, Dict[str, Any]]:
    g = _norm(group)
    if g == "japanese":
        return JAPANESE
    if g == "cumulative":
        return CUMULATIVE
    return {}


def get_pattern(group: str, name: str) -> Dict[str, Any]:
    """Retrieve pattern definition safely (case-insensitive)."""
    return _group_dict(group).get(_norm(name), {})


def list_patterns(group: str | None = None) -> list[str]:
    """List available patterns (optionally by group)."""
    if not group:
        return list(JAPANESE.keys()) + list(CUMULATIVE.keys())
    d = _group_dict(group)
    return list(d.keys())


def required_candles(name: str, group: str | None = None) -> int:
    """Minimum candles the pattern definition requires."""
    groups = [group] if group else ["japanese", "cumulative"]
    for g in groups:
        p = get_pattern(g, name)
        if p:
            return max(1, int(p.get("candles_required", 1)))
    return 1


def contexts_for(name: str, group: str | None = None) -> dict:
    """Return the contexts mapping for a pattern (or {})."""
    groups = [group] if group else ["japanese", "cumulative"]
    for g in groups:
        p = get_pattern(g, name)
        if p:
            return dict(p.get("contexts") or {})
    return {}


def required_lookback(name: str, context_key: str) -> int:
    """Return lookback bars for (pattern, context_key), with safe fallback.

    This is the single source of truth that fusion / runners should call.
    """
    nm = _norm(name)
    ctx = _norm(context_key)
    for g in ["japanese", "cumulative"]:
        p = get_pattern(g, nm)
        if not p:
            continue
        c = (p.get("contexts") or {}).get(ctx) or {}
        lb = c.get("lookback")
        if isinstance(lb, int) and lb > 0:
            return lb

    # fallback heuristic if not specified
    candles = required_candles(nm, group=None)
    return max(20, candles * 10)


def role_for(name: str, group: str | None = None) -> str:
    """Return the Bible role tag for a pattern, e.g. 'REVERSAL', 'STRUCTURAL'."""
    groups = [group] if group else ["japanese", "cumulative"]
    for g in groups:
        p = get_pattern(g, name)
        if p:
            return str(p.get("role", "UNKNOWN")).upper()
    return "UNKNOWN"


# ------------------------------------------------------------
# 🔍 Validation (forward-only)
# ------------------------------------------------------------
def validate() -> dict:
    """Validate structure and context tokens. Returns summary stats."""
    errs: list[str] = []
    total = 0

    def _check_block(block: Dict[str, Dict[str, Any]], group_name: str):
        nonlocal total
        for name, cfg in block.items():
            total += 1
            cr = cfg.get("candles_required", 1)
            if not isinstance(cr, int) or cr < 1:
                errs.append(f"{group_name}.{name}: invalid candles_required={cr}")
            ctxs = cfg.get("contexts", {})
            if not isinstance(ctxs, dict):
                errs.append(f"{group_name}.{name}: contexts must be dict")
                continue
            for ckey, meta in ctxs.items():
                if ckey not in _VALID_CONTEXTS:
                    errs.append(f"{group_name}.{name}: unknown context '{ckey}'")
                tf_token = (meta or {}).get("timeframe")
                if tf_token:
                    try:
                        TF.validate_token(str(tf_token).lower())
                    except Exception as e:
                        errs.append(f"{group_name}.{name}: bad timeframe '{tf_token}': {e}")
                lb = (meta or {}).get("lookback")
                if lb is not None and (not isinstance(lb, int) or lb <= 0):
                    errs.append(f"{group_name}.{name}: lookback must be +int, got {lb}")

    _check_block(JAPANESE, "JAPANESE")
    _check_block(CUMULATIVE, "CUMULATIVE")
    return {"ok": not errs, "count": total, "errors": errs}


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Pattern Library (Bible v10.5)")
    print("Japanese:", list_patterns("japanese"))
    print("Cumulative:", list_patterns("cumulative"))
    print("hammer/daily lookback →", required_lookback("hammer", "daily"))
    print("bullish_engulfing/hourly_1h →", required_lookback("bullish_engulfing", "hourly_1h"))
    print("role_for(hammer) →", role_for("hammer"))
    print("role_for(double_top) →", role_for("double_top"))
    print("validate →")
    pprint(validate())

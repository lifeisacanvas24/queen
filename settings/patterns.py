#!/usr/bin/env python3
# ============================================================
# queen/settings/patterns.py — Pattern Recognition Config (v8.1)
# Canonical definitions + safe helpers + validation (forward-only)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from queen.settings import timeframes as TF  # single owner of TF logic

# ------------------------------------------------------------
# 🕯️ Japanese Candlestick Patterns
# ------------------------------------------------------------
JAPANESE: Dict[str, Dict[str, Any]] = {
    "hammer": {
        "candles_required": 1,
        "contexts": {
            "intraday_5m": {"timeframe": "5m", "lookback": 40},
            "intraday_15m": {"timeframe": "15m", "lookback": 40},
            "daily": {"timeframe": "1d", "lookback": 15},
        },
        "_note": "Hammer: Bullish reversal; long lower wick; confirms best with volume uptick.",
    },
    "shooting_star": {
        "candles_required": 1,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 40},
            "daily": {"timeframe": "1d", "lookback": 15},
        },
        "_note": "Shooting Star: Bearish reversal; long upper wick; confirms with OBV divergence.",
    },
    "doji": {
        "candles_required": 1,
        "contexts": {
            "intraday_5m": {"timeframe": "5m", "lookback": 25},
            "intraday_15m": {"timeframe": "15m", "lookback": 25},
            "daily": {"timeframe": "1d", "lookback": 10},
        },
        "_note": "Doji: Indecision marker; confirmation needed from next candle body expansion.",
    },
    "engulfing_bullish": {
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 30},
            "hourly_1h": {"timeframe": "1h", "lookback": 25},
            "daily": {"timeframe": "1d", "lookback": 15},
            "weekly": {"timeframe": "1w", "lookback": 8},
        },
        "_note": "Bullish Engulfing: Full-body reversal; OBV uptick strengthens reliability.",
    },
    "engulfing_bearish": {
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 30},
            "hourly_1h": {"timeframe": "1h", "lookback": 25},
            "daily": {"timeframe": "1d", "lookback": 15},
            "weekly": {"timeframe": "1w", "lookback": 8},
        },
        "_note": "Bearish Engulfing: Marks exhaustion after extended rally; OBV contraction confirms.",
    },
    "inside_bar": {
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 35},
            "daily": {"timeframe": "1d", "lookback": 20},
        },
        "_note": "Inside Bar: Consolidation before expansion; strong precursor for SPS buildup.",
    },
    "morning_star": {
        "candles_required": 3,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 50},
            "daily": {"timeframe": "1d", "lookback": 25},
        },
        "_note": "Morning Star: 3-bar bullish reversal sequence; ideal near lower CPR zone.",
    },
    "evening_star": {
        "candles_required": 3,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 50},
            "daily": {"timeframe": "1d", "lookback": 25},
        },
        "_note": "Evening Star: 3-bar bearish reversal; confirms with RSI > 65 dropping to < 50.",
    },
}

# ------------------------------------------------------------
# 📈 Cumulative / Structural Patterns
# ------------------------------------------------------------
CUMULATIVE: Dict[str, Dict[str, Any]] = {
    "double_bottom": {
        "candles_required": 30,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 120},
            "hourly_1h": {"timeframe": "1h", "lookback": 60},
            "daily": {"timeframe": "1d", "lookback": 50},
            "weekly": {"timeframe": "1w", "lookback": 26},
        },
        "_note": "Double Bottom: Mid/long-term accumulation base; confirms with OBV breakout.",
    },
    "double_top": {
        "candles_required": 30,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 120},
            "hourly_1h": {"timeframe": "1h", "lookback": 60},
            "daily": {"timeframe": "1d", "lookback": 50},
            "weekly": {"timeframe": "1w", "lookback": 26},
        },
        "_note": "Double Top: Distribution zone; matches high RPS readings.",
    },
    "cup_handle": {
        "candles_required": 60,
        "contexts": {
            "hourly_1h": {"timeframe": "1h", "lookback": 90},
            "daily": {"timeframe": "1d", "lookback": 90},
            "weekly": {"timeframe": "1w", "lookback": 52},
        },
        "_note": "Cup & Handle: Classic breakout structure; aligns with SPS > 1.0 and MCS > 0.5.",
    },
    "head_shoulders": {
        "candles_required": 40,
        "contexts": {
            "hourly_1h": {"timeframe": "1h", "lookback": 80},
            "daily": {"timeframe": "1d", "lookback": 60},
            "weekly": {"timeframe": "1w", "lookback": 26},
        },
        "_note": "Head & Shoulders: Bearish reversal; confirm with RPS > 1.0 and RSI divergence.",
    },
    "inverse_head_shoulders": {
        "candles_required": 40,
        "contexts": {
            "hourly_1h": {"timeframe": "1h", "lookback": 80},
            "daily": {"timeframe": "1d", "lookback": 60},
            "weekly": {"timeframe": "1w", "lookback": 26},
        },
        "_note": "Inverse H&S: Bullish reversal; confirm with OBV rising and CPR breakout.",
    },
    "ascending_triangle": {
        "candles_required": 25,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 60},
            "daily": {"timeframe": "1d", "lookback": 30},
            "weekly": {"timeframe": "1w", "lookback": 15},
        },
        "_note": "Ascending Triangle: Bullish continuation; forms during SPS buildup.",
    },
    "descending_triangle": {
        "candles_required": 25,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 60},
            "daily": {"timeframe": "1d", "lookback": 30},
            "weekly": {"timeframe": "1w", "lookback": 15},
        },
        "_note": "Descending Triangle: Bearish continuation; confirms with RPS elevation.",
    },
    "vcp": {
        "candles_required": 40,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 80},
            "daily": {"timeframe": "1d", "lookback": 40},
            "weekly": {"timeframe": "1w", "lookback": 20},
        },
        "_note": "VCP (Volatility Contraction Pattern): Bullish breakout trigger; OBV rising and CPR tightening.",
    },
}


# ------------------------------------------------------------
# 🧠 Helpers (safe accessors)
# ------------------------------------------------------------
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


def required_lookback(name: str, context_key: str) -> int:
    """Return lookback bars for (pattern, context_key)."""
    ctx = _norm(context_key)
    for g in ["japanese", "cumulative"]:
        p = get_pattern(g, name)
        if not p:
            continue
        c = (p.get("contexts") or {}).get(ctx) or {}
        lb = c.get("lookback")
        if isinstance(lb, int) and lb > 0:
            return lb
    # fallback heuristic if not specified
    candles = required_candles(name, group=None)
    # simple, safe: 10× candles, min 20
    return max(20, candles * 10)


# ------------------------------------------------------------
# 🔍 Validation (forward-only)
# ------------------------------------------------------------
_VALID_CONTEXTS = {
    "intraday_5m",
    "intraday_15m",
    "hourly_1h",
    "daily",
    "weekly",
    "monthly",
}


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
                # timeframe tokens inside context are optional; if present validate
                tf_token = (meta or {}).get("timeframe")
                if tf_token:
                    try:
                        TF.validate_token(str(tf_token).lower())
                    except Exception as e:
                        errs.append(
                            f"{group_name}.{name}: bad timeframe '{tf_token}': {e}"
                        )
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

    print("🧩 Queen Pattern Library")
    pprint(list_patterns("japanese"))
    print("hammer/daily lookback →", required_lookback("hammer", "daily"))
    print(
        "engulfing_bullish/1h via ctx →",
        required_lookback("engulfing_bullish", "hourly_1h"),
    )
    print("validate →", validate())

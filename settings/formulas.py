#!/usr/bin/env python3
# ============================================================
# queen/settings/formulas.py — Canonical Indicator & Meta-Layer Definitions (v9.1)
# Forward-only, Polars-first notes, light validation
# ============================================================
from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 🧩 Indicator Formulas
# ------------------------------------------------------------
INDICATORS: Dict[str, Dict[str, Any]] = {
    "RSI": {
        "formula": "RSI = 100 - (100 / (1 + (Avg(Gains, N) / Avg(Losses, N))))",
        "inputs": ["Close"],
        "params": {"N": 14},
        "signal": "Momentum oscillator between 0–100. Bullish bias when RSI crosses 50–65; bearish when below 45–35.",
    },
    "ATR": {
        "formula": "ATR = EMA(TrueRange, N); TrueRange = max(High - Low, |High - PrevClose|, |Low - PrevClose|)",
        "inputs": ["High", "Low", "Close"],
        "params": {"N": 14},
        "signal": "Measures volatility expansion; higher ATR = wider stops and stronger breakouts.",
    },
    "VWAP": {
        "formula": "VWAP = (Σ(Price_i × Volume_i)) / Σ(Volume_i)",
        "inputs": ["TypicalPrice = (High + Low + Close)/3", "Volume"],
        "signal": "Price above VWAP implies strength; below VWAP implies weakness.",
    },
    "OBV": {
        "formula": "OBV_t = OBV_{t-1} + Volume_t × sign(Close_t - Close_{t-1})",
        "inputs": ["Close", "Volume"],
        "signal": "Tracks volume flow direction; rising OBV with price = accumulation.",
    },
    "ADX": {
        "formula": "ADX = EMA(DI+, N) / (DI+ + DI−); DI± = 100 × EMA((+DM or -DM)/TR, N)",
        "inputs": ["High", "Low"],
        "signal": "Quantifies trend strength; >25 = trending, <20 = consolidation.",
    },
    "CPR": {
        "formula": {
            "Pivot": "(High + Low + Close) / 3",
            "BC": "(High + Low) / 2",
            "TC": "(Pivot - BC) + Pivot",
        },
        "compression": "Compression = (TC - BC) / Pivot; narrow CPR → buildup",
        "signal": "CPR width < 0.3×avg width indicates high compression → SPS rise.",
    },
    "MACD": {
        "formula": "MACD = EMA(Close, Fast) - EMA(Close, Slow); Signal = EMA(MACD, SignalPeriod); Histogram = MACD - Signal",
        "signal": "Histogram slope used for early momentum curvature detection (SPS/MCS).",
    },
    "ICHIMOKU": {
        "formula": {
            "Tenkan": "(Highest(High,9) + Lowest(Low,9)) / 2",
            "Kijun": "(Highest(High,26) + Lowest(Low,26)) / 2",
            "SpanA": "(Tenkan + Kijun) / 2 (shifted 26 forward)",
            "SpanB": "(Highest(High,52) + Lowest(Low,52)) / 2 (shifted 26 forward)",
        },
        "signal": "Price above both spans = bullish cloud; Tenkan/Kijun cross inside cloud = early breakout (SPS boost).",
    },
    "HEIKINASHI": {
        "formula": {
            "HA_Close": "(O + H + L + C) / 4",
            "HA_Open": "(Prev_HA_Open + Prev_HA_Close) / 2",
        },
        "signal": "Smoother trend representation; used for CPS trend continuation scoring.",
    },
    "VOLUME": {
        "VDU": "Volume_t ≤ 0.5 × AvgVolume(10)",
        "Spike": "Volume_t ≥ 1.5 × AvgVolume(10)",
        "signal": "VDU → low-activity coil; Spike → breakout validation.",
    },
}

# ------------------------------------------------------------
# 🕯️ Pattern Recognition Formulas
# ------------------------------------------------------------
PATTERNS: Dict[str, str] = {
    "ENGULFING_BULLISH": "Close_t > Open_t and Open_t < Close_{t-1} and Body_t > Body_{t-1}",
    "HAMMER": "(LowerWick ≥ 2 × Body) and (UpperWick ≤ 0.3 × Body)",
    "SHOOTING_STAR": "(UpperWick ≥ 2 × Body) and (LowerWick ≤ 0.3 × Body)",
    "DOJI": "|Close - Open| ≤ 0.1 × (High - Low)",
    "DOUBLE_BOTTOM": "Two swing lows within ±2% of each other; neckline breakout confirms pattern",
    "VCP": "Sequentially contracting swing ranges + rising OBV",
}

# ------------------------------------------------------------
# 🧠 Meta-Layer Formulas
# ------------------------------------------------------------
META_LAYERS: Dict[str, Dict[str, Any]] = {
    "SPS": {
        "formula": "SPS = f(CompressionRatio ↓, VolumeDryUp ↑, ATR_Trend ↑)",
        "components": ["CPR width", "Volume ratio", "ATR slope"],
        "signal": "High SPS = compression + contraction → pre-breakout coil",
    },
    "MCS": {
        "formula": "MCS = f(WRB_count, RSI_slope, OBV_gradient)",
        "signal": "Measures continuation momentum; high after breakout with RSI > 55 and OBV rising.",
    },
    "CPS": {
        "formula": "CPS = f(PatternRecurrence / Lookback)",
        "signal": "Persistence of similar bullish/bearish patterns; consistency = trend strength.",
    },
    "RPS": {
        "formula": "RPS = f(RSI_Divergence, Volume_Spike, CPR_Rejection)",
        "signal": "Detects early reversals near exhaustion zones (R2/S2 rejections).",
    },
}

# ------------------------------------------------------------
# ⚖️ Composite Scoring Logic
# ------------------------------------------------------------
COMPOSITE_SCORE: Dict[str, Any] = {
    "formula": "Score = Σ(Indicator_i × Weight_i) + Σ(MetaLayer_j × Weight_j) + Σ(Pattern_k × Weight_k)",
    "normalized": "All weights per timeframe normalized to ≈ 1.0",
    "range": "0–10",
    "signal": {
        ">= 8.0": "Strong setup (confirmed breakout or continuation)",
        "6.0–7.9": "Building setup (watchlist candidate)",
        "< 6.0": "Weak / rangebound",
    },
}

# ------------------------------------------------------------
# 🧾 Notes (Polars-first)
# ------------------------------------------------------------
NOTES: Dict[str, str] = {
    "1": "All formulas are symbolic; computation should use Polars/Numpy in the engine (no pandas).",
    "2": "Meta-layer formulas aggregate weighted indicators and pattern confirmations dynamically.",
    "3": "CPS/RPS act as stabilizers to prevent false breakouts.",
    "4": "VDU/Volume spike states modulate SPS weighting adaptively.",
}


# ------------------------------------------------------------
# 🧩 Helpers
# ------------------------------------------------------------
def indicator_names() -> list[str]:
    return list(INDICATORS.keys())


def pattern_names() -> list[str]:
    return list(PATTERNS.keys())


def meta_layer_names() -> list[str]:
    return list(META_LAYERS.keys())


def get_indicator(name: str) -> Dict[str, Any]:
    return INDICATORS.get((name or "").upper(), {})


def get_pattern(name: str) -> str:
    return PATTERNS.get((name or "").upper(), "")


def get_meta_layer(name: str) -> Dict[str, Any]:
    return META_LAYERS.get((name or "").upper(), {})


def validate() -> dict:
    """Light sanity checks: uppercase keys + basic shapes."""
    errs: list[str] = []

    def _check_upper(block: dict, label: str):
        for k in block:
            if k != k.upper():
                errs.append(f"{label}: key '{k}' should be UPPERCASE")

    _check_upper(INDICATORS, "INDICATORS")
    _check_upper(PATTERNS, "PATTERNS")
    _check_upper(META_LAYERS, "META_LAYERS")

    # ensure indicators have a formula/signal field
    for k, v in INDICATORS.items():
        if not isinstance(v, dict) or ("formula" not in v and "VDU" not in v):
            errs.append(f"INDICATOR {k}: missing 'formula'/shape")

    return {"ok": len(errs) == 0, "errors": errs}


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧮 Queen Formulas Library")
    pprint(get_indicator("RSI"))
    pprint(get_meta_layer("SPS"))
    pprint(COMPOSITE_SCORE)
    pprint(validate())

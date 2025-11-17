#!/usr/bin/env python3
# ============================================================
# queen/settings/cockpit_schema.py — v1.0
# Canonical cockpit row schema + tooltips (front-end contract)
# ============================================================
from __future__ import annotations

from typing import Dict, List

# Display order (grouped by category)
FIELD_ORDER: List[str] = [
    # Core identity
    "symbol", "cmp", "held",

    # Instrument strip (Upstox-style)
    "open", "high", "low", "prev_close",
    "volume", "avg_price",
    "upper_circuit", "lower_circuit",
    "52w_high", "52w_low",

    # Tactical result
    "score", "early", "decision", "bias",
    "Tactical_Index", "regime",

    # Pattern / reversal
    "PatternScore", "PatternBias", "TopPattern",
    "Reversal_Score", "Reversal_Stack_Alert",

    # Volatility / regime drivers
    "RScore_norm", "VolX_norm", "LBX_norm",
    "VolX_bias",

    # Context + levels
    "vwap_zone", "cpr_ctx",
    "entry", "sl", "targets",
    "atr", "rsi", "ema_bias", "ema50", "obv", "cpr",

    # Meta
    "advice", "notes",
    "pnl_abs", "pnl_pct",
]


# Simple category hint if you want to group columns in UI later
FIELD_CATEGORY: Dict[str, str] = {
    "symbol": "core",
    "cmp": "core",
    "held": "core",

    "open": "instrument",
    "high": "instrument",
    "low": "instrument",
    "prev_close": "instrument",
    "volume": "instrument",
    "avg_price": "instrument",
    "upper_circuit": "instrument",
    "lower_circuit": "instrument",
    "52w_high": "instrument",
    "52w_low": "instrument",

    "score": "tactical",
    "early": "tactical",
    "decision": "tactical",
    "bias": "tactical",
    "Tactical_Index": "tactical",
    "regime": "tactical",

    "PatternScore": "pattern",
    "PatternBias": "pattern",
    "TopPattern": "pattern",
    "Reversal_Score": "pattern",
    "Reversal_Stack_Alert": "pattern",

    "RScore_norm": "drivers",
    "VolX_norm": "drivers",
    "LBX_norm": "drivers",
    "VolX_bias": "drivers",

    "vwap_zone": "context",
    "cpr_ctx": "context",
    "entry": "levels",
    "sl": "levels",
    "targets": "levels",
    "atr": "levels",
    "rsi": "levels",
    "ema_bias": "levels",
    "ema50": "levels",
    "obv": "levels",
    "cpr": "levels",

    "advice": "meta",
    "notes": "meta",
    "pnl_abs": "meta",
    "pnl_pct": "meta",
}


# Human-readable tooltips (short, “trader brain”)
FIELD_TOOLTIPS: Dict[str, str] = {
    "symbol": "Ticker symbol.",
    "cmp": "Last traded price (CMP).",
    "held": "You currently hold this symbol in the selected book.",

    "open": "Today’s opening price.",
    "high": "Intraday high for the current session.",
    "low": "Intraday low for the current session.",
    "prev_close": "Previous session closing price.",
    "volume": "Total traded quantity for the current session.",
    "avg_price": "Volume-weighted average price (VWAP-style) for the session.",
    "upper_circuit": "Exchange-defined upper circuit price for the day.",
    "lower_circuit": "Exchange-defined lower circuit price for the day.",
    "52w_high": "52-week highest traded price.",
    "52w_low": "52-week lowest traded price.",

    "score": "0–10 tactical strength based on EMA/RSI/VWAP/CPR/OBV plus early cues.",
    "early": "Early-signal intensity (0–10); higher = more ‘pre-breakout’ feel.",
    "decision": "Suggested action: BUY / ADD / HOLD / AVOID / EXIT.",
    "bias": "High-level directional bias (Long / Neutral / Weak).",
    "Tactical_Index": "0–1 fused tactical index from regime, volatility, liquidity and pattern context.",
    "regime": "Tactical regime object with name/label/color (Bullish / Neutral / Bearish).",

    "PatternScore": "Pattern fusion score combining candlesticks and structure.",
    "PatternBias": "Net pattern bias (bullish / bearish / neutral).",
    "TopPattern": "Most influential detected pattern at the moment.",
    "Reversal_Score": "Reversal confluence score (regime + divergence + squeeze + traps + patterns).",
    "Reversal_Stack_Alert": "Readable label from reversal stack (e.g., Confluence BUY / SELL).",

    "RScore_norm": "Normalized regime score (0–1) from higher-order market regime engine.",
    "VolX_norm": "Normalized volatility expansion/compression score.",
    "LBX_norm": "Normalized liquidity breadth score.",
    "VolX_bias": "Textual volatility bias (expansion / contraction / normal).",

    "vwap_zone": "Whether CMP is Above/At/Below current VWAP.",
    "cpr_ctx": "Context of CMP relative to CPR pivot (Above/Below/At).",
    "entry": "Recommended trigger price for fresh or additional entry.",
    "sl": "Suggested stop loss level.",
    "targets": "Target ladder (T1/T2/T3) derived from ATR and structure.",
    "atr": "Average True Range (ATR-14) – typical intraday volatility.",
    "rsi": "Relative Strength Index (RSI-14) value.",
    "ema_bias": "Trend bias from EMA stack (Bullish / Bearish / Neutral).",
    "ema50": "50-period EMA; medium-term trend reference.",
    "obv": "On-Balance Volume trend (Rising / Falling / Flat).",
    "cpr": "Current day’s CPR pivot level.",

    "advice": "Plain-English playbook guidance for this symbol.",
    "notes": "Short context notes: early cues, UC/LC proximity, key drivers.",
    "pnl_abs": "Current unrealized profit/loss in absolute terms for your position.",
    "pnl_pct": "Current unrealized profit/loss as a percentage.",
}

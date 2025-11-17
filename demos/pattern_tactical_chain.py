#!/usr/bin/env python3
# ============================================================
# queen/demos/pattern_tactical_chain_demo.py
# ------------------------------------------------------------
# End-to-end demo for the Bible v10.5 chain:
#
#   candles → indicators/state → patterns → PatternComponent
#           → tactical_index
#
# This is a *demo* script, not a test. Safe to run locally:
#   python -m queen.demos.pattern_tactical_chain_demo
# ============================================================

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np
import polars as pl

# --- Core plumbing imports ----------------------------------
from queen.technicals.indicators.all import attach_all_indicators
from queen.technicals.indicators.state import attach_state_features
from queen.technicals.patterns.runner import run_patterns
from queen.technicals.signals.pattern_fusion import compute_pattern_component
from queen.technicals.signals.reversal_summary import summarize_reversal_patterns
from queen.technicals.signals.tactical.core import compute_tactical_index


# ------------------------------------------------------------
# 1) Synthetic OHLCV generator (one symbol, one timeframe)
# ------------------------------------------------------------
def _make_synthetic_df(n: int = 120, *, symbol: str = "DEMO") -> pl.DataFrame:
    """Create a small sine-wave + noise OHLCV DataFrame for demo purposes.
    """
    np.random.seed(42)
    x = np.linspace(0, 6 * math.pi, n)

    base = 100 + 2.0 * np.sin(x)  # gentle trend + oscillation
    noise = np.random.normal(0, 0.4, size=n)

    close = base + noise
    open_ = close + np.random.normal(0, 0.3, size=n)
    high = np.maximum(open_, close) + np.abs(np.random.normal(0.2, 0.1, size=n))
    low = np.minimum(open_, close) - np.abs(np.random.normal(0.2, 0.1, size=n))
    volume = 1_000_000 + np.random.normal(0, 50_000, size=n)

    ts = pl.datetime_range(
        start=pl.datetime(2025, 1, 1, 9, 15),
        end=pl.datetime(2025, 1, 1, 9, 15) + pl.duration(minutes=5 * (n - 1)),
        interval="5m",
        eager=True,
    )

    return pl.DataFrame(
        {
            "timestamp": ts,
            "symbol": [symbol] * n,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


# ------------------------------------------------------------
# 2) Run full Bible v10.5 chain on the DF
# ------------------------------------------------------------
def run_pattern_tactical_chain(
    *,
    context: str = "intraday_15m",
    patterns: List[str] | None = None,
) -> Dict[str, object]:
    """Pipeline:
    raw_df
      → attach_all_indicators (EMA/RSI/ATR/VWAP + Keltner/MACD/Volume/Breadth)
      → run_patterns (Japanese + composite flags)
      → attach_state_features (credibility, base_3w, vol_delta, rsi_density, LQS)
      → summarize_reversal_patterns
      → compute_pattern_component
      → compute_tactical_index (with PatternComponent as one input)
    """
    # 1) Synthetic candles
    df = _make_synthetic_df()
    print("🔹 Raw DF (tail):")
    print(df.tail(5), "\n")

    # 2) Attach indicators (optional but realistic)
    df_ind = attach_all_indicators(df, context=context)
    print("🔹 With indicators (columns):")
    print([c for c in df_ind.columns if c not in df.columns][:10], "...", "\n")

    # 3) Run pattern detectors (core + composite)
    df_patterns = run_patterns(df_ind)
    print("🔹 Pattern columns present:")
    pat_cols = [c for c in df_patterns.columns if c in
                ["doji", "hammer", "shooting_star",
                 "bullish_engulfing", "bearish_engulfing",
                 "pattern_name", "pattern_bias", "confidence"]]
    print(pat_cols, "\n")

    # 4) Attach state features (credibility, base_3w, vol_delta, rsi_density, LQS)
    df_state = attach_state_features(
        df_patterns,
        context=context,
        patterns=patterns,
    )

    print("🔹 State columns sample (tail):")
    state_cols = [
        c for c in df_state.columns
        if any(
            c.startswith(prefix)
            for prefix in ("hammer_", "shooting_star_", "bullish_engulfing_",
                           "bearish_engulfing_", "doji_", "base_3w",
                           "vol_delta", "rsi_density", "liquidity_stability")
        )
    ]
    print(state_cols)
    print(df_state.select(state_cols).tail(5), "\n")

    # 5) Reversal summary snapshot
    rev_summary = summarize_reversal_patterns(df_state, context=context, patterns=patterns)
    print("🔹 Reversal summary snapshot:")
    print(rev_summary, "\n")

    # 6) PatternFusion → PatternComponent block
    pattern_block = compute_pattern_component(
        df_state,
        context=context,
        patterns=patterns,
        weight=0.25,  # Bible: patterns contribute up to ±0.25 to fusion
    )
    print("🔹 Pattern fusion block:")
    print(pattern_block, "\n")

    # 7) Build minimal metrics dict for Tactical Index
    #
    # In production, RScore_norm / VolX_norm / LBX_norm come from:
    #   • regime engine
    #   • volatility fusion
    #   • liquidity breadth
    #
    # For this demo we just use simple placeholders so you see how
    # PatternComponent joins the fusion.
    metrics = {
        "RScore_norm": 0.55,  # pretend mildly bullish regime
        "VolX_norm": 0.45,    # moderate volatility
        "LBX_norm": 0.60,     # decent liquidity
        "PatternComponent": pattern_block["PatternComponent"],
    }

    tac = compute_tactical_index(metrics, interval="15m")
    print("🔹 Tactical Index output:")
    print(tac, "\n")

    return {
        "df_final": df_state,
        "reversal_summary": rev_summary,
        "pattern_block": pattern_block,
        "tactical_index": tac,
    }


# ------------------------------------------------------------
# 3) Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Running Pattern → State → Fusion → Tactical demo (Bible v10.5)...\n")
    out = run_pattern_tactical_chain(context="intraday_15m")
    print("✅ Demo completed.")

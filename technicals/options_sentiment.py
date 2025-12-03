#!/usr/bin/env python3
# ============================================================
# options_sentiment.py — Hybrid Options Sentiment Engine
# ============================================================
from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl

from queen.helpers.fno_universe import is_fno
from queen.helpers.options_catalog import get_atm_ladder

# ============================================================
# Internal utilities
# ============================================================

def _compute_pcr(df: pl.DataFrame) -> Optional[float]:
    puts = df.filter(pl.col("instrument_type") == "PE")["open_interest"].sum()
    calls = df.filter(pl.col("instrument_type") == "CE")["open_interest"].sum()
    return float(puts / calls) if calls > 0 else None


def _classify_oi_change(df: pl.DataFrame) -> Dict[str, str]:
    """Expect df to contain:
    strike_price, instrument_type, open_interest, prev_open_interest
    """
    out = {}

    for t in ("CE", "PE"):
        d = df.filter(pl.col("instrument_type") == t)
        if d.is_empty():
            out[t] = "unknown"
            continue

        oi = d["open_interest"].sum()
        prev = d["prev_open_interest"].sum()
        price_now = d["close"].max() if "close" in d.columns else None
        price_prev = d["prev_close"].max() if "prev_close" in d.columns else None

        if price_now is None or price_prev is None:
            out[t] = "unknown"
            continue

        dp = price_now - price_prev
        doi = oi - prev

        if dp > 0 and doi > 0:
            out[t] = "lbu"  # Long Build-Up
        elif dp < 0 and doi < 0:
            out[t] = "luu"  # Long Unwinding
        elif dp > 0 and doi < 0:
            out[t] = "scu"  # Short Covering
        elif dp < 0 and doi > 0:
            out[t] = "sbu"  # Short Build-Up
        else:
            out[t] = "neutral"

    return out


def _max_pain(df: pl.DataFrame) -> Optional[float]:
    """Max Pain = strike with highest combined (CE+PE) OI.
    Derived only from LIVE chain, no catalog.
    """
    if df.is_empty():
        return None

    out = (
        df.group_by("strike_price")
        .agg(pl.col("open_interest").sum().alias("total_oi"))
        .sort("total_oi", descending=True)
    )

    return float(out["strike_price"][0]) if out.height > 0 else None


# ============================================================
# MAIN API
# ============================================================

def compute_options_sentiment(
    symbol: str,
    mode: str,
    ltp: float,
    chain_df: pl.DataFrame,
    prev_chain_df: Optional[pl.DataFrame] = None,
) -> Dict[str, Any]:
    """Compute hybrid options sentiment; safe neutral fallback for non-F&O.

    Returns dict:
      bias: bullish / bearish / neutral
      sentiment_score: 0–100
      pcr
      atm_pressure
      max_pain
      max_pain_distance
      oi_change_call
      oi_change_put
    """
    # ------------------------------------------------------------
    # Neutral path (non-F&O symbols)
    # ------------------------------------------------------------
    if not is_fno(symbol):
        return {
            "bias": "neutral",
            "sentiment_score": 50,
            "reason": "non_fno_symbol",
            "pcr": None,
            "max_pain": None,
            "atm_pressure": None,
        }

    # ------------------------------------------------------------
    # Inputs validation
    # ------------------------------------------------------------
    if chain_df.is_empty():
        return {
            "bias": "neutral",
            "sentiment_score": 50,
            "reason": "empty_chain",
        }

    # Inject previous chain if present
    if prev_chain_df is not None:
        chain_df = chain_df.join(
            prev_chain_df.select([
                "strike_price",
                "instrument_type",
                "open_interest",
                "close"
            ]).rename({
                "open_interest": "prev_open_interest",
                "close": "prev_close"
            }),
            on=["strike_price", "instrument_type"],
            how="left",
        )
    else:
        chain_df = chain_df.with_columns([
            pl.lit(0).alias("prev_open_interest"),
            pl.lit(ltp).alias("prev_close"),  # fallback
        ])


    # ------------------------------------------------------------
    # PCR
    # ------------------------------------------------------------
    pcr = _compute_pcr(chain_df)

    # ------------------------------------------------------------
    # OI Change Classification (CE & PE)
    # ------------------------------------------------------------
    oi_class = _classify_oi_change(chain_df)

    # ------------------------------------------------------------
    # Max Pain (from LIVE, not catalog)
    # ------------------------------------------------------------
    mp = _max_pain(chain_df)
    mp_dist = (ltp - mp) if mp else None

    # ------------------------------------------------------------
    # ATM Ladder
    # ------------------------------------------------------------
    expiries = chain_df["expiry"].unique().to_list()
    expiry = expiries[0] if expiries else None

    strikes = chain_df["strike_price"].unique().sort().to_list()
    ladder = get_atm_ladder(strikes, ltp)

    atm = ladder.get("atm")
    if atm:
        ce_atm_oi = chain_df.filter(
            (pl.col("strike_price") == atm) & (pl.col("instrument_type") == "CE")
        )["open_interest"].sum()

        pe_atm_oi = chain_df.filter(
            (pl.col("strike_price") == atm) & (pl.col("instrument_type") == "PE")
        )["open_interest"].sum()

        atm_pressure = pe_atm_oi - ce_atm_oi
    else:
        atm_pressure = None

    # ------------------------------------------------------------
    # Derive Bias
    # ------------------------------------------------------------
    if atm_pressure is None or pcr is None:
        bias = "neutral"
        score = 50
    else:
        if pcr > 1.1 and atm_pressure > 0:
            bias = "bullish"
            score = 70
        elif pcr < 0.9 and atm_pressure < 0:
            bias = "bearish"
            score = 30
        else:
            bias = "neutral"
            score = 50

    return {
        "bias": bias,
        "sentiment_score": score,
        "pcr": pcr,
        "max_pain": mp,
        "max_pain_distance": mp_dist,
        "atm_pressure": atm_pressure,
        "oi_change_call": oi_class.get("CE"),
        "oi_change_put": oi_class.get("PE"),
        "expiry": expiry,
        "atm": atm,
    }

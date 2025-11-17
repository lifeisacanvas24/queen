#!/usr/bin/env python3
# ============================================================
# queen/services/cockpit_row.py — v1.0
# Canonical cockpit row builder (back-end contract)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl

from queen.services.enrich_instruments import enrich_instrument_snapshot
from queen.services.enrich_tactical import enrich_indicators as enrich_tactical
from queen.services.scoring import action_for, compute_indicators

# Keys we promise to expose to the front-end instrument strip
_INSTRUMENT_KEYS = (
    "open",
    "high",
    "low",
    "prev_close",
    "volume",
    "avg_price",
    "upper_circuit",
    "lower_circuit",
    "52w_high",
    "52w_low",
)


def build_cockpit_row(
    symbol: str,
    df: pl.DataFrame,
    *,
    interval: str = "15m",
    book: str = "all",
    tactical: Optional[Dict[str, Any]] = None,
    pattern: Optional[Dict[str, Any]] = None,
    reversal: Optional[Dict[str, Any]] = None,
    volatility: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a fully enriched cockpit row for `symbol`.

    Pipeline:
      1) compute_indicators(df)           → base indicators (CMP, RSI, ATR, CPR, EMA…)
      2) enrich_instrument_snapshot(...)  → OHLC + volume + UC/LC + 52W band
      3) enrich_tactical(...)             → Tactical_Index / Pattern / VolX dicts (optional)
      4) action_for(...)                  → decision, score, ladders
      5) bubble instrument keys into row
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {}

    base = compute_indicators(df)
    if not base:
        return {}

    # Keep DF for early-signal fusion in scoring.action_for
    base["_df"] = df

    # 1) Instrument snapshot strip (Upstox-style)
    base = enrich_instrument_snapshot(symbol, base, df=df)

    # 2) Tactical / pattern / volatility (can be None for now; forward-only)
    enriched = enrich_tactical(
        base,
        tactical=tactical,
        pattern=pattern,
        reversal=reversal,
        volatility=volatility,
    )

    # 3) Decision + ladders
    row = action_for(symbol, enriched, book=book, use_uc_lc=True)

    # CMP sanity
    if "CMP" in enriched and "cmp" not in row:
        try:
            row["cmp"] = float(enriched["CMP"])
        except Exception:
            pass

    # 4) Propagate instrument keys so cockpit JSON has them
    for k in _INSTRUMENT_KEYS:
        if k in enriched and k not in row:
            row[k] = enriched[k]

    return row

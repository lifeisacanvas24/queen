#!/usr/bin/env python3
# ============================================================
# queen/services/cockpit_row.py — v2.3
# Canonical cockpit row builder (CMP via candles, tactical via scoring)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl

from queen.helpers.candles import ensure_sorted, last_close
from queen.services.enrich_instruments import enrich_instrument_snapshot
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
    tactical: Optional[Dict[str, Any]] = None,   # kept for signature compatibility
    pattern: Optional[Dict[str, Any]] = None,
    reversal: Optional[Dict[str, Any]] = None,
    volatility: Optional[Dict[str, Any]] = None,
    pos: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a fully enriched cockpit row for `symbol`.

    Single sources of truth:
      • Indicators / targets / entry / SL → services.scoring.action_for()
      • CMP (bar close)                   → helpers.candles.last_close(df)
      • OHLC / Vol / avg_price            → intraday DF (Upstox)
      • PrevClose / UC / LC / 52w bands   → NSE bands (enrich_instrument_snapshot)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {}

    # 0) Ensure time-ordered bars
    df = ensure_sorted(df)

    # 1) Indicator snapshot (RSI / ATR / VWAP / CPR / OBV / EMAs …)
    ind = compute_indicators(df)
    if not ind:
        return {}

    # Let scoring’s early-engine see the full DF
    ind["_df"] = df

    # 2) Tactical row from the scoring engine
    #    This already computes: cmp, score, early, decision, entry, sl, targets, notes, advice, held, position, …
    row = action_for(symbol, ind, book=book, use_uc_lc=False)

    # 3) Instrument snapshot (OHLC / volume / avg_price / prev_close / UC-LC / 52w)
    row = enrich_instrument_snapshot(symbol, row, df=df)

    # 4) Canonical CMP override via candles helper
    cmp_val: Optional[float] = last_close(df)
    if cmp_val is None:
        # very defensive fallback to anything cmp-like the scoring row had
        try:
            raw = row.get("cmp") or row.get("CMP") or ind.get("CMP")
            if raw is not None:
                cmp_val = float(raw)
        except Exception:
            cmp_val = None

    row["cmp"] = cmp_val
    row["interval"] = interval
    row["symbol"] = symbol  # make sure symbol is set

    # 5) Bubble instrument keys explicitly (in case scoring added its own keys)
    for k in _INSTRUMENT_KEYS:
        v = row.get(k)
        if v is not None:
            row[k] = v

    # 6) Optional external pos override (e.g. when caller already loaded positions)
    #    If 'pos' is not provided, we keep whatever action_for() already computed.
    if pos and pos.get("qty", 0) > 0:
        try:
            qty = float(pos["qty"])
            avg = float(pos["avg_price"])
            px = cmp_val
            if px is not None:
                pnl_abs = (px - avg) * qty
                pnl_pct = (px - avg) / avg * 100.0
            else:
                pnl_abs = None
                pnl_pct = None

            row["position"] = {
                "side": "LONG",
                "qty": qty,
                "avg": avg,
                "pnl_abs": pnl_abs,
                "pnl_pct": pnl_pct,
            }
            row["held"] = True
        except Exception:
            # fall back to whatever scoring gave us
            row.setdefault("held", True)
    else:
        row.setdefault("held", bool(row.get("position")))

    return row

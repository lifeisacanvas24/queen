#!/usr/bin/env python3
# ============================================================
# queen/services/cockpit_row.py — v2.3 (Bible + Strategy Fusion)
# Base cockpit row builder (shared by /monitor + /cockpit)
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl

from queen.helpers.candles import ensure_sorted, last_close
from queen.services.enrich_instruments import enrich_instrument_snapshot
from queen.services.scoring import (
    action_for,
    compute_indicators_plus_bible,
)
from queen.strategies.fusion import apply_strategies  # 🔁 Unified strategy / TV fusion hook

_INSTRUMENT_KEYS = (
    "open",
    "high",
    "low",
    "close",
    "prev_close",
    "volume",
    "upper_circuit",
    "lower_circuit",
    "fifty_two_week_high",
    "fifty_two_week_low",
)


def build_cockpit_row(
    symbol: str,
    df: pl.DataFrame,
    *,
    interval: str = "15m",
    book: str = "all",
    tactical: Optional[Dict[str, Any]] = None,   # kept for fwd-compat, not used here
    pattern: Optional[Dict[str, Any]] = None,    # Bible overlays are merged upstream
    reversal: Optional[Dict[str, Any]] = None,
    volatility: Optional[Dict[str, Any]] = None,
    pos: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construct a fully enriched *base* cockpit row for `symbol`.

    Single sources of truth:
      • Indicators + Bible + Trade validity → services.scoring.compute_indicators_plus_bible()
      • Score / entry / SL / swing ladder  → services.scoring.action_for()
      • CMP (bar close)                    → helpers.candles.last_close(df)
      • O/H/L/Prev/VWAP/UC/LC/52W          → queen.fetchers.nse_fetcher
                                             (via enrich_instrument_snapshot)
      • Volume + avg_price                 → intraday DF
      • Hybrid dynamic ladder              → services.ladder_state.augment_targets_state()
                                             (called by live/summary services, not here)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {}

    # 0) Ensure time-ordered bars
    df = ensure_sorted(df)

    # 1) Mega indicator + Bible + Trade validity snapshot
    #    (includes _df, structure, trend, vol, risk, alignment, Trade_Status, etc.)
    ind = compute_indicators_plus_bible(
        df,
        interval=interval,
        symbol=symbol,
        pos=pos,
    )
    if not ind:
        return {}

    # 2) Tactical row from scoring engine (builds ladders / decision / notes / etc.)
    row = action_for(symbol, ind, book=book, use_uc_lc=False)
    if not row:
        return {}

    # 2b) Unified strategies: playbook tagging + TV fusion (scalp overrides)
    row = apply_strategies(row, interval=interval)

    # 3) Canonical CMP from latest close (strict intraday DF)
    cmp_val = last_close(df)
    try:
        if cmp_val is not None:
            cmp_val = float(cmp_val)
    except Exception:
        cmp_val = None

    row["cmp"] = cmp_val
    row["symbol"] = symbol.upper()
    row["interval"] = interval

    # 3b) Intraday ATR hint for ladder_state (dynamic vs static targets)
    # We normalise a bunch of possible keys into a single `atr_intraday`
    atr_intraday = (
        ind.get("atr_intraday")
        or ind.get("ATR_Intraday")
        or ind.get("atr_15m")
        or ind.get("ATR_15m")
        or ind.get("atr")          # last resort: generic ATR from intraday frame
        or ind.get("ATR")
    )
    try:
        if atr_intraday is not None:
            atr_intraday = float(atr_intraday)
    except Exception:
        atr_intraday = None

    if atr_intraday is not None:
        # Old + new names so ladder_state / Bible VOL can both see it
        row.setdefault("atr_intraday", atr_intraday)
        row.setdefault("ATR_Intraday", atr_intraday)

    # 4) Instrument snapshot: NSE + DF (vol/avg_price + OHLC/UC/LC/52W/VWAP)
    row = enrich_instrument_snapshot(symbol, row, df=df)

    # 5) Position override (PnL)
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
                "pnl": pnl_abs,
                "pnl_abs": pnl_abs,
                "pnl_pct": pnl_pct,
            }
            row["held"] = True
        except Exception:
            row.setdefault("held", True)
    else:
        row.setdefault("held", bool(row.get("position")))

    # 6) Bubble instrument keys explicitly (guaranteed at top-level)
    for k in _INSTRUMENT_KEYS:
        v = row.get(k)
        if v is not None:
            row[k] = v

    # 7) Optional: human-readable risk summary string for cockpit cards
    risk_summary = _format_risk_summary(row)
    if risk_summary:
        row["risk_summary"] = risk_summary

    return row

def _format_risk_summary(row: Dict[str, Any]) -> Optional[str]:
    """
    Build a compact, human-readable risk string for cockpit cards.

    Examples:
      "Risk: 4.2 / Balanced / Normal size"
      "Risk: Medium / Normal size"
      "Risk: High / Tight SL"
    """
    score = row.get("Risk_Score")
    profile = row.get("Risk_Profile") or row.get("Risk_Rating")
    size = row.get("Position_Size_Suggestion")
    sl_zone = row.get("SL_Zone")

    # Prefer position-size hint, else fall back to SL zone
    size_hint = size or (f"{sl_zone} SL" if sl_zone else None) or "Normal size"

    if score is not None and profile:
        try:
            return f"Risk: {float(score):.1f} / {profile} / {size_hint}"
        except Exception:
            return f"Risk: {profile} / {size_hint}"

    if profile:
        return f"Risk: {profile} / {size_hint}"

    return None

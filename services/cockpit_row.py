#queen/services/cockpit_row.py
from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl

from queen.helpers.candles import ensure_sorted, last_close
from queen.helpers.market import MARKET_TZ  # or queen.settings.market
from queen.services.enrich_instruments import enrich_instrument_snapshot
from queen.services.ladder_state import augment_targets_state
from queen.services.scoring import action_for, compute_indicators

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
    tactical: Optional[Dict[str, Any]] = None,
    pattern: Optional[Dict[str, Any]] = None,
    reversal: Optional[Dict[str, Any]] = None,
    volatility: Optional[Dict[str, Any]] = None,
    pos: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a fully enriched *base* cockpit row for `symbol`.

    Single sources of truth:
      • Indicators / score / entry / SL / Bible ladder → services.scoring.action_for()
      • CMP (bar close)                               → helpers.candles.last_close(df)
      • O/H/L/Prev/VWAP/UC/LC/52W                     → queen.fetchers.nse_fetcher (via enrich_instrument_snapshot)
      • Volume + avg_price                            → intraday DF
      • Hybrid dynamic ladder                         → services.ladder_state.augment_targets_state()
                                                        (called by the live/summary services, not here)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {}

    df = ensure_sorted(df)

    # 1) Indicator snapshot
    ind = compute_indicators(df)
    if not ind:
        return {}

    ind["_df"] = df

    # 2) Tactical row from scoring engine
    row = action_for(symbol, ind, book=book, use_uc_lc=False)
    if not row:
        return {}

    # 3) Canonical CMP from latest close (strict intraday)
    cmp_val = last_close(df)
    try:
        if cmp_val is not None:
            cmp_val = float(cmp_val)
    except Exception:
        cmp_val = None

    row["cmp"] = cmp_val
    row["symbol"] = symbol.upper()
    row["interval"] = interval

    # intraday ATR hint for ladder_state
    row.setdefault(
        "atr_intraday",
        ind.get("atr_intraday") or ind.get("atr_15m") or ind.get("atr"),
    )

    # 4) Instrument snapshot: NSE + DF
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

    # 6) Bubble instrument keys explicitly
    for k in _INSTRUMENT_KEYS:
        v = row.get(k)
        if v is not None:
            row[k] = v

    return row

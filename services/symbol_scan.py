#!/usr/bin/env python3
# ============================================================
# queen/services/symbol_scan.py — v1.3 (Rules-based multi-TF scan, TF-aware)
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from queen.alerts.evaluator import eval_rule
from queen.alerts.rules import Rule
from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers.common import timeframe_key
from queen.helpers.instruments import get_listing_date, validate_historical_range
from queen.helpers.market import MARKET_TZ
from queen.settings.indicator_policy import min_bars_for_indicator
from queen.settings.patterns import required_lookback as required_lookback_pattern
from queen.settings.timeframes import (
    context_to_token,
    is_intraday,
    window_days_for_tf,
)


# ---------- internal policy helpers ----------
def _min_bars_for(rule: Rule) -> int:
    """Priority:
    1) rule.params.min_bars
    2) indicator policy (for indicator)
    3) patterns policy cushion
    4) price fallback
    """
    if rule.params and "min_bars" in rule.params:
        try:
            return max(1, int(rule.params["min_bars"]))
        except Exception:
            pass

    kind = (rule.kind or "").lower()
    tf = (rule.timeframe or "1d").lower()

    if kind == "indicator":
        try:
            return max(1, int(min_bars_for_indicator(rule.indicator or "", tf)))
        except Exception:
            return 42  # safe floor

    if kind == "pattern":
        try:
            lb = int(required_lookback_pattern(rule.pattern or "", timeframe_key(tf)))
        except Exception:
            lb = 40
        return max(1, lb + 5)

    # price fallback
    return 30


def _window(interval: str, need_bars: int) -> Tuple[Optional[str], Optional[str]]:
    """Daily/weekly/monthly need a date window; intraday returns (None, None)."""
    token = context_to_token(interval or "1d")  # normalize token
    if is_intraday(token):
        return None, None

    days = window_days_for_tf(token, need_bars)
    to_dt = datetime.now(MARKET_TZ).date()
    from_dt = to_dt - timedelta(days=days)
    return from_dt.isoformat(), to_dt.isoformat()


async def _load_df(symbol: str, timeframe: str, need_bars: int) -> pl.DataFrame:
    """Fetch a dataframe with enough history for `need_bars` and trim tail."""
    token = context_to_token(timeframe or "1d")
    mode = "intraday" if is_intraday(token) else "daily"
    from_date, to_date = _window(token, need_bars)

    # listing/date guards
    if mode == "daily" and from_date and to_date:
        ldt = get_listing_date(symbol)
        if ldt and isinstance(ldt, date) and ldt > datetime.fromisoformat(from_date).date():
            from_date = ldt.isoformat()
        if not validate_historical_range(symbol, datetime.fromisoformat(from_date).date()):
            return pl.DataFrame()

    df = await fetch_unified(
        symbol,
        mode=mode,
        interval=token,
        from_date=from_date,
        to_date=to_date,
    )
    if df.is_empty():
        return df
    return df.tail(need_bars)


# ---------- public API ----------
async def run_symbol_scan(
    symbols: List[str], rules: List[Rule], bars: int = 150
) -> List[Dict[str, Any]]:
    """Evaluate a set of rules over the requested symbols.
    Returns a flat list of result dicts (stable for API/CLI/cron).
    """
    out: List[Dict[str, Any]] = []

    # group rules by symbol for efficient fetch
    rules_by_sym: Dict[str, List[Rule]] = {}
    for r in rules:
        rules_by_sym.setdefault(r.symbol, []).append(r)

    for sym in symbols:
        cache: Dict[str, pl.DataFrame] = {}
        for r in rules_by_sym.get(sym, []):
            tf = (r.timeframe or "1d").lower()
            need = min(bars, max(bars, _min_bars_for(r)))  # honor bars floor

            if tf not in cache:
                df = await _load_df(sym, tf, need)
                cache[tf] = df

            df = cache[tf]
            if df.is_empty():
                ok, meta = False, {"reason": "empty_df"}
            else:
                ok, meta = eval_rule(r, df)

            out.append(
                {
                    "symbol": sym,
                    "timeframe": tf,
                    "rule": r.name or r.pattern or r.indicator or "unnamed",
                    "ok": bool(ok),
                    "meta": meta,
                }
            )
    return out

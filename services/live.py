#!/usr/bin/env python3
# ============================================================
# queen/services/live.py — v2.1
# Unified live actionables (CLI + Web), cockpit_row-backed
# ============================================================
from __future__ import annotations

from typing import Dict, List

import polars as pl

from queen.daemons.live_engine import MonitorConfig, _one_pass
from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.candles import last_close
from queen.helpers.portfolio import load_positions
from queen.services.cockpit_row import build_cockpit_row

try:
    from queen.settings.timeframes import MIN_BARS as _SETTINGS_MIN_BARS
except Exception:
    _SETTINGS_MIN_BARS = None


# -------------------------------------------------------------------
# Bars policy + backfill
# -------------------------------------------------------------------
def _min_bars(interval_min: int) -> int:
    """Minimum bars policy per intraday interval."""
    fallback = {5: 150, 15: 120, 30: 100, 60: 60}
    src = _SETTINGS_MIN_BARS or fallback
    return int(src.get(interval_min, 120))


async def _intraday_with_backfill(symbol: str, interval_min: int) -> pl.DataFrame:
    """Try hard to return enough bars for indicators."""
    need = _min_bars(interval_min)
    cap = max(need, 600)
    iv = f"{interval_min}m"

    df = await fetch_intraday(symbol, iv)
    if not df.is_empty() and getattr(df, "height", 0) >= need:
        return df.tail(cap)

    # days param
    for d in (2, 5, 10):
        try:
            df2 = await fetch_intraday(symbol, iv, days=d)
            if not df2.is_empty() and df2.height >= need:
                return df2.tail(cap)
            if not df2.is_empty():
                df = df2
        except TypeError:
            break

    # bars param
    for mult in (2, 3, 4, 6, 8):
        try:
            df2 = await fetch_intraday(symbol, iv, bars=need * mult)
            if not df2.is_empty() and df2.height >= need:
                return df2.tail(cap)
            if not df2.is_empty() and df2.height > getattr(df, "height", 0):
                df = df2
        except TypeError:
            break

    # start param (ISO)
    try:
        from datetime import datetime, timedelta, timezone

        start = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        df2 = await fetch_intraday(symbol, iv, start=start)
        if not df2.is_empty() and df2.height >= need:
            return df2.tail(cap)
        if not df2.is_empty() and df2.height > getattr(df, "height", 0):
            df = df2
    except TypeError:
        pass

    return df.tail(cap) if not df.is_empty() else df


# -------------------------------------------------------------------
# Compact snapshot (for internal CPR/VWAP/ATR/RSI/OBV metrics)
# -------------------------------------------------------------------
async def cmp_snapshot(symbols: List[str], interval_min: int) -> List[Dict]:
    """Use daemon live_engine _one_pass for a lightweight snapshot.

    Returns a list of dicts with at least:
      symbol, cmp, cpr, vwap, atr, rsi, obv, summary, targets, sl
    """
    cfg = MonitorConfig(
        symbols=[s.upper() for s in symbols],
        interval_min=interval_min,
        view="compact",
    )
    rows = await _one_pass(cfg)
    out: List[Dict] = []
    for r in rows:
        try:
            sym = (r.get("symbol") or "").upper()
            cmp_ = r.get("cmp")
            out.append(
                {
                    "symbol": sym,
                    "cmp": float(cmp_) if cmp_ is not None else None,
                    "cpr": r.get("cpr"),
                    "vwap": r.get("vwap"),
                    "atr": r.get("atr"),
                    "rsi": r.get("rsi"),
                    "obv": r.get("obv"),
                    "summary": r.get("summary"),
                    "targets": r.get("targets") or [],
                    "sl": r.get("sl"),
                }
            )
        except Exception:
            continue
    return out


# -------------------------------------------------------------------
# Live actionables — canonical rows for /monitor/actionable + Live UI
# -------------------------------------------------------------------
async def actionables_for(
    symbols: List[str],
    interval_min: int,
    book: str,
) -> List[Dict]:
    """Unified actionable rows for /monitor and Live Cockpit.

    Uses build_cockpit_row() so scoring / targets / SL match the
    Summary cockpit, and normalizes CMP via Candle helpers.
    """
    symbols = [s.upper() for s in symbols]
    pos_map = load_positions(book) or {}

    # Prefer daemon snapshot CMP (same as CLI)
    snap = await cmp_snapshot(symbols, interval_min)
    cmp_map = {r["symbol"]: r.get("cmp") for r in snap if r.get("cmp") is not None}

    tf_str = f"{interval_min}m"
    rows: List[Dict] = []

    for sym in symbols:
        try:
            df = await _intraday_with_backfill(sym, interval_min)
            if df.is_empty():
                continue

            row = build_cockpit_row(
                sym,
                df,
                interval=tf_str,
                book=book,
                tactical=None,
                pattern=None,
                reversal=None,
                volatility=None,
            )
            if not row:
                continue

            # CMP: snapshot first, then last_close(df)
            cmp_val = cmp_map.get(sym)
            if cmp_val is None:
                cmp_val = last_close(df)
            if cmp_val is not None:
                row["cmp"] = cmp_val

            row["held"] = sym in pos_map
            rows.append(row)
        except Exception:
            continue

    prio = {"BUY": 0, "ADD": 0, "HOLD": 1}
    rows.sort(
        key=lambda x: (-(x.get("score") or 0), prio.get(x.get("decision", ""), 2))
    )
    return rows

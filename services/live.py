#!/usr/bin/env python3
# ============================================================
# queen/services/live.py — v2.4
# Unified live actionables (CLI + Web), cockpit_row-backed
# ============================================================
from __future__ import annotations

from typing import Dict, List, Tuple

import polars as pl

from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.candles import ensure_sorted, last_close
from queen.helpers.instruments import get_instrument_meta
from queen.helpers.logger import log
from queen.helpers.market import MARKET_TZ
from queen.helpers.portfolio import load_positions
from queen.services.cockpit_row import build_cockpit_row
from queen.services.ladder_state import augment_targets_state  # at top
from queen.settings.timeframes import DAILY_ATR_BACKFILL_DAYS_INTRADAY as _ATR_DAYS

# Indicator cores (for cmp_snapshot + daemon reuse)
from queen.technicals.indicators.core import (
    atr_last,
    cpr_from_prev_day,
    obv_trend,
    rsi_last,
    vwap_last,
)

try:
    from queen.settings.timeframes import MIN_BARS as _SETTINGS_MIN_BARS
except Exception:
    _SETTINGS_MIN_BARS = None

# -------------------------------------------------------------------
# Today-only intraday helper (CMP anchor)
# -------------------------------------------------------------------
async def _today_intraday_df(
    symbol: str,
    interval_min: int,
    limit: int | None = None,
) -> pl.DataFrame:
    """Pure intraday for *today only*, used to anchor CMP.

    Mirrors old live_engine behaviour:
      - fetch_intraday("15m") → tail(limit) → last close.
    """
    iv = f"{interval_min}m"
    df = await fetch_intraday(symbol, iv)
    if not df.is_empty() and limit:
        df = df.tail(limit)
    return ensure_sorted(df) if not df.is_empty() else df

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
    for d in (2, 5, 10, _ATR_DAYS):
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
# Shared structure/targets helper (old live_engine logic)
# -------------------------------------------------------------------
def structure_and_targets(
    last_close_val: float,
    cpr,
    vwap,
    rsi,
    atr,
    obv,
) -> Tuple[str, list[str], float]:
    """Simple, console-friendly structure + targets block."""
    summary: list[str] = []

    if cpr is not None and vwap is not None:
        if last_close_val > max(cpr, vwap):
            summary.append("Above VWAP/CPR")
        elif last_close_val < min(cpr, vwap):
            summary.append("Below VWAP/CPR")
        else:
            summary.append("Inside CPR/VWAP")

    if obv == "Rising":
        summary.append("OBV ↑")
    elif obv == "Falling":
        summary.append("OBV ↓")

    if rsi is not None:
        if rsi >= 60:
            summary.append("RSI strong")
        elif rsi <= 45:
            summary.append("RSI weak")

    atr_val = atr or max(1.0, last_close_val * 0.01)
    t1 = round(last_close_val + 0.5 * atr_val, 1)
    t2 = round(last_close_val + 1.0 * atr_val, 1)
    t3 = round(last_close_val + 1.5 * atr_val, 1)
    sl = round(last_close_val - 1.0 * atr_val, 1)

    return (
        "; ".join(summary) if summary else "Neutral",
        [f"T1 {t1}", f"T2 {t2}", f"T3 {t3}"],
        sl,
    )


# -------------------------------------------------------------------
# Compact snapshot (used by /monitor/snapshot + /monitor/stream)
# -------------------------------------------------------------------
# -------------------------------------------------------------------
# Compact snapshot (used by /monitor/snapshot + /monitor/stream)
# -------------------------------------------------------------------
async def cmp_snapshot(symbols: List[str], interval_min: int) -> List[Dict]:
    """Lightweight live snapshot for monitor endpoints.

    Returns at least:
      symbol, cmp, cpr, vwap, atr, rsi, obv, summary, targets, sl

    ✅ CMP is anchored to *today-only intraday* (pure intraday),
       indicators use the richer backfilled DF for context.
    """
    out: List[Dict] = []
    tf_str = f"{interval_min}m"
    need = _min_bars(interval_min)

    for sym in [s.upper() for s in symbols]:
        try:
            # A) CMP from pure intraday today
            df_today = await _today_intraday_df(sym, interval_min, limit=need)
            cmp_val = last_close(df_today) if not df_today.is_empty() else None

            # B) Context DF via backfill for indicators
            df_ctx = await _intraday_with_backfill(sym, interval_min)
            if df_ctx.is_empty():
                df_ctx = df_today
            if df_ctx.is_empty():
                continue

            df_ctx = ensure_sorted(df_ctx)

            # fallback if CMP missing
            if cmp_val is None:
                cmp_val = last_close(df_ctx)
            if cmp_val is None:
                continue

            # indicator core
            cpr = cpr_from_prev_day(df_ctx)
            vwap = vwap_last(df_ctx)
            rsi = rsi_last(df_ctx["close"], 14)
            atr = atr_last(df_ctx, 14)
            obv = obv_trend(df_ctx)

            summary, targets, sl = structure_and_targets(
                last_close_val=cmp_val,
                cpr=cpr,
                vwap=vwap,
                rsi=rsi,
                atr=atr,
                obv=obv,
            )

            out.append(
                {
                    "symbol": sym,
                    "interval": tf_str,
                    "cmp": cmp_val,
                    "cpr": cpr,
                    "vwap": vwap,
                    "atr": atr,
                    "rsi": rsi,
                    "obv": obv,
                    "summary": summary,
                    "targets": targets,
                    "sl": sl,
                }
            )
        except Exception as e:
            log.exception(f"[live.cmp_snapshot] {sym} failed → {e}")
            continue

    return out

async def _today_intraday_df(symbol: str, interval_min: int, limit: int) -> pl.DataFrame:
    """Pure intraday snapshot for *today only* (no backfill).

    Upstox intraday endpoint without days/bars returns today's data,
    so we just fetch + sort + tail(limit).
    """
    iv = f"{interval_min}m"
    df = await fetch_intraday(symbol, iv)
    if df.is_empty():
        return df
    return ensure_sorted(df).tail(limit)

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
    Summary cockpit.

    ✅ CMP is anchored to *today-only intraday* (pure intraday),
       with a fallback to the backfilled DF last_close().
    """
    symbols = [s.upper() for s in symbols]
    pos_map = load_positions(book) or {}

    tf_str = f"{interval_min}m"
    need = _min_bars(interval_min)
    rows: List[Dict] = []

    for sym in symbols:
        try:
            # A) CMP anchor from pure intraday today
            df_today = await _today_intraday_df(sym, interval_min, limit=need)
            if not df_today.is_empty():
                df_today = ensure_sorted(df_today)
                cmp_today = last_close(df_today)
            else:
                cmp_today = None

            # B) Context DF with backfill for indicators / Bible
            df = await _intraday_with_backfill(sym, interval_min)
            if df.is_empty():
                df = df_today
            if df.is_empty():
                continue

            df = ensure_sorted(df)

            # C) Base cockpit row (indicators, Bible ladders, instrument meta)
            row = build_cockpit_row(
                sym,
                df,
                interval=tf_str,
                book=book,
                tactical=None,
                pattern=None,
                reversal=None,
                volatility=None,
                pos=pos_map.get(sym),
            )
            if not row:
                continue

            # D) CMP: prefer today-only intraday, then row.cmp, then DF close
            eff_cmp = cmp_today or row.get("cmp") or last_close(df)
            if eff_cmp is not None:
                row["cmp"] = eff_cmp

            # 🔹 DO NOT override O/H/L/Prev now — they come from enrich_instrument_snapshot (NSE).

            # F) Hybrid ladder using final CMP
            row = augment_targets_state(row, interval=tf_str)

            # mark held if a position exists
            row["held"] = sym in pos_map or bool(row.get("position"))

            rows.append(row)
        except Exception as e:
            log.exception(f"[live.actionables_for] {sym} failed → {e}")
            continue

    prio = {"BUY": 0, "ADD": 0, "HOLD": 1}
    rows.sort(
        key=lambda x: (
            -(x.get("score") or 0),
            prio.get((x.get("decision") or "").upper(), 2),
        )
    )
    return rows

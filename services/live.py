#!/usr/bin/env python3
# ============================================================
# queen/services/live.py — v2.6
# Unified live actionables (CLI + Web), cockpit_row-backed
#
# - cmp_snapshot: lightweight indicator snapshot for monitor UI
# - actionables_for: full actionable rows via build_actionable_row
# ============================================================
from __future__ import annotations

# -------------------------------------------------------------------
# Light actionable view (for fast UIs / snapshot-style endpoints)
# -------------------------------------------------------------------
from typing import (
    Any,  # if not already imported at top
    Dict,
    List,
)

import polars as pl

from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.candles import ensure_sorted, last_close
from queen.helpers.logger import log
from queen.helpers.portfolio import load_positions
from queen.services.actionable_row import build_actionable_row
from queen.settings.timeframes import DAILY_ATR_BACKFILL_DAYS_INTRADAY as _ATR_DAYS

# Indicator cores (for cmp_snapshot)
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

    Upstox intraday endpoint without days/bars returns today's data,
    so we just fetch + sort + tail(limit) if provided.
    """
    iv = f"{interval_min}m"
    df = await fetch_intraday(symbol, iv)
    if df.is_empty():
        return df
    df = ensure_sorted(df)
    if limit:
        return df.tail(limit)
    return df


# -------------------------------------------------------------------
# Bars policy + backfill
# -------------------------------------------------------------------
def _min_bars(interval_min: int) -> int:
    """Minimum bars policy per intraday interval."""
    fallback: Dict[int, int] = {5: 150, 15: 120, 30: 100, 60: 60}
    src = _SETTINGS_MIN_BARS or fallback
    base = int(src.get(interval_min, 120))
    # ✅ guarantee EMA200 stability
    return max(200, base)


async def _intraday_with_backfill(symbol: str, interval_min: int) -> pl.DataFrame:
    """Try hard to return enough bars for indicators."""
    need = _min_bars(interval_min)
    cap = max(need, 600)
    iv = f"{interval_min}m"

    df = await fetch_intraday(symbol, iv)
    if not df.is_empty() and getattr(df, "height", 0) >= need:
        return ensure_sorted(df.tail(cap))

    # days param
    for d in (2, 5, 10, _ATR_DAYS):
        try:
            df2 = await fetch_intraday(symbol, iv, days=d)
        except TypeError:
            break

        if not df2.is_empty() and df2.height >= need:
            return ensure_sorted(df2.tail(cap))
        if not df2.is_empty() and df2.height > getattr(df, "height", 0):
            df = df2

    # bars param
    for mult in (2, 3, 4, 6, 8):
        try:
            df2 = await fetch_intraday(symbol, iv, bars=need * mult)
        except TypeError:
            break

        if not df2.is_empty() and df2.height >= need:
            return ensure_sorted(df2.tail(cap))
        if not df2.is_empty() and df2.height > getattr(df, "height", 0):
            df = df2

    # start param (ISO)
    try:
        from datetime import datetime, timedelta, timezone

        start = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        df2 = await fetch_intraday(symbol, iv, start=start)
        if not df2.is_empty() and df2.height >= need:
            return ensure_sorted(df2.tail(cap))
        if not df2.is_empty() and df2.height > getattr(df, "height", 0):
            df = df2
    except TypeError:
        pass

    return ensure_sorted(df.tail(cap)) if not df.is_empty() else df


# -------------------------------------------------------------------
# Simple structure + targets block (for cmp_snapshot only)
# -------------------------------------------------------------------
def structure_and_targets(
    last_close_val: float,
    cpr,
    vwap,
    rsi,
    atr,
    obv,
):
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


# -------------------------------------------------------------------
# Live actionables — canonical rows for /monitor/actionable + Live UI
# -------------------------------------------------------------------
async def actionables_for(
    symbols: List[str],
    interval_min: int,
    book: str,
) -> List[Dict]:
    """Unified actionable rows for /monitor and Live Cockpit.

    Uses build_actionable_row() so scoring / targets / SL / overlays
    match both Summary cockpit AND replay_actionable.
    """
    symbols = [s.upper() for s in symbols]
    pos_map = load_positions(book) or {}

    tf_str = f"{interval_min}m"
    need = _min_bars(interval_min)
    rows: List[Dict] = []

    for sym in symbols:
        try:
            # --------------------------------------------------------
            # A) CMP anchor from pure intraday today
            # --------------------------------------------------------
            df_today = await _today_intraday_df(sym, interval_min, limit=need)
            if not df_today.is_empty():
                df_today = ensure_sorted(df_today)
                cmp_today = last_close(df_today)
            else:
                cmp_today = None

            # --------------------------------------------------------
            # B) Context DF with backfill (for indicators / Bible)
            # --------------------------------------------------------
            df = await _intraday_with_backfill(sym, interval_min)
            if df.is_empty():
                df = df_today
            if df.is_empty():
                continue

            df = ensure_sorted(df)

            # --------------------------------------------------------
            # C) Unified actionable row (engine core)
            # --------------------------------------------------------
            row, _ = build_actionable_row(
                symbol=sym,
                df=df,
                interval=tf_str,
                book=book,
                pos_mode="live",
                positions_map=pos_map,
                cmp_anchor=cmp_today,
            )
            if not row:
                continue

            rows.append(row)

        except Exception as e:
            log.exception(f"[live.actionables_for] {sym} failed → {e}")
            continue

    # ------------------------------------------------------------
    # Final sort order
    # ------------------------------------------------------------
    prio = {"BUY": 0, "ADD": 0, "HOLD": 1}
    rows.sort(
        key=lambda x: (
            -(x.get("score") or 0),
            prio.get((x.get("decision") or "").upper(), 2),
        )
    )
    return rows



_LIGHT_ACTIONABLE_KEYS = (
    "symbol",
    "interval",
    "time_bucket",

    # Core decision
    "cmp",
    "score",
    "early",
    "decision",
    "bias",
    "advice",

    # Trade status
    "trade_status",
    "trade_status_label",
    "trade_reason",
    "trade_score",
    "trade_flags",

    # Playbook / tactical overlay
    "playbook",
    "playbook_tags",
    "action_tag",
    "action_reason",
    "risk_mode",

    # Trend / alignment “headline”
    "trend_label",
    "trend_score",
    "Alignment_Label",
    "Alignment_Score",

    # Zones / context
    "vwap_zone",
    "VWAP_Context",
    "cpr_ctx",
    "CPR_Context",

    # Targets / ladder summary
    "targets_label",
    "targets_static_text",
    "targets_dynamic_text",
)


def _to_light_actionable(row: Dict[str, Any]) -> Dict[str, Any]:
    """Project a full actionable row into a light, UI-friendly schema.

    Intent:
      • Keep only the “headline” info needed for list / grid UIs.
      • Avoid heavy fields (full indicators, swing arrays, etc.)
    """
    out: Dict[str, Any] = {k: row.get(k) for k in _LIGHT_ACTIONABLE_KEYS if k in row}

    # Ensure a few always-present fallbacks
    out.setdefault("symbol", row.get("symbol"))
    out.setdefault("interval", row.get("interval"))
    out.setdefault("decision", row.get("decision"))
    out.setdefault("bias", row.get("bias"))
    out.setdefault("cmp", row.get("cmp"))

    return out


async def actionables_light_for(
    symbols: List[str],
    interval_min: int,
    book: str,
) -> List[Dict[str, Any]]:
    """Lightweight wrapper over actionables_for().

    Uses the SAME engine, but returns projected “light” rows:
      • good for snapshot / mobile / quick dashboards
      • no duplicated logic
    """
    full_rows = await actionables_for(symbols, interval_min, book)
    return [_to_light_actionable(r) for r in full_rows]

def project_light_actionable(row: Dict[str, Any]) -> Dict[str, Any]:
    """Public helper to project a single full actionable row into the light schema.

    Used by HTTP routers or any UI layer that wants to downgrade a
    full engine row to a skinny, list-friendly payload.
    """
    return _to_light_actionable(row)

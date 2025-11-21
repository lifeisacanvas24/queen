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
from queen.services.bible_engine import (
    trade_validity_block,
    compute_alignment_block,   # ✅ ADD THIS
)
from queen.services.scoring import compute_indicators
from queen.services.tactical_pipeline import compute_bible_blocks
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
    fallback = {5: 150, 15: 120, 30: 100, 60: 60}
    src = _SETTINGS_MIN_BARS or fallback
    base = int(src.get(interval_min, 120))
    return max(200, base)   # ✅ guarantee EMA200 stability


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

def _recompute_cmp_sensitive(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    After CMP override, recompute CMP-sensitive contexts:
      - vwap_zone / cpr_ctx
      - Alignment block
      - Trade validity block

    Uses bible_engine's pure blocks (no circulars).
    """
    if not row:
        return row

    cmp_ = row.get("cmp")
    if cmp_ is None:
        return row

    try:
        cmp_ = float(cmp_)
    except Exception:
        return row

    # Normalize VWAP/CPR keys from row
    vwap_val = (
        row.get("VWAP")
        or row.get("vwap")
        or row.get("vwap_last")
    )
    cpr_val = (
        row.get("CPR")
        or row.get("cpr")
        or row.get("cpr_last")
    )

    try:
        if vwap_val is not None:
            vwap_val = float(vwap_val)
            row["VWAP"] = vwap_val
    except Exception:
        vwap_val = None

    try:
        if cpr_val is not None:
            cpr_val = float(cpr_val)
            row["CPR"] = cpr_val
    except Exception:
        cpr_val = None

    # ---------- Recompute vwap_zone + cpr_ctx from FINAL CMP ----------
    if vwap_val is not None:
        diff = (cmp_ - vwap_val) / max(1.0, vwap_val) * 100.0
        if abs(diff) <= 0.3:
            row["vwap_zone"] = "Near/Choppy"
        else:
            row["vwap_zone"] = "Above" if diff > 0 else "Below"

    if cpr_val is not None:
        diff = (cmp_ - cpr_val) / max(1.0, cpr_val) * 100.0
        if abs(diff) <= 0.3:
            row["cpr_ctx"] = "Inside CPR"
        else:
            row["cpr_ctx"] = "Above CPR" if diff > 0 else "Below CPR"

    # ---------- NOW build metrics AFTER zones are corrected ----------
    metrics = dict(row)
    metrics["CMP"] = cmp_
    metrics["cmp"] = cmp_
    metrics["vwap_zone"] = row.get("vwap_zone")
    metrics["cpr_ctx"] = row.get("cpr_ctx")

    # ---------- Recompute Alignment block (will trust corrected zones) ----------
    try:
        align = compute_alignment_block(metrics)
    except Exception as e:
        log.exception(f"[live._recompute_cmp_sensitive] alignment failed → {e}")
        align = {}

    if align:
        row.update(align)

        # keep legacy keys synced
        if align.get("VWAP_Context"):
            row["vwap_zone"] = align["VWAP_Context"]

        if align.get("CPR_Context"):
            cctx = align["CPR_Context"]
            if cctx == "Above":
                row["cpr_ctx"] = "Above CPR"
            elif cctx == "Below":
                row["cpr_ctx"] = "Below CPR"
            elif cctx == "Inside":
                row["cpr_ctx"] = "Inside CPR"
            else:
                row["cpr_ctx"] = cctx

    # ---------- Recompute Trade Validity using final CMP + corrected alignment ----------
    try:
        validity = trade_validity_block(dict(row))
    except Exception as e:
        log.exception(f"[live._recompute_cmp_sensitive] validity failed → {e}")
        validity = {}

    if validity:
        row["trade_status"] = validity.get("Trade_Status", row.get("trade_status"))
        row["trade_status_label"] = validity.get(
            "Trade_Status_Label", row.get("trade_status_label")
        )
        row["trade_reason"] = validity.get("Trade_Reason", row.get("trade_reason"))
        row["trade_score"] = validity.get("Trade_Score", row.get("trade_score"))
        row["trade_flags"] = validity.get("Trade_Flags", row.get("trade_flags"))

    return row
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
            # ------------------------------------------------------------
            # A) CMP anchor from pure intraday today
            # ------------------------------------------------------------
            df_today = await _today_intraday_df(sym, interval_min, limit=need)
            if not df_today.is_empty():
                df_today = ensure_sorted(df_today)
                cmp_today = last_close(df_today)     # FUNCTION, no shadowing
            else:
                cmp_today = None

            # ------------------------------------------------------------
            # B) Context DF with backfill (for indicators / Bible)
            # ------------------------------------------------------------
            df = await _intraday_with_backfill(sym, interval_min)
            if df.is_empty():
                df = df_today
            if df.is_empty():
                continue

            df = ensure_sorted(df)

            # ------------------------------------------------------------
            # C) Feed last TF candle + prev close into row for WRB trailing
            # ------------------------------------------------------------
            try:
                last_open_px   = float(df["open"].tail(1).item())
                last_high_px   = float(df["high"].tail(1).item())
                last_low_px    = float(df["low"].tail(1).item())
                last_close_px  = float(df["close"].tail(1).item())  # renamed ✔

                prev_close_px = None
                if df.height >= 2:
                    prev_close_px = float(df["close"].tail(2).head(1).item())

                candle_ctx = {
                    "last_tf_open": last_open_px,
                    "last_tf_high": last_high_px,
                    "last_tf_low": last_low_px,
                    "last_tf_close": last_close_px,
                    "prev_tf_close": prev_close_px,
                }

            except Exception:
                candle_ctx = {}

            # ------------------------------------------------------------
            # D) Base indicators
            # ------------------------------------------------------------
            base_ind = compute_indicators(df) or {}
            base_ind["_df"] = df

            if cmp_today is not None:
                base_ind["CMP"] = float(cmp_today)
                base_ind["cmp"] = float(cmp_today)

            # ------------------------------------------------------------
            # E) Bible blocks
            # ------------------------------------------------------------
            bible = compute_bible_blocks(df, base_ind, interval=tf_str)

            # ------------------------------------------------------------
            # F) Base cockpit row
            # ------------------------------------------------------------
            row = build_cockpit_row(
                sym,
                df,
                interval=tf_str,
                book=book,
                tactical=bible,
                pattern=bible,
                reversal=bible,
                volatility=bible,
                pos=pos_map.get(sym),
            )
            if not row:
                continue

            # ------------------------------------------------------------
            # G) CMP finalization (CMP_today → row.cmp → DF close)
            # ------------------------------------------------------------
            eff_cmp = cmp_today or row.get("cmp") or last_close(df)
            if eff_cmp is not None:
                row["cmp"] = float(eff_cmp)

            # ------------------------------------------------------------
            # H) Attach candle context for WRB trailing
            # ------------------------------------------------------------
            if candle_ctx:
                row.update(candle_ctx)

            # ------------------------------------------------------------
            # I) Attach Bible metrics
            # ------------------------------------------------------------
            if bible:
                row.update(bible)

            # ------------------------------------------------------------
            # J) Recompute CMP-sensitive blocks
            # ------------------------------------------------------------
            row = _recompute_cmp_sensitive(row)

            # ------------------------------------------------------------
            # K) Hybrid ladder (T1–T6, WRB trailing, R1–R3)
            # ------------------------------------------------------------
            row = augment_targets_state(row, interval=tf_str)

            # ------------------------------------------------------------
            # L) Mark held position
            # ------------------------------------------------------------
            row["held"] = sym in pos_map or bool(row.get("position"))

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

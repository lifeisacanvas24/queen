#!/usr/bin/env python3
# ============================================================
# queen/services/live.py — v1.5
# CPR ctx fallback + RSI/EMA expose + CPR+EMA UI badges
# ============================================================
from __future__ import annotations

from typing import Dict, List, Optional

import polars as pl

from queen.daemons.live_engine import MonitorConfig, _one_pass
from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.portfolio import load_positions
from queen.services.scoring import action_for, compute_indicators

try:
    from queen.settings.timeframes import MIN_BARS as _SETTINGS_MIN_BARS
except Exception:
    _SETTINGS_MIN_BARS = None

try:
    # optional RSI fallback util
    from queen.technicals.indicators.core import rsi_last
except Exception:
    rsi_last = None

# -------------------------------------------------------------------
def _min_bars(interval_min: int) -> int:
    fallback = {5: 150, 15: 120, 30: 100, 60: 60}
    src = _SETTINGS_MIN_BARS or fallback
    return int(src.get(interval_min, 120))

def _safe_float(v) -> Optional[float]:
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(v)
    except Exception:
        return None

# --- replace existing helper with this beefed-up version ---
async def _intraday_with_backfill(symbol: str, interval_min: int) -> pl.DataFrame:
    """Try hard to return enough bars for indicators:
      1) plain fetch
      2) days=2,5,10 (if supported)
      3) bars=..., progressively larger (if supported)
      4) start/timestamp strings (if supported by your fetcher)
    Always tail() to a sane cap.
    """
    need = _min_bars(interval_min)                 # e.g. 120 for 15m (tunable)
    cap  = max(need, 600)                          # don't grow unbounded
    iv   = f"{interval_min}m"

    # 1) vanilla
    df = await fetch_intraday(symbol, iv)
    if not df.is_empty() and getattr(df, "height", 0) >= need:
        return df.tail(cap)

    # 2) try multiple 'days' sizes
    for d in (2, 5, 10):
        try:
            df2 = await fetch_intraday(symbol, iv, days=d)
            if not df2.is_empty() and df2.height >= need:
                return df2.tail(cap)
            if not df2.is_empty():
                df = df2   # keep the best so far
        except TypeError:
            break  # this fetcher may not support 'days'

    # 3) try larger 'bars' windows
    for mult in (2, 3, 4, 6, 8):
        try:
            df2 = await fetch_intraday(symbol, iv, bars=need * mult)
            if not df2.is_empty() and df2.height >= need:
                return df2.tail(cap)
            if not df2.is_empty() and df2.height > getattr(df, "height", 0):
                df = df2
        except TypeError:
            break  # no 'bars' kw supported

    # 4) try 'start' (ISO) if fetcher supports time ranges
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

    # Return best we managed (even if short); downstream fallbacks will handle it.
    return df.tail(cap) if not df.is_empty() else df

# -------------------------------------------------------------------
def _ctx_from_value(cmp_val: float | None, ref: float | None, eps_pct: float = 0.10) -> Optional[str]:
    if cmp_val is None or ref is None:
        return None
    eps = abs(ref) * (eps_pct / 100.0)
    if abs(cmp_val - ref) <= eps:
        return "At"
    return "Above" if cmp_val > ref else "Below"

def _cpr_ctx_with_fallback(cmp_val: float | None, cpr_pp: float | None, vwap: float | None) -> str:
    ctx = _ctx_from_value(cmp_val, cpr_pp)
    if ctx is not None:
        return ctx
    ctx = _ctx_from_value(cmp_val, vwap)
    return ctx if ctx is not None else "Unknown"

# -------------------------------------------------------------------
def _ensure_min_width_with_atr(row: Dict, atr: Optional[float]) -> Dict:
    if not atr or atr <= 0:
        return row
    MIN_TGT_ATR = 0.60
    MIN_SL_ATR  = 0.40
    entry = _safe_float(row.get("entry"))
    if entry is None:
        return row
    sl = _safe_float(row.get("sl"))
    if sl is not None:
        dec = (row.get("decision") or "").upper()
        longish = dec in ("BUY", "ADD", "ENTER") or (row.get("cmp") and row["cmp"] >= entry)
        gap = MIN_SL_ATR * atr
        if longish and (entry - sl) < gap:
            row["sl"] = round(entry - gap, 1)
        if not longish and (sl - entry) < gap:
            row["sl"] = round(entry + gap, 1)

    levels: List[float] = []
    for t in (row.get("targets") or []):
        try:
            levels.append(float(str(t).split()[-1]))
        except Exception:
            pass
    if levels:
        longish = (row.get("decision") or "").upper() in ("BUY", "ADD", "ENTER") or (
            row.get("cmp") and row["cmp"] >= entry
        )
        widened, prev = [], entry
        for lv in levels:
            need = MIN_TGT_ATR * atr
            widened.append(max(lv, prev + need) if longish else min(lv, prev - need))
            prev = widened[-1]
        row["targets"] = [f"T{i+1} {round(v,1)}" for i, v in enumerate(widened)]
    return row

# -------------------------------------------------------------------
async def cmp_snapshot(symbols: List[str], interval_min: int) -> List[Dict]:
    cfg = MonitorConfig(symbols=[s.upper() for s in symbols], interval_min=interval_min, view="compact")
    rows = await _one_pass(cfg)
    out: List[Dict] = []
    for r in rows:
        try:
            sym = (r.get("symbol") or "").upper()
            cmp_ = r.get("cmp")
            out.append({
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
            })
        except Exception:
            continue
    return out

# -------------------------------------------------------------------
async def actionables_for(symbols: List[str], interval_min: int, book: str) -> List[Dict]:
    symbols = [s.upper() for s in symbols]
    pos_map = load_positions(book) or {}
    snap = await cmp_snapshot(symbols, interval_min)
    cmp_map  = {r["symbol"]: r.get("cmp") for r in snap if r.get("cmp") is not None}
    cpr_map  = {r["symbol"]: r.get("cpr") for r in snap}
    vwap_map = {r["symbol"]: r.get("vwap") for r in snap}

    rows: List[Dict] = []
    for sym in symbols:
        try:
            df = await _intraday_with_backfill(sym, interval_min)
            if df.is_empty() or (hasattr(df, "height") and df.height < 10):
                row = {"symbol": sym, "decision": "", "score": 0, "entry": None, "sl": None, "targets": [],
                       "notes": "(watchlist: insufficient bars for signals)"}
            else:
                ind = compute_indicators(df) or {}

                # CPR + RSI fallback
                if ind.get("cpr") is None and sym in cpr_map:
                    ind["cpr"] = cpr_map[sym]
                if ind.get("rsi") is None and rsi_last:
                    try:
                        close = df["close"].cast(pl.Float64, strict=False)
                        ind["rsi"] = float(rsi_last(close, 14))
                    except Exception:
                        ind["rsi"] = None

                cmp_now = cmp_map.get(sym)
                vwap_now = ind.get("vwap") if ind.get("vwap") is not None else vwap_map.get(sym)
                ind["cpr_ctx"] = _cpr_ctx_with_fallback(cmp_now, ind.get("cpr"), vwap_now)

                row = action_for(sym, ind, book=book, use_uc_lc=True)

                # overwrite to ensure non-null
                row["rsi"] = row.get("rsi") or ind.get("rsi")
                row["ema_bias"] = row.get("ema_bias") or ind.get("ema_bias")
                row["vwap_zone"] = _ctx_from_value(cmp_now, vwap_now) or "Unknown"
                row["cpr"] = row.get("cpr") or ind.get("cpr")
                row["cpr_ctx"] = row.get("cpr_ctx") or ind.get("cpr_ctx")
                row["ema50"] = ind.get("ema50")
                row["obv"] = ind.get("obv")
                row["atr"] = ind.get("atr")

                row = _ensure_min_width_with_atr(row, _safe_float(ind.get("atr")))

                if "early" not in row or row.get("early") in (None, ""):
                    entry = row.get("entry")
                    atr_val = _safe_float(ind.get("atr"))
                    if atr_val and cmp_now and entry:
                        dist = abs(cmp_now - entry) / max(1e-6, atr_val)
                        row["early"] = int(max(0.0, min(10.0, dist * 4)))
                    else:
                        row["early"] = 0

            row["held"] = sym in pos_map
            if sym in cmp_map:
                row["cmp"] = cmp_map[sym]
            rows.append(row)
        except Exception:
            continue

    prio = {"BUY": 0, "ADD": 0, "HOLD": 1}
    rows.sort(key=lambda x: (-(x.get("score") or 0), prio.get(x.get("decision", ""), 2)))
    return rows

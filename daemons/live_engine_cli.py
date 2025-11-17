#!/usr/bin/env python3
# ============================================================
# queen/daemons/live_engine.py — v1.6 (Calendar-aware CPR + robust live loop)
# ============================================================
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

import polars as pl
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.console import Group
from zoneinfo import ZoneInfo

from queen.helpers.logger import log
from queen.helpers.market import sleep_until_next_candle, get_market_state
from queen.fetchers.upstox_fetcher import fetch_intraday

# ✅ DRY: shared core indicators
from queen.technicals.indicators.core import (
    cpr_from_prev_day,   # preferred (calendar-aware via day grouping when prior-day bars exist)
    vwap_last,
    rsi_last,
    atr_last,
    obv_trend,
)

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_INTERVAL_MIN = 15

__all__ = ["MonitorConfig", "run_live_console", "_one_pass"]

@dataclass
class MonitorConfig:
    symbols: List[str]
    interval_min: int = DEFAULT_INTERVAL_MIN
    view: str = "compact"  # "compact" | "expanded" | "both"
    limit_bars: int = 200  # keep memory low


# --------------------- data fetch ---------------------
async def _fetch_intraday(symbol: str, interval: str, limit: int) -> pl.DataFrame:
    df = await fetch_intraday(symbol, interval)
    return df.tail(limit) if limit and not df.is_empty() else df


async def fetch_intraday_15m(symbol: str, limit: int = 200) -> pl.DataFrame:
    return await _fetch_intraday(symbol, "15m", limit)


async def fetch_intraday_60m(symbol: str, limit: int = 240) -> pl.DataFrame:
    return await _fetch_intraday(symbol, "60m", limit)


# --------------------- CPR fallback (calendar-aware) ---------------------
def _cpr_from_last_completed_session(df: pl.DataFrame) -> Optional[float]:
    """
    Calendar-aware CPR from the last *completed* session present in df.

    Logic:
      - Build a date column from timestamp in IST.
      - Identify the last completed session date:
          • If df contains today's date → use the previous date present.
          • Else → use the last date present.
      - Compute prior-day H/L and last close from that date's rows.
      - Return (H+L+C)/3 or None on failure.
    """
    if df.is_empty() or "timestamp" not in df.columns:
        return None

    try:
        dated = df.with_columns(pl.col("timestamp").dt.convert_time_zone("Asia/Kolkata").dt.date().alias("d"))
        # all available session dates, sorted
        dlist = (
            dated.select(pl.col("d"))
                 .unique()
                 .sort("d")
                 .get_column("d")
                 .to_list()
        )
        if not dlist:
            return None

        today_ist = datetime.now(tz=IST).date()
        if today_ist in dlist and len(dlist) >= 2:
            target_day = dlist[-2]  # previous available trading day
        else:
            target_day = dlist[-1]  # last available day in data

        day_df = dated.filter(pl.col("d") == target_day)
        if day_df.is_empty():
            return None

        # Compute prior-day H/L and last close (Series operations are simplest here)
        hi = float(day_df["high"].max())
        lo = float(day_df["low"].min())
        cl_ser = day_df["close"].drop_nulls()
        if cl_ser.is_empty():
            return None
        cl = float(cl_ser.tail(1).item())
        return (hi + lo + cl) / 3.0
    except Exception as e:
        log.debug(f"[Live] _cpr_from_last_completed_session fallback failed: {e}")
        return None


async def _ensure_prev_day_cpr(symbol: str, df15: pl.DataFrame, limit_bars: int) -> Optional[float]:
    """
    Try canonical CPR first; if missing, compute calendar-aware fallback.
    If still missing (e.g., broker returned only a few bars for today),
    enrich once with 60m history and retry.
    """
    # 1) Try the canonical helper (uses prior session when present)
    try:
        cpr = cpr_from_prev_day(df15)
        if cpr is not None:
            return cpr
    except Exception:
        # fall through to our fallback
        pass

    # 2) Calendar-aware fallback on current df
    cpr = _cpr_from_last_completed_session(df15)
    if cpr is not None:
        return cpr

    # 3) Enrich once using 60m to get a longer span, then recompute
    log.info(f"[Live] {symbol}: augmenting history via 60m fallback")
    df60 = await fetch_intraday_60m(symbol, limit=3 * limit_bars)  # widen a bit
    if df60.is_empty():
        return None

    # union + sort, de-dup by timestamp
    # Using vertical concat + unique on timestamp is simple and robust
    merged = pl.concat([df15, df60], how="vertical_relaxed").unique(subset=["timestamp"]).sort("timestamp")
    merged = merged.tail(max(limit_bars, 200))  # cap size
    # Retry both methods
    try:
        cpr = cpr_from_prev_day(merged)
        if cpr is not None:
            return cpr
    except Exception:
        pass
    return _cpr_from_last_completed_session(merged)


# --------------------- Core One-Pass ---------------------
async def _one_pass(cfg: MonitorConfig) -> List[Dict]:
    rows: List[Dict] = []
    for sym in cfg.symbols:
        try:
            df = await fetch_intraday_15m(sym, limit=cfg.limit_bars)
            if df.is_empty():
                log.warning(f"[Live] No data for {sym}")
                continue

            close_series = df["close"].cast(pl.Float64, strict=False)
            if close_series.is_empty():
                log.warning(f"[Live] No close series for {sym}")
                continue
            last_close = float(close_series.tail(1).item())

            # CPR (strict: prior trading day only, with enrichment if needed)
            cpr = await _ensure_prev_day_cpr(sym, df, cfg.limit_bars)

            # Other indicators (gracefully None if short dataset)
            vwap = vwap_last(df)
            rsi = rsi_last(close_series, 14)
            atr = atr_last(df, 14)
            obv = obv_trend(df)

            summary, targets, sl = _structure_and_targets(last_close, cpr, vwap, rsi, atr, obv)
            rows.append({
                "symbol": sym, "cmp": last_close, "cpr": cpr, "vwap": vwap,
                "atr": atr, "rsi": rsi, "obv": obv, "summary": summary,
                "targets": targets, "sl": sl,
            })
        except Exception as e:
            log.exception(f"[Live] {sym} failed → {e}")
    return rows


# --------------------- Console Rendering ---------------------
async def run_live_console(cfg: MonitorConfig):
    meta = get_market_state()
    head = Panel.fit(
        f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | Session: {meta['session']} | Syms: {len(cfg.symbols)}",
        border_style="green",
    )

    rows = await _one_pass(cfg)
    comp, expd = _compact_table(rows), _expanded_table(rows)
    body = comp if cfg.view == "compact" else expd if cfg.view == "expanded" else Group(comp, expd)

    with Live(Group(head, body), refresh_per_second=4, screen=False) as live:
        while True:
            await sleep_until_next_candle(cfg.interval_min, jitter_ratio=0.10, emit_log=False)
            rows = await _one_pass(cfg)
            comp, expd = _compact_table(rows), _expanded_table(rows)
            body = comp if cfg.view == "compact" else expd if cfg.view == "expanded" else Group(comp, expd)
            meta = get_market_state()
            head = Panel.fit(
                f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | Session: {meta['session']}",
                border_style="green",
            )
            live.update(Group(head, body))


# --------------------- Helpers ---------------------
def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:,.1f}"
    return str(x)


def _compact_table(rows: List[Dict]) -> Table:
    t = Table(title="Live Intraday (Compact)", expand=True)
    for c in ["Symbol", "CPR", "VWAP", "ATR", "RSI", "OBV", "Summary", "Targets", "SL"]:
        t.add_column(c)
    for r in rows:
        t.add_row(
            r["symbol"],
            _fmt(r.get("cpr")),
            _fmt(r.get("vwap")),
            _fmt(r.get("atr")),
            _fmt(r.get("rsi")),
            str(r.get("obv", "—")),
            r.get("summary", "—"),
            " • ".join(r.get("targets", [])),
            _fmt(r.get("sl")),
        )
    return t


def _expanded_table(rows: List[Dict]) -> Table:
    t = Table(title="Live Intraday (Expanded)", expand=True)
    for c in ["Symbol", "CMP", "CPR", "VWAP", "ATR", "RSI", "OBV Trend", "Structure", "Targets", "SL"]:
        t.add_column(c)
    for r in rows:
        t.add_row(
            r["symbol"], _fmt(r.get("cmp")), _fmt(r.get("cpr")), _fmt(r.get("vwap")),
            _fmt(r.get("atr")), _fmt(r.get("rsi")), str(r.get("obv", "—")),
            r.get("summary", "—"), " → ".join(r.get("targets", [])), _fmt(r.get("sl")),
        )
    return t


def _structure_and_targets(last_close: float, cpr, vwap, rsi, atr, obv) -> tuple[str, list[str], float]:
    summary = []
    if cpr is not None and vwap is not None:
        if last_close > max(cpr, vwap):
            summary.append("Above VWAP/CPR")
        elif last_close < min(cpr, vwap):
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

    atr_val = atr or max(1.0, last_close * 0.01)
    t1 = round(last_close + 0.5 * atr_val, 1)
    t2 = round(last_close + 1.0 * atr_val, 1)
    t3 = round(last_close + 1.5 * atr_val, 1)
    sl = round(last_close - 1.0 * atr_val, 1)
    return ("; ".join(summary) if summary else "Neutral"), [f"T1 {t1}", f"T2 {t2}", f"T3 {t3}"], sl

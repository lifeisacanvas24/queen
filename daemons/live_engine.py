#!/usr/bin/env python3
# ============================================================
# queen/daemons/live_engine.py — v2.1
# Cockpit-row powered live loop
# ✅ CMP from pure intraday (today-only, matches old engine)
# ✅ Indicators/targets from backfilled DF (via services.live)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import polars as pl
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

# 👇 NEW: for CMP we always use the pure intraday endpoint
from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.candles import ensure_sorted
from queen.helpers.candles import last_close as candle_last_close
from queen.helpers.logger import log
from queen.helpers.market import get_market_state, sleep_until_next_candle
from queen.services.cockpit_row import build_cockpit_row
from queen.services.live import _intraday_with_backfill, structure_and_targets

# Indicator cores (same as services.live)
from queen.technicals.indicators.core import (
    atr_last,
    cpr_from_prev_day,
    obv_trend,
    rsi_last,
    vwap_last,
)

DEFAULT_INTERVAL_MIN = 15

__all__ = ["MonitorConfig", "run_live_console", "_one_pass"]


# --------------------- config ---------------------
@dataclass
class MonitorConfig:
    symbols: List[str]
    interval_min: int = DEFAULT_INTERVAL_MIN
    view: str = "compact"  # "compact" | "expanded" | "both"
    limit_bars: int = 200  # keep memory low


# --------------------- helpers ---------------------
async def _today_intraday_df(symbol: str, interval_min: int, limit: int) -> pl.DataFrame:
    """Pure intraday fetch for *today only*, used to anchor CMP.

    This mirrors the old v1.6 behaviour:
      - fetch_intraday("15m") → tail(limit) → last close.
    """
    iv = f"{interval_min}m"
    df = await fetch_intraday(symbol, iv)
    if not df.is_empty() and limit:
        df = df.tail(limit)
    return ensure_sorted(df) if not df.is_empty() else df


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:,.1f}"
    return str(x)


# --------------------- Core One-Pass ---------------------
async def _one_pass(cfg: MonitorConfig) -> List[Dict]:
    """Build one snapshot of rows for all symbols.

    🔹 CMP is always from *pure intraday today* (matches old engine).
    🔹 Indicators (CPR / VWAP / RSI / ATR / OBV / targets / SL)
       use the richer backfilled DF via _intraday_with_backfill.
    """
    rows: List[Dict] = []
    interval_str = f"{cfg.interval_min}m"

    for sym in cfg.symbols:
        try:
            # A) CMP anchor — today-only intraday (old behaviour)
            df_today: pl.DataFrame = await _today_intraday_df(
                sym, cfg.interval_min, cfg.limit_bars
            )
            if df_today.is_empty():
                log.warning(f"[Live] No intraday data for {sym} ({interval_str})")
                # we still try backfilled DF below for structure, but CMP will be None
                cmp_val = None
            else:
                cmp_val = candle_last_close(df_today)
                if cmp_val is None:
                    log.warning(f"[Live] No close series for {sym} on today-only DF")

            # B) Rich context DF — with backfill for ATR / CPR etc.
            df_ctx: pl.DataFrame = await _intraday_with_backfill(sym, cfg.interval_min)
            if df_ctx.is_empty():
                # If backfill failed, fall back to today DF for indicators as well.
                df_ctx = df_today

            if df_ctx.is_empty():
                # nothing to work with at all
                continue

            df_ctx = ensure_sorted(df_ctx)

            # 2) Indicator core (same as cmp_snapshot / live.cmp_snapshot)
            cpr = cpr_from_prev_day(df_ctx)
            vwap = vwap_last(df_ctx)
            close_series = df_ctx["close"]
            rsi = rsi_last(close_series, 14)
            atr = atr_last(df_ctx, 14)
            obv = obv_trend(df_ctx)

            # 3) Structure + targets based on CMP + indicator context
            # If for some reason CMP is None, fall back to contextual DF last close.
            eff_cmp = cmp_val
            if eff_cmp is None:
                eff_cmp = candle_last_close(df_ctx)
            if eff_cmp is None:
                log.warning(f"[Live] Unable to resolve CMP for {sym}")
                continue

            summary, targets, sl = structure_and_targets(
                last_close_val=eff_cmp,
                cpr=cpr,
                vwap=vwap,
                rsi=rsi,
                atr=atr,
                obv=obv,
            )

            # 4) Optional cockpit_row enrichment (PnL, Bible meta, strip)
            row = build_cockpit_row(
                sym,
                df_ctx,
                interval=interval_str,
                book="all",
                tactical=None,
                pattern=None,
                reversal=None,
                volatility=None,
            ) or {}

            # 5) Fill / override the fields the TUI cares about
            row.update(
                {
                    "symbol": sym,
                    "cmp": eff_cmp,  # ✅ CMP from today-only intraday
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

            rows.append(row)

        except Exception as e:
            log.exception(f"[Live] {sym} snapshot failed → {e}")

    return rows


# --------------------- Console Rendering ---------------------
async def run_live_console(cfg: MonitorConfig):
    """Rich live console dashboard, now driven by cockpit rows + core indicators."""
    meta = get_market_state()
    head = Panel.fit(
        f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | "
        f"Session: {meta['session']} | Syms: {len(cfg.symbols)}",
        border_style="green",
    )

    rows = await _one_pass(cfg)
    comp, expd = _compact_table(rows), _expanded_table(rows)
    body = (
        comp
        if cfg.view == "compact"
        else expd if cfg.view == "expanded" else Group(comp, expd)
    )

    with Live(Group(head, body), refresh_per_second=4, screen=False) as live:
        while True:
            await sleep_until_next_candle(
                cfg.interval_min, jitter_ratio=0.10, emit_log=False
            )
            rows = await _one_pass(cfg)
            comp, expd = _compact_table(rows), _expanded_table(rows)
            body = (
                comp
                if cfg.view == "compact"
                else expd
                if cfg.view == "expanded"
                else Group(comp, expd)
            )
            meta = get_market_state()
            head = Panel.fit(
                f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | "
                f"Session: {meta['session']}",
                border_style="green",
            )
            live.update(Group(head, body))


# --------------------- Tables ---------------------
def _compact_table(rows: List[Dict]) -> Table:
    """Compact table — keep the old feel, driven by enriched rows."""
    t = Table(title="Live Intraday (Compact)", expand=True)
    for c in ["Symbol", "CPR", "VWAP", "ATR", "RSI", "OBV", "Summary", "Targets", "SL"]:
        t.add_column(c)

    for r in rows:
        t.add_row(
            r.get("symbol", "—"),
            _fmt(r.get("cpr")),
            _fmt(r.get("vwap")),
            _fmt(r.get("atr")),
            _fmt(r.get("rsi")),
            _fmt(r.get("obv")),
            r.get("summary") or r.get("notes", "—"),
            " • ".join(r.get("targets", []) or []),
            _fmt(r.get("sl")),
        )
    return t


def _expanded_table(rows: List[Dict]) -> Table:
    """Expanded table — add CMP + structure."""
    t = Table(title="Live Intraday (Expanded)", expand=True)
    for c in [
        "Symbol",
        "CMP",
        "CPR",
        "VWAP",
        "ATR",
        "RSI",
        "OBV Trend",
        "Structure",
        "Targets",
        "SL",
    ]:
        t.add_column(c)

    for r in rows:
        t.add_row(
            r.get("symbol", "—"),
            _fmt(r.get("cmp")),
            _fmt(r.get("cpr")),
            _fmt(r.get("vwap")),
            _fmt(r.get("atr")),
            _fmt(r.get("rsi")),
            _fmt(r.get("obv")),
            r.get("summary") or r.get("notes", "—"),
            " → ".join(r.get("targets", []) or []),
            _fmt(r.get("sl")),
        )
    return t

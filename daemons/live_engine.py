#!/usr/bin/env python3
# ============================================================
# queen/daemons/live_engine.py — v1.8
# Cockpit-row powered live loop (DRY + interval-aware)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import polars as pl
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.candles import ensure_sorted
from queen.helpers.candles import last_close as candle_last_close
from queen.helpers.logger import log
from queen.helpers.market import get_market_state, sleep_until_next_candle
from queen.services.cockpit_row import build_cockpit_row

DEFAULT_INTERVAL_MIN = 15

__all__ = ["MonitorConfig", "run_live_console", "_one_pass"]


# --------------------- config ---------------------
@dataclass
class MonitorConfig:
    symbols: List[str]
    interval_min: int = DEFAULT_INTERVAL_MIN
    view: str = "compact"  # "compact" | "expanded" | "both"
    limit_bars: int = 200  # keep memory low


# --------------------- data fetch ---------------------
async def _fetch_intraday(symbol: str, interval: str, limit: int) -> pl.DataFrame:
    """Thin wrapper over fetch_intraday → Polars frame, tail-capped."""
    df = await fetch_intraday(symbol, interval)
    return df.tail(limit) if limit and not df.is_empty() else df


# --------------------- Core One-Pass (DRY with cockpit) ---------------------
async def _one_pass(cfg: MonitorConfig) -> List[Dict]:
    """Build one snapshot of rows for all symbols.

    Important:
      • Uses the same build_cockpit_row() as /cockpit/api/summary
      • Interval is cfg.interval_min (no hard-coded 15m)
      • CMP is normalized via helpers.candles.last_close(df) if needed

    """
    rows: List[Dict] = []
    interval_str = f"{cfg.interval_min}m"

    for sym in cfg.symbols:
        try:
            df = await _fetch_intraday(sym, interval_str, cfg.limit_bars)
            if df.is_empty():
                log.warning(f"[Live] No data for {sym} ({interval_str})")
                continue

            df = ensure_sorted(df)

            # Canonical cockpit row (same as Summary API)
            row = build_cockpit_row(
                sym,
                df,
                interval=interval_str,
                book="all",      # CLI is book-agnostic; 'all' mirrors summary default
                tactical=None,   # tactical/pattern/reversal/volatility can be wired later
                pattern=None,
                reversal=None,
                volatility=None,
            )
            if not row:
                continue

            # CMP: prefer cockpit_row; else force from candles
            cmp_val = row.get("cmp")
            if cmp_val is None:
                cmp_val = candle_last_close(df)
                if cmp_val is not None:
                    row["cmp"] = cmp_val

            rows.append(row)

        except Exception as e:
            log.exception(f"[Live] {sym} snapshot failed → {e}")

    return rows


# --------------------- Console Rendering ---------------------
async def run_live_console(cfg: MonitorConfig):
    """Rich live console dashboard, now driven by cockpit rows."""
    meta = get_market_state()
    head = Panel.fit(
        f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | "
        f"Session: {meta['session']} | Syms: {len(cfg.symbols)}",
        border_style="green",
    )

    rows = await _one_pass(cfg)
    comp, expd = _compact_table(rows), _expanded_table(rows)
    body = comp if cfg.view == "compact" else expd if cfg.view == "expanded" else Group(
        comp, expd
    )

    with Live(Group(head, body), refresh_per_second=4, screen=False) as live:
        while True:
            await sleep_until_next_candle(
                cfg.interval_min, jitter_ratio=0.10, emit_log=False
            )
            rows = await _one_pass(cfg)
            comp, expd = _compact_table(rows), _expanded_table(rows)
            body = comp if cfg.view == "compact" else expd if cfg.view == "expanded" else Group(
                comp, expd
            )
            meta = get_market_state()
            head = Panel.fit(
                f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | "
                f"Session: {meta['session']}",
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
    """Compact table — keep the old feel, but drive from cockpit rows."""
    t = Table(title="Live Intraday (Compact)", expand=True)
    for c in ["Symbol", "CPR", "VWAP", "ATR", "RSI", "OBV", "Summary", "Targets", "SL"]:
        t.add_column(c)

    for r in rows:
        t.add_row(
            r.get("symbol", "—"),
            _fmt(r.get("cpr")),                     # from build_cockpit_row / indicators
            _fmt(r.get("vwap") or r.get("avg_price")),
            _fmt(r.get("atr")),
            _fmt(r.get("rsi")),
            _fmt(r.get("obv")),
            r.get("summary") or r.get("notes", "—"),
            " • ".join(r.get("targets", [])),
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
            _fmt(r.get("vwap") or r.get("avg_price")),
            _fmt(r.get("atr")),
            _fmt(r.get("rsi")),
            _fmt(r.get("obv")),
            r.get("summary") or r.get("notes", "—"),
            " → ".join(r.get("targets", [])),
            _fmt(r.get("sl")),
        )
    return t

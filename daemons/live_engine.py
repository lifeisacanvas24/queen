#!/usr/bin/env python3
# ============================================================
# queen/monitor/live_engine.py — v1.0 (Upstox live loop + indicators)
# ============================================================
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import polars as pl
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.console import Group

from queen.helpers.logger import log
from queen.helpers.market import MARKET_TZ, sleep_until_next_candle, get_market_state
from queen.settings import settings as SETTINGS
from queen.helpers import io
from queen.helpers.instruments import resolve_instrument

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
DEFAULT_INTERVAL_MIN = 15


@dataclass
class MonitorConfig:
    symbols: List[str]
    interval_min: int = DEFAULT_INTERVAL_MIN
    view: str = "compact"  # "compact" | "expanded" | "both"


# ------------------------------------------------------------
# Fetch (wire to your Upstox route)
# ------------------------------------------------------------
async def fetch_intraday_15m(symbol: str, limit: int = 120) -> pl.DataFrame:
    """
    Return a Polars DataFrame with columns:
    ['timestamp','open','high','low','close','volume'] (tz-aware UTC/IST ok).
    This adapter uses your existing resolver + fetch router.
    """
    try:
        ins_key = resolve_instrument(symbol, mode="INTRADAY")
    except Exception:
        ins_key = symbol  # allow raw key if already "NSE_EQ|..."
    # 👉 Replace with your actual fetcher call
    from queen.fetchers.upstox_fetcher import fetch_intraday_minutes

    df = await fetch_intraday_minutes(ins_key, minutes=15, limit=limit)
    return df if isinstance(df, pl.DataFrame) else pl.DataFrame()


# ------------------------------------------------------------
# Indicators (CPR, VWAP, RSI, ATR, OBV)
# ------------------------------------------------------------
def _prev_day_hlc(df: pl.DataFrame) -> Tuple[float, float, float] | None:
    if df.is_empty():
        return None
    ts_col = "timestamp"
    d_ist = df.select(
        pl.col(ts_col).dt.convert_time_zone(str(MARKET_TZ)).dt.date()
    ).to_series()
    prev_day = d_ist.max() - dt.timedelta(days=1)
    day_df = df.filter(
        pl.col(ts_col).dt.convert_time_zone(str(MARKET_TZ)).dt.date() == prev_day
    )
    if day_df.is_empty():
        return None
    H = float(day_df["high"].max())
    L = float(day_df["low"].min())
    C = float(day_df["close"].tail(1).item())
    return H, L, C


def _cpr_from_prev_day(df: pl.DataFrame) -> float | None:
    hlc = _prev_day_hlc(df)
    if not hlc:
        return None
    H, L, C = hlc
    pivot = (H + L + C) / 3.0
    return pivot  # center pivot as CPR proxy


def _vwap(df: pl.DataFrame) -> float | None:
    if df.is_empty():
        return None
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].cast(pl.Float64, strict=False).fill_null(0)
    num = (typical * vol).sum()
    den = vol.sum()
    return float(num / den) if float(den) > 0 else None


def _rsi(close: pl.Series, length: int = 14) -> float | None:
    if close.len() <= length + 1:
        return None
    diff = close.diff()
    up = diff.clip_min(0.0)
    dn = (-diff).clip_min(0.0)
    roll_up = up.rolling_mean(window_size=length)
    roll_dn = dn.rolling_mean(window_size=length)
    rs = roll_up / pl.when(roll_dn == 0).then(1e-9).otherwise(roll_dn)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.drop_nulls().tail(1)
    return float(val.item()) if val.len() else None


def _atr(df: pl.DataFrame, length: int = 14) -> float | None:
    if df.height < length + 2:
        return None
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pl.max_horizontal(h - l, (h - prev_c).abs(), (l - prev_c).abs())
    atr = tr.rolling_mean(window_size=length).drop_nulls().tail(1)
    return float(atr.item()) if atr.len() else None


def _obv_trend(df: pl.DataFrame) -> str:
    if df.is_empty():
        return "Flat"
    sign = (df["close"].diff() > 0).cast(pl.Int8) - (df["close"].diff() < 0).cast(
        pl.Int8
    )
    obv = (sign * df["volume"].fill_null(0)).cum_sum()
    # Short slope check on last ~20 bars
    last = obv.tail(20)
    if last.is_empty():
        return "Flat"
    rising = float(last.tail(1).item() - last.head(1).item())
    return "Rising" if rising > 0 else "Falling" if rising < 0 else "Flat"


def _structure_and_targets(
    symbol: str,
    cpr: float | None,
    vwap: float | None,
    rsi: float | None,
    atr: float | None,
    obv_trend: str,
    last_close: float,
) -> Tuple[str, List[str], float]:
    # Very lightweight heuristics; adjust later with your fusion policy.
    summary = []
    if cpr and vwap:
        if last_close > max(cpr, vwap):
            summary.append("Above VWAP/CPR")
        elif last_close < min(cpr, vwap):
            summary.append("Below VWAP/CPR")
        else:
            summary.append("Inside CPR/VWAP band")
    if obv_trend == "Rising":
        summary.append("OBV ↑")
    elif obv_trend == "Falling":
        summary.append("OBV ↓")
    if rsi is not None:
        if rsi >= 60:
            summary.append("RSI strong")
        elif rsi <= 45:
            summary.append("RSI weak")
    text = "; ".join(summary) if summary else "Neutral"

    # Dynamic ladder: T1..T3 around ATR; SL under structure
    atr_val = atr or max(1.0, last_close * 0.01)
    t1 = round(last_close + 0.5 * atr_val, 1)
    t2 = round(last_close + 1.0 * atr_val, 1)
    t3 = round(last_close + 1.5 * atr_val, 1)
    targets = [f"T1 {t1}", f"T2 {t2}", f"T3 {t3}"]
    sl = round(last_close - 1.0 * atr_val, 1)
    return text, targets, sl


# ------------------------------------------------------------
# Renderers
# ------------------------------------------------------------
def _compact_table(rows: List[Dict]) -> Table:
    t = Table(title="Live Intraday (Compact)", expand=True)
    t.add_column("Symbol")
    t.add_column("CPR")
    t.add_column("VWAP")
    t.add_column("ATR")
    t.add_column("RSI")
    t.add_column("OBV")
    t.add_column("Summary")
    t.add_column("Targets")
    t.add_column("SL")
    for r in rows:
        t.add_row(
            r["symbol"],
            _fmt(r["cpr"]),
            _fmt(r["vwap"]),
            _fmt(r["atr"]),
            _fmt(r["rsi"]),
            r["obv"],
            r["summary"],
            " • ".join(r["targets"]),
            _fmt(r["sl"]),
        )
    return t


def _expanded_table(rows: List[Dict]) -> Table:
    t = Table(title="Live Intraday (Expanded Card View)", expand=True)
    t.add_column("Symbol")
    t.add_column("CMP")
    t.add_column("CPR")
    t.add_column("VWAP")
    t.add_column("ATR")
    t.add_column("RSI")
    t.add_column("OBV Trend")
    t.add_column("Structure Summary")
    t.add_column("Updated Targets")
    t.add_column("SL (Struct.)")
    for r in rows:
        t.add_row(
            r["symbol"],
            _fmt(r["cmp"]),
            _fmt(r["cpr"]),
            _fmt(r["vwap"]),
            _fmt(r["atr"]),
            _fmt(r["rsi"]),
            r["obv"],
            r["summary"],
            " → ".join(r["targets"]),
            _fmt(r["sl"]),
        )
    return t


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:,.1f}"
    return str(x)


# ------------------------------------------------------------
# One refresh pass
# ------------------------------------------------------------
async def _one_pass(cfg: MonitorConfig) -> List[Dict]:
    rows: List[Dict] = []
    for sym in cfg.symbols:
        df = await fetch_intraday_15m(sym, limit=200)
        if df.is_empty():
            log.warning(f"[Live] No data for {sym}")
            continue
        last_close = float(df["close"].tail(1).item())
        cpr = _cpr_from_prev_day(df)
        vwap = _vwap(df)
        rsi = _rsi(df["close"].cast(pl.Float64, strict=False), 14)
        atr = _atr(df, 14)
        obv = _obv_trend(df)
        summary, targets, sl = _structure_and_targets(
            sym, cpr, vwap, rsi, atr, obv, last_close
        )

        rows.append(
            {
                "symbol": sym,
                "cmp": last_close,
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
    return rows


# ------------------------------------------------------------
# Public: live loop (console)
# ------------------------------------------------------------
async def run_live_console(cfg: MonitorConfig):
    # initial header panel
    meta = get_market_state()
    head = Panel.fit(
        f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | Session: {meta['session']}",
        border_style="green",
    )
    rows = await _one_pass(cfg)
    comp = _compact_table(rows)
    expd = _expanded_table(rows)
    body = (
        comp
        if cfg.view == "compact"
        else expd
        if cfg.view == "expanded"
        else Group(comp, expd)
    )

    with Live(Group(head, body), refresh_per_second=4, screen=False) as live:
        while True:
            await sleep_until_next_candle(
                cfg.interval_min, jitter_ratio=0.10, emit_log=False
            )
            rows = await _one_pass(cfg)
            comp = _compact_table(rows)
            expd = _expanded_table(rows)
            body = (
                comp
                if cfg.view == "compact"
                else expd
                if cfg.view == "expanded"
                else Group(comp, expd)
            )
            meta = get_market_state()
            head = Panel.fit(
                f"✅ Live {cfg.interval_min}-min | Gate: {meta['gate']} | Session: {meta['session']}",
                border_style="green",
            )
            live.update(Group(head, body))

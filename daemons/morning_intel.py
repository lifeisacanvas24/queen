#!/usr/bin/env python3
# ============================================================
# queen/daemons/morning_intel.py — v1.0 (Next-session forecast + actionable leaderboard)
# ============================================================
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import polars as pl

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS
from queen.settings.settings import PATHS
from queen.helpers.instruments import resolve_instrument
from queen.fetchers.upstox_fetcher import (
    fetch_intraday,
    fetch_daily_range,
)
# shared indicator math (DRY)
from queen.technicals.indicators.core import (
    rsi_last, vwap_last, atr_last, cpr_from_prev_day, obv_trend,
    ema,  # we'll use ema().tail(1).item() for bias checks
)

# optional supertrend import — soft dependency
try:
    # expected: returns DataFrame with columns ["supertrend","supertrend_dir"]
    from queen.technicals.indicators.advanced import supertrend as st_compute  # type: ignore
except Exception:  # pragma: no cover
    st_compute = None


@dataclass
class ForecastRow:
    symbol: str
    cmp: Optional[float]
    score: int
    decision: str
    reasons: List[str]
    ema_bias: str
    rsi: Optional[float]
    vwap_zone: str
    supertrend_bias: str


# --------------------- helpers ---------------------
def _buy_sell_hold(score: int) -> str:
    if score >= 8:
        return "BUY"
    if score <= 3:
        return "SELL"
    return "HOLD"


def _fmt_last(s: pl.Series) -> Optional[float]:
    if s is None or s.len() == 0:
        return None
    tail = s.drop_nulls().tail(1)
    return float(tail.item()) if tail.len() else None


async def _daily_df(symbol: str, days_window: int = 14, bars_fallback: int = 40) -> pl.DataFrame:
    """Fetch ~2 weeks of daily candles; this is robust to weekends/holidays."""
    to_d = date.today().isoformat()
    from_d = (date.today() - timedelta(days=days_window)).isoformat()
    df = await fetch_daily_range(symbol, from_d, to_d, "1d")
    if df.is_empty() and days_window < 60:
        # widen window once if broker gives no data in that span
        return await _daily_df(symbol, days_window=60, bars_fallback=bars_fallback)
    return df.tail(bars_fallback) if not df.is_empty() else df


async def _intraday_df(symbol: str, interval: str = "15m", tail: int = 200) -> pl.DataFrame:
    df = await fetch_intraday(symbol, interval)
    return df.tail(tail) if not df.is_empty() else df


def _ema_bias(daily_df: pl.DataFrame) -> str:
    """EMA20/50/200 staircase bias from daily candles."""
    if daily_df.is_empty() or daily_df.height < 200:
        return "Neutral"
    e20 = _fmt_last(ema(daily_df, 20))
    e50 = _fmt_last(ema(daily_df, 50))
    e200 = _fmt_last(ema(daily_df, 200))
    if None in (e20, e50, e200):
        return "Neutral"
    if e20 > e50 > e200:
        return "Bullish"
    if e20 < e50 < e200:
        return "Bearish"
    return "Neutral"


def _supertrend_bias(df: pl.DataFrame) -> Tuple[str, Optional[float]]:
    if st_compute is None or df.is_empty():
        return "Neutral", None
    try:
        st_df = st_compute(df)  # must return "supertrend" & "supertrend_dir"
        bias = str(st_df["supertrend_dir"].tail(1).item())
        val = float(st_df["supertrend"].tail(1).item())
        return bias, val
    except Exception:
        return "Neutral", None


def _vwap_zone(cmp_: Optional[float], vwap_: Optional[float]) -> str:
    if cmp_ is None or vwap_ is None:
        return "Neutral"
    if cmp_ > vwap_:
        return "Above VWAP"
    if cmp_ < vwap_:
        return "Below VWAP"
    return "Neutral"


def _score_and_reasons(
    ema_bias: str,
    supertrend_bias: str,
    rsi_val: Optional[float],
    cmp_: Optional[float],
    vwap_: Optional[float],
    e50_last: Optional[float],
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    if ema_bias == "Bullish":
        score += 3
        reasons.append("EMA stack ↑")
    elif ema_bias == "Bearish":
        score -= 2
        reasons.append("EMA stack ↓")

    if supertrend_bias == "Bullish":
        score += 2
        reasons.append("Supertrend ↑")
    elif supertrend_bias == "Bearish":
        score -= 2
        reasons.append("Supertrend ↓")

    if rsi_val is not None:
        if rsi_val >= 60:
            score += 2
            reasons.append("RSI strong")
        elif rsi_val <= 45:
            score -= 2
            reasons.append("RSI weak")

    if cmp_ is not None and vwap_ is not None:
        if cmp_ > vwap_:
            score += 1
            reasons.append("Price > VWAP")
        else:
            reasons.append("Price ≤ VWAP")

    if cmp_ is not None and e50_last is not None:
        if cmp_ > e50_last:
            score += 2
            reasons.append("Price > EMA50")
        else:
            reasons.append("Price ≤ EMA50")

    # clamp to 0..10 for readability
    score = max(0, min(10, score))
    return score, reasons


# --------------------- core forecast ---------------------
async def forecast_next_session(next_session: date) -> List[ForecastRow]:
    """Compute BUY/SELL/HOLD + reasons for the next trading day."""
    symbols: List[str] = (
        SETTINGS.DEFAULTS.get("INTRADAY_SYMBOLS")  # prefer configured list
        or SETTINGS.DEFAULTS.get("SYMBOLS")
        or []
    )
    if not symbols:
        log.warning("[Forecast] No symbols in settings; nothing to do.")
        return []

    log.info(f"[Forecast] Preparing plan for {next_session.isoformat()} on {len(symbols)} symbols")

    out: List[ForecastRow] = []
    for sym in symbols:
        try:
            _ = resolve_instrument(sym)  # validates we know this instrument
        except Exception:
            log.warning(f"[Forecast] Unknown instrument key for {sym}; skipping")
            continue

        # fetch sources
        daily = await _daily_df(sym, days_window=30, bars_fallback=240)
        intra = await _intraday_df(sym, "15m", 200)

        if daily.is_empty() and intra.is_empty():
            log.warning(f"[Forecast] No data for {sym}")
            continue

        # last close (pref: intraday last close, else daily last close)
        cmp_: Optional[float] = None
        if not intra.is_empty():
            cmp_ = float(intra["close"].tail(1).item())
        elif not daily.is_empty():
            cmp_ = float(daily["close"].tail(1).item())

        # indicators (DRY)
        ema_bias = _ema_bias(daily)
        rsi_val = rsi_last((intra if not intra.is_empty() else daily)["close"].cast(pl.Float64, strict=False), 14)
        vwap_val = vwap_last(intra if not intra.is_empty() else daily)
        _ = atr_last(daily, 14)  # not used in score now, but available for SL sizing
        cpr = cpr_from_prev_day(intra if not intra.is_empty() else daily)  # available if needed
        obv = obv_trend(intra if not intra.is_empty() else daily)          # available if needed
        st_bias, _st_val = _supertrend_bias(intra if not intra.is_empty() else daily)

        e50_last = None
        if not daily.is_empty():
            e50_last = _fmt_last(ema(daily, 50))

        vwap_zone = _vwap_zone(cmp_, vwap_val)
        score, reasons = _score_and_reasons(ema_bias, st_bias, rsi_val, cmp_, vwap_val, e50_last)
        decision = _buy_sell_hold(score)

        out.append(
            ForecastRow(
                symbol=sym,
                cmp=cmp_,
                score=score,
                decision=decision,
                reasons=reasons,
                ema_bias=ema_bias,
                rsi=rsi_val,
                vwap_zone=vwap_zone,
                supertrend_bias=st_bias,
            )
        )

    # persist compact snapshot for server & cockpit
    if out:
        snap = [
            {
                "symbol": r.symbol,
                "cmp": r.cmp,
                "score": r.score,
                "decision": r.decision,
                "reasons": r.reasons,
                "ema_bias": r.ema_bias,
                "rsi": r.rsi,
                "vwap_zone": r.vwap_zone,
                "supertrend": r.supertrend_bias,
                "next_session": next_session.isoformat(),
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            for r in out
        ]
        PATHS["RUNTIME"].mkdir(parents=True, exist_ok=True)
        PATHS["SNAPSHOTS"].mkdir(parents=True, exist_ok=True)

        (PATHS["RUNTIME"] / "next_session_plan.json").write_text(
            __import__("json").dumps(snap, indent=2)
        )
        (PATHS["SNAPSHOTS"] / f"next_session_plan_{next_session.isoformat()}.json").write_text(
            __import__("json").dumps(snap, indent=2)
        )
        log.info(f"[Forecast] Saved next_session_plan for {next_session}")

    return out


# --------------------- CLI entry ---------------------
def run_cli(next_session: Optional[date] = None):
    next_d = next_session or (date.today() + timedelta(days=1))
    async def main():
        rows = await forecast_next_session(next_d)
        if not rows:
            log.warning("[Forecast] No rows produced")
            return
        # tiny console dump
        from rich.table import Table
        from rich.console import Console
        t = Table(title=f"Next Session Plan — {next_d.isoformat()}", expand=True)
        for c in ["Symbol","CMP","Score","Decision","EMA Bias","RSI","VWAP Zone","Supertrend","Reasons"]:
            t.add_column(c)
        for r in rows:
            t.add_row(
                r.symbol,
                f"{r.cmp:.2f}" if r.cmp is not None else "—",
                str(r.score),
                r.decision,
                r.ema_bias,
                f"{r.rsi:.1f}" if r.rsi is not None else "—",
                r.vwap_zone,
                r.supertrend_bias,
                " · ".join(r.reasons),
            )
        Console().print(t)

    asyncio.run(main())


if __name__ == "__main__":
    run_cli()

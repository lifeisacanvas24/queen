#!/usr/bin/env python3
# ============================================================
# queen/daemons/alert_v2.py — v0.12.1
# Closed-market aware · backfill · daily fallback
# Debug tails · colored crosses · settings-driven heuristics
# Startup summary of effective knobs
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Iterable, Optional, Tuple

import httpx
import polars as pl
from queen.alerts.evaluator import eval_rule
from queen.alerts.rules import Rule, load_rules
from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers import io
from queen.helpers.common import (
    colorize,
    indicator_call_kwargs,
    logger_supports_color,
    utc_now_iso,
)
from queen.helpers.instruments import get_listing_date, validate_historical_range
from queen.helpers.logger import log
from queen.helpers.market import MARKET_TZ, get_market_state, is_working_day
from queen.settings.indicator_policy import min_bars_for_indicator
from queen.settings.patterns import required_lookback  # ✅ settings owner
from queen.settings.settings import DEFAULTS, alert_path_jsonl, alert_path_rules
from queen.technicals.patterns.core import EXPORTS as PATTERNS
from queen.technicals.registry import get_indicator

# ------------------------------------------------------------
# 🔧 Config (settings-driven with safe fallbacks)
# ------------------------------------------------------------
_ALERTS = DEFAULTS.get("ALERTS", {}) or {}
_CONSOLE_COLORS = DEFAULTS.get("CONSOLE_COLORS", {}) or {}
_INDICATOR_MIN_BARS_MAP = DEFAULTS.get("INDICATOR_MIN_BARS", {}) or {}

DEFAULT_COOLDOWN = int(_ALERTS.get("COOLDOWN_SECONDS", 60))
_DEFAULT_DAILY_FALLBACK_BARS = int(_ALERTS.get("DAILY_FALLBACK_BARS", 150))
_INDICATOR_MIN_MULT = int(_ALERTS.get("INDICATOR_MIN_MULT", 3))
_INDICATOR_MIN_FLOOR = int(_ALERTS.get("INDICATOR_MIN_FLOOR", 30))
_PATTERN_CUSHION = int(_ALERTS.get("PATTERN_CUSHION", 5))
_PRICE_MIN_BARS = int(_ALERTS.get("PRICE_MIN_BARS", 5))

# ------------------------------------------------------------
# 🔧 Cooldown (proc-local)
# ------------------------------------------------------------
_LAST_FIRE: dict[tuple[str, str], float] = {}

# ============================================================
# 🧠 Helpers
# ============================================================


# ------------------------------------------------------------
# 🎨 Console colors
# ------------------------------------------------------------


# ------------------------------------------------------------
# 📅 Helpers
# ------------------------------------------------------------
def _backfill_days(start: date, max_days: int) -> Iterable[date]:
    d = start
    yielded = 0
    while yielded < max_days:
        d = d - timedelta(days=1)
        if is_working_day(d):
            yielded += 1
            yield d


# ------------------------------------------------------------
# 📏 Policy (settings-first)
# ------------------------------------------------------------
def _timeframe_key(tf: str) -> str:
    tf = (tf or "").lower()
    if tf.endswith("m"):
        return f"intraday_{tf}"
    if tf.endswith("h"):
        return f"hourly_{tf}"
    if tf == "1d":
        return "daily"
    if tf == "1w":
        return "weekly"
    if tf == "1mo":
        return "monthly"
    return f"intraday_{tf}"


def _min_bars_for(rule: Rule) -> int:
    """Priority:
    1) YAML override: rule.params.min_bars
    2) Settings policy for indicators: indicator_policy.min_bars_for_indicator()
    3) Heuristics from DEFAULTS['ALERTS'] for pattern/price
    """
    # 1) explicit override
    if rule.params and "min_bars" in rule.params:
        try:
            return max(1, int(rule.params["min_bars"]))
        except Exception:
            pass

    k = (rule.kind or "").lower()

    # 2) indicator: settings-driven policy first
    if k == "indicator":
        try:
            return max(
                1,
                int(
                    min_bars_for_indicator(rule.indicator or "", rule.timeframe or "1m")
                ),
            )
        except Exception:
            length = 14
            if rule.params and "length" in rule.params:
                try:
                    length = max(1, int(rule.params["length"]))
                except Exception:
                    pass
            return max(_INDICATOR_MIN_FLOOR, length * _INDICATOR_MIN_MULT)

    # 3a) pattern: computed lookback + cushion
    if k == "pattern":
        try:
            lb = int(
                required_lookback(
                    rule.pattern or "", _timeframe_key(rule.timeframe or "1m")
                )
            )
        except Exception:
            lb = 40
        return max(1, lb + _PATTERN_CUSHION)

    # 3b) price
    return max(1, _PRICE_MIN_BARS)


def _days_for_interval(interval: str, need_bars: int) -> int:
    iv = interval.lower()
    if iv == "1d":
        return max(need_bars + 20, 120)
    if iv == "1w":
        return max((need_bars + 6) * 7, 365)
    if iv == "1mo":
        return max((need_bars + 3) * 30, 720)
    return max(need_bars + 20, 120)


def _desired_window(days_back: int) -> Tuple[date, date]:
    to_dt = datetime.now(MARKET_TZ).date()
    from_dt = to_dt - timedelta(days=max(1, days_back))
    return from_dt, to_dt


def _clamp_to_listing(
    symbol: str, start: date, end: date
) -> Tuple[Optional[date], date]:
    ldt = get_listing_date(symbol)
    if isinstance(ldt, date) and ldt > start:
        start = ldt
    if start > end:
        return None, end
    return start, end


# ------------------------------------------------------------
# 📥 Fetchers
# ------------------------------------------------------------
async def _fetch_intraday(
    symbol: str,
    interval: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> pl.DataFrame:
    return await fetch_unified(
        symbol, mode="intraday", interval=interval, from_date=from_date, to_date=to_date
    )


async def _fetch_daily_window(
    symbol: str, interval: str, need_bars: int
) -> pl.DataFrame:
    days = _days_for_interval(interval, need_bars)
    wanted_from, wanted_to = _desired_window(days)
    clamped_from, end = _clamp_to_listing(symbol, wanted_from, wanted_to)
    if clamped_from is None:
        log.warning(
            f"[RangeCheck] {symbol}: window entirely before listing date — skip {interval}"
        )
        return pl.DataFrame()
    if not validate_historical_range(symbol, clamped_from):
        return pl.DataFrame()
    return await fetch_unified(
        symbol,
        mode="daily",
        interval=interval,
        from_date=clamped_from.isoformat(),
        to_date=end.isoformat(),
    )


async def _fetch_df_intraday_with_backfill(
    symbol: str,
    interval: str,
    min_bars: int,
    backfill_days: int,
    debug: bool,
) -> pl.DataFrame:
    today_local = datetime.now(MARKET_TZ).date()
    if validate_historical_range(symbol, today_local):
        df = await _fetch_intraday(symbol, interval)
        if not df.is_empty() and df.height >= min_bars:
            return df.tail(min_bars)
    else:
        if debug:
            log.info(
                f"[RangeCheck] {symbol}: today {today_local} pre-listing — skipping intraday"
            )

    for d in _backfill_days(today_local, backfill_days):
        if not validate_historical_range(symbol, d):
            if debug:
                log.info(
                    f"[RangeCheck] {symbol}: {d} < listing_date — stopping backfill"
                )
            break
        if debug:
            log.info(
                f"[Debug] {symbol} intraday empty for {today_local.isoformat()} — trying {d.isoformat()}…"
            )
        ds = d.strftime("%Y-%m-%d")
        df = await _fetch_intraday(symbol, interval, from_date=ds, to_date=ds)
        if not df.is_empty():
            return df.tail(min_bars)
        today_local = d
    return pl.DataFrame()


# ------------------------------------------------------------
# 🚨 Main
# ------------------------------------------------------------
async def run_daemon(
    rules_path: Optional[str],
    out_path: Optional[str],
    tick_interval: int = 1,
    once: bool = False,
    debug: bool = False,
    cooldown: int = DEFAULT_COOLDOWN,
    force_closed: bool = False,
    backfill_days: int = 0,
    no_intraday_backfill: bool = False,
    daily_fallback: bool = False,
    daily_bars: int = _DEFAULT_DAILY_FALLBACK_BARS,
    closed_eval_daily: bool = False,
    debug_values: int = 0,
    color_mode: str = "auto",  # "auto" | "always" | "never"
    http_post: Optional[str] = None,
    http_timeout: float = 3.0,
    post_only: bool = False,
):
    # color gate
    if color_mode == "always":
        color_ok = True
    elif color_mode == "never":
        color_ok = False
    else:
        color_ok = logger_supports_color(logging.getLogger())

    # rules + sinks
    rules = load_rules(rules_path)
    src = Path(rules_path) if rules_path else alert_path_rules()
    out = Path(out_path) if out_path else alert_path_jsonl()
    client: httpx.AsyncClient | None = None
    if http_post:
        client = httpx.AsyncClient(timeout=http_timeout)
    out.parent.mkdir(parents=True, exist_ok=True)

    # ---- startup summary ----
    log.info(
        colorize(
            "[AlertV2] Knobs → "
            f"cooldown={cooldown}s, daily_fallback_bars={daily_bars}, "
            f"ind_min_floor={_INDICATOR_MIN_FLOOR}, ind_min_mult={_INDICATOR_MIN_MULT}, "
            f"pattern_cushion={_PATTERN_CUSHION}, price_min_bars={_PRICE_MIN_BARS}, "
            f"per_indicator_overrides={len(_INDICATOR_MIN_BARS_MAP)}, "
            f"color_mode={color_mode} (enabled={color_ok})",
            "cyan",
            color_ok,
        )
    )
    log.info(f"[AlertV2] Loaded {len(rules)} rule(s) from {src.resolve()}")
    log.info(f"[AlertV2] Writing alerts → {out.resolve()}")

    async def evaluate_once():
        state = get_market_state()
        market_open = bool(state.get("is_open"))

        for rule in rules:
            sym = rule.symbol
            tf = (rule.timeframe or "1m").lower()
            need = _min_bars_for(rule)
            df: Optional[pl.DataFrame] = None

            try:
                # --- Closed-market handling ---
                if tf.endswith(("m", "h")) and not market_open and not force_closed:
                    if closed_eval_daily:
                        if debug:
                            log.info(
                                colorize(
                                    f"[Debug] {sym} {rule.name}: market closed — evaluating daily instead of {tf}",
                                    "cyan",
                                    color_ok,
                                )
                            )
                        df = await _fetch_daily_window(sym, "1d", max(need, daily_bars))
                    else:
                        if debug:
                            log.info(
                                colorize(
                                    f"[Debug] {sym} {rule.name}: market closed; skipping {tf}",
                                    "yellow",
                                    color_ok,
                                )
                            )
                        continue

                # --- Fetch data ---
                if df is None:
                    if tf.endswith(("m", "h")):
                        if no_intraday_backfill:
                            today = datetime.now(MARKET_TZ).date()
                            if not validate_historical_range(sym, today):
                                df = pl.DataFrame()
                            else:
                                df = await _fetch_intraday(sym, tf)
                        else:
                            df = await _fetch_df_intraday_with_backfill(
                                sym, tf, need, backfill_days, debug
                            )
                    elif tf in ("1d", "1w", "1mo"):
                        df = await _fetch_daily_window(sym, tf, need)
                    else:
                        df = await _fetch_daily_window(sym, "1d", need)

                # --- Optional fallback ---
                if df.is_empty() and daily_fallback and tf.endswith(("m", "h")):
                    if debug:
                        log.info(
                            colorize(
                                f"[Debug] {sym} intraday empty after backfill — falling back to daily",
                                "yellow",
                                color_ok,
                            )
                        )
                    df = await _fetch_daily_window(sym, "1d", max(need, daily_bars))

                # guards
                if df.is_empty():
                    if debug:
                        log.info(
                            colorize(
                                f"[Debug] {sym} {rule.name}: empty df for {tf}",
                                "yellow",
                                color_ok,
                            )
                        )
                    continue

                if df.height > need:
                    df = df.tail(need)

                # --- debug-values tail ---
                if debug and debug_values > 0:
                    try:
                        k = (rule.kind or "").lower()
                        if k == "price":
                            tail = df["close"].drop_nulls().tail(debug_values).to_list()
                            log.info(
                                colorize(
                                    f"[Debug] {sym} {rule.name}: close tail({debug_values}) → {tail}",
                                    "cyan",
                                    color_ok,
                                )
                            )
                        elif k == "indicator":
                            fn = get_indicator((rule.indicator or "").lower())
                            outv = fn(
                                df, **indicator_call_kwargs(rule.params)
                            )  # ✅ filtered kwargs
                            if isinstance(outv, pl.DataFrame):
                                for c in outv.columns:
                                    if pl.datatypes.is_numeric(outv[c].dtype):
                                        vals = (
                                            outv[c]
                                            .drop_nulls()
                                            .tail(debug_values)
                                            .to_list()
                                        )
                                        log.info(
                                            colorize(
                                                f"[Debug] {sym} {rule.name}: {c} tail({debug_values}) → {vals}",
                                                "cyan",
                                                color_ok,
                                            )
                                        )
                                        break
                            else:
                                vals = outv.drop_nulls().tail(debug_values).to_list()
                                nm = (
                                    getattr(outv, "name", rule.indicator)
                                    or rule.indicator
                                )
                                log.info(
                                    colorize(
                                        f"[Debug] {sym} {rule.name}: {nm} tail({debug_values}) → {vals}",
                                        "cyan",
                                        color_ok,
                                    )
                                )
                        elif k == "pattern":
                            fn = PATTERNS.get((rule.pattern or "").lower())
                            if fn:
                                mask = fn(df, **(rule.params or {}))
                                vals = [
                                    bool(x) for x in mask.tail(debug_values).to_list()
                                ]
                                log.info(
                                    colorize(
                                        f"[Debug] {sym} {rule.name}: {rule.pattern} tail({debug_values}) → {vals}",
                                        "cyan",
                                        color_ok,
                                    )
                                )
                    except Exception as e:
                        log.info(
                            colorize(
                                f"[Debug] {sym} {rule.name}: debug-values failed → {e}",
                                "yellow",
                                color_ok,
                            )
                        )

                # --- Evaluate rule ---
                ok, meta = eval_rule(rule, df)
                rname = rule.name or rule.pattern or rule.indicator or "unnamed"

                if ok:
                    key = (sym, rname)
                    now = monotonic()
                    last = _LAST_FIRE.get(key, 0.0)
                    if now - last < max(0, cooldown):
                        if debug:
                            log.info(
                                colorize(
                                    f"[Debug] cooldown skip: {sym} | {rname} ({now-last:.1f}s)",
                                    "yellow",
                                    color_ok,
                                )
                            )
                        continue

                    evt = {
                        "ts": utc_now_iso(),
                        "symbol": sym,
                        "rule": rname,
                        "detail": {
                            "kind": rule.kind,
                            "timeframe": rule.timeframe,
                            "op": rule.op,
                            "value": rule.value,
                            "pattern": rule.pattern,
                            "indicator": rule.indicator,
                            "params": rule.params or {},
                            **(meta or {}),
                        },
                    }
                    if not post_only:
                        io.append_jsonl(out, evt)
                    _LAST_FIRE[key] = now
                    # optional HTTP sink
                    if client and http_post:
                        try:
                            await client.post(http_post, json=evt)
                        except Exception as e:
                            log.info(f"[AlertV2] HTTP sink error → {e}")

                    # Colorized success line for crosses
                    if (rule.op or "").startswith("crosses"):
                        color = "green" if rule.op == "crosses_above" else "red"
                        log.info(
                            colorize(f"[AlertV2] 🔔 {sym} | {rname}", color, color_ok)
                        )
                    else:
                        log.info(f"[AlertV2] 🔔 {sym} | {rname}")
                else:
                    if debug and rule.op and rule.op.startswith("crosses"):
                        last2 = (meta or {}).get("last2")
                        level = (meta or {}).get("level")
                        msg = f"[Debug] {sym} {rname}: {rule.op} level={level} — last2={last2} (no trigger)"
                        log.info(colorize(msg, "yellow", color_ok))
            except Exception as e:
                log.error(
                    f"[AlertV2] eval failed for {rule.name or rule} on {sym} → {e}"
                )

    if once:
        await evaluate_once()
        if client:
            await client.aclose()
        return

    try:
        while True:
            await evaluate_once()
            await asyncio.sleep(max(1, tick_interval))
    finally:
        if client:
            await client.aclose()


# ------------------------------------------------------------
# 🧰 CLI
# ------------------------------------------------------------
def run_cli():
    p = argparse.ArgumentParser(
        description="AlertV2 — closed-market aware + settings-driven heuristics"
    )
    p.add_argument("--rules", default=str(alert_path_rules()), help="Rules YAML")
    p.add_argument("--out", default=str(alert_path_jsonl()), help="Alerts JSONL")
    p.add_argument("--tick-interval", type=int, default=1)
    p.add_argument("--once", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN)
    p.add_argument("--force-closed", action="store_true")
    p.add_argument("--backfill-days", type=int, default=0)
    p.add_argument("--no-intraday-backfill", action="store_true")
    p.add_argument("--daily-fallback", action="store_true")
    p.add_argument("--daily-bars", type=int, default=_DEFAULT_DAILY_FALLBACK_BARS)
    p.add_argument("--closed-eval-daily", action="store_true")
    p.add_argument(
        "--debug-values",
        type=int,
        default=0,
        help="Print last N indicator/price values",
    )
    p.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="ANSI color output",
    )
    p.add_argument(
        "--no-color", action="store_true", help="(deprecated) Disable ANSI colors"
    )
    p.add_argument("--http-post", type=str, default=None, help="POST fired alerts here")
    p.add_argument(
        "--http-timeout", type=float, default=3.0, help="HTTP timeout seconds"
    )
    p.add_argument(
        "--post-only",
        action="store_true",
        help="Send via HTTP POST only; do not write local JSONL",
    )

    args = p.parse_args()
    color_mode = "never" if args.no_color else args.color

    asyncio.run(
        run_daemon(
            rules_path=args.rules,
            out_path=args.out,
            tick_interval=args.tick_interval,
            once=args.once,
            debug=args.debug,
            cooldown=args.cooldown,
            force_closed=args.force_closed,
            backfill_days=args.backfill_days,
            no_intraday_backfill=args.no_intraday_backfill,
            daily_fallback=args.daily_fallback,
            daily_bars=args.daily_bars,
            closed_eval_daily=args.closed_eval_daily,
            debug_values=args.debug_values,
            color_mode=color_mode,
            http_post=args.http_post,
            http_timeout=args.http_timeout,
            post_only=args.post_only,
        )
    )


if __name__ == "__main__":
    run_cli()

#!/usr/bin/env python3
# ============================================================
# queen/daemons/alert_v2.py — v0.9
# Settings-driven sinks + --debug + cooldown + min-bars (policy)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Optional

import polars as pl
from queen.alerts.evaluator import eval_rule
from queen.alerts.rules import Rule, load_rules
from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers.logger import log
from queen.settings.indicator_policy import min_bars_for_indicator
from queen.settings.settings import alert_path_jsonl, alert_path_rules
from queen.technicals.patterns.core import required_lookback as pattern_lookback

# ------------------------------------------------------------
# 🔧 Cooldown state (in-proc)
# ------------------------------------------------------------
_LAST_FIRE: dict[tuple[str, str], float] = {}  # (symbol, rule_name) -> last_fire_ts
DEFAULT_COOLDOWN = 60  # seconds


# ------------------------------------------------------------
# 🕒 utils
# ------------------------------------------------------------
def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


# convert "5m" -> "intraday_5m", "1d" -> "daily", "1w" -> "weekly", "1mo" -> "monthly"
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
    return f"intraday_{tf}"  # safe default


# ------------------------------------------------------------
# 📏 min-bars policy (settings-first; indicator_policy + patterns)
# ------------------------------------------------------------
def _min_bars_for(rule: Rule) -> int:
    """Priority:
    1) rule.params.min_bars (explicit)
    2) indicator_policy.min_bars_for_indicator(name, params)  [for kind='indicator']
    3) pattern_lookback(pattern, timeframe_key) + cushion     [for kind='pattern']
    4) price: 5
    """
    # 1) explicit override from YAML
    if rule.params and "min_bars" in rule.params:
        try:
            return max(1, int(rule.params["min_bars"]))
        except Exception:
            pass

    kind = (rule.kind or "").lower()

    if kind == "indicator":
        ind = (rule.indicator or "").lower()
        try:
            return max(1, int(min_bars_for_indicator(ind, rule.params or {})))
        except Exception:
            # conservative fallback if policy lookup fails
            length = 14
            try:
                if "length" in (rule.params or {}):
                    length = max(1, int(rule.params["length"]))
            except Exception:
                pass
            return max(30, length * 3)

    if kind == "pattern":
        tf_key = _timeframe_key(rule.timeframe or "1m")
        try:
            lb = int(pattern_lookback(rule.pattern or "", tf_key))
        except Exception:
            lb = 40
        return max(10, lb + 5)

    return 5  # price rule


# ------------------------------------------------------------
# 📥 data fetch
# ------------------------------------------------------------
async def _fetch_df(symbol: str, timeframe: str, min_bars: int) -> pl.DataFrame:
    """Route timeframe to correct fetch mode, then tail(min_bars)."""
    tf = (timeframe or "1m").lower()
    if tf.endswith(("m", "h")):
        df = await fetch_unified(symbol, mode="intraday", interval=tf)
    elif tf in ("1d", "1w", "1mo"):
        df = await fetch_unified(symbol, mode="daily", interval=tf)
    else:
        df = await fetch_unified(symbol, mode="daily", interval="1d")

    if df.is_empty() or df.height <= min_bars:
        return df
    return df.tail(min_bars)


# ------------------------------------------------------------
# 🚨 main loop
# ------------------------------------------------------------
async def run_daemon(
    rules_path: Optional[str],
    out_path: Optional[str],
    tick_interval: int = 1,
    once: bool = False,
    debug: bool = False,
    cooldown: int = DEFAULT_COOLDOWN,
):
    rules = load_rules(rules_path)
    src = Path(rules_path) if rules_path else alert_path_rules()
    log.info(f"[AlertV2] Loaded {len(rules)} rule(s) from {src.resolve()}")

    out = Path(out_path) if out_path else alert_path_jsonl()
    out.parent.mkdir(parents=True, exist_ok=True)

    async def evaluate_once():
        for rule in rules:
            sym = rule.symbol
            tf = rule.timeframe or "1m"
            try:
                need = _min_bars_for(rule)
                df = await _fetch_df(sym, tf, min_bars=need)
                if df.is_empty():
                    if debug:
                        log.info(f"[Debug] {sym} {rule.name}: empty df for {tf}")
                    continue

                ok, meta = eval_rule(rule, df)
                rname = rule.name or rule.pattern or rule.indicator or "unnamed"

                if ok:
                    # cooldown gate
                    key = (sym, rname)
                    now = monotonic()
                    last = _LAST_FIRE.get(key, 0.0)
                    if now - last < max(0, cooldown):
                        if debug:
                            log.info(
                                f"[Debug] cooldown skip: {sym} | {rname} ({now-last:.1f}s since last)"
                            )
                        continue

                    evt = {
                        "ts": _utc_now_iso(),
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
                    with out.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(evt) + "\n")
                    _LAST_FIRE[key] = now
                    log.info(f"[AlertV2] 🔔 {sym} | {rname}")
                else:
                    if debug and rule.op and rule.op.startswith("crosses"):
                        last2 = (meta or {}).get("last2")
                        level = (meta or {}).get("level")
                        log.info(
                            f"[Debug] {sym} {rname}: {rule.op} level={level} — last2={last2} (no trigger)"
                        )

            except Exception as e:
                log.error(
                    f"[AlertV2] eval failed for {rule.name or rule} on {sym} → {e}"
                )

    if once:
        await evaluate_once()
        return

    while True:
        await evaluate_once()
        await asyncio.sleep(max(1, tick_interval))


# ------------------------------------------------------------
# 🧰 CLI
# ------------------------------------------------------------
def run_cli():
    p = argparse.ArgumentParser(description="AlertV2 — settings-driven sinks")
    p.add_argument("--rules", default=str(alert_path_rules()), help="Rules YAML")
    p.add_argument("--out", default=str(alert_path_jsonl()), help="Alerts JSONL")
    p.add_argument("--tick-interval", type=int, default=1)
    p.add_argument("--once", action="store_true")
    p.add_argument(
        "--debug", action="store_true", help="Explain why crosses_* did/didn't fire"
    )
    p.add_argument(
        "--cooldown",
        type=int,
        default=DEFAULT_COOLDOWN,
        help="Seconds to suppress repeats per (symbol,rule)",
    )
    args = p.parse_args()

    asyncio.run(
        run_daemon(
            args.rules,
            args.out,
            args.tick_interval,
            args.once,
            args.debug,
            args.cooldown,
        )
    )


if __name__ == "__main__":
    run_cli()

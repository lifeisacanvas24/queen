#!/usr/bin/env python3
# ============================================================
# queen/daemons/alert_v2.py — v0.7 (settings-driven sinks + --debug)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl
from queen.alerts.evaluator import eval_rule
from queen.alerts.rules import load_rules
from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers.logger import log
from queen.settings.settings import alert_path_jsonl, alert_path_rules


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


async def _fetch_df(symbol: str, timeframe: str) -> pl.DataFrame:
    """Route timeframe to correct fetch path. Supports 'Xm', 'Xh', '1d'."""
    tf = timeframe.lower()
    if tf.endswith(("m", "h")):
        return await fetch_unified(symbol, mode="intraday", interval=tf)
    if tf in ("1d", "1w", "1mo"):
        # daily/weekly/monthly through historical path; let fetcher parse unit
        return await fetch_unified(symbol, mode="daily", interval=tf)
    # default daily
    return await fetch_unified(symbol, mode="daily", interval="1d")


async def run_daemon(
    rules_path: Optional[str],
    out_path: Optional[str],
    tick_interval: int = 1,
    once: bool = False,
    debug: bool = False,
):
    rules = load_rules(rules_path)
    rules_src = Path(rules_path) if rules_path else alert_path_rules()
    log.info(f"[AlertV2] Loaded {len(rules)} rule(s) from {rules_src.resolve()}")

    out = Path(out_path) if out_path else alert_path_jsonl()
    out.parent.mkdir(parents=True, exist_ok=True)

    async def evaluate_once():
        for rule in rules:
            sym = rule.symbol
            timeframe = rule.timeframe or "1m"
            try:
                df = await _fetch_df(sym, timeframe)
                if df.is_empty():
                    if debug:
                        log.debug(
                            f"[AlertV2] {sym} {rule.name}: empty dataframe for {timeframe}"
                        )
                    continue

                ok, meta = eval_rule(rule, df)
                if ok:
                    evt = {
                        "ts": _utc_now_iso(),
                        "symbol": sym,
                        "rule": rule.name
                        or rule.pattern
                        or rule.indicator
                        or "unnamed",
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
                    log.info(f"[AlertV2] 🔔 {sym} | {evt['rule']}")
                else:
                    # Debug trace for crosses_* explaining why it didn’t fire
                    if debug and rule.op and rule.op.startswith("crosses"):
                        last2 = (meta or {}).get("last2")
                        level = (meta or {}).get("level")
                        if last2 is not None and level is not None:
                            log.info(
                                f"[Debug] {sym} {rule.name}: {rule.op} level={level} — last2={last2} (no trigger)"
                            )
                        else:
                            log.info(
                                f"[Debug] {sym} {rule.name}: {rule.op} (no trigger) meta={meta}"
                            )

            except Exception as e:
                log.error(f"[AlertV2] eval failed for {rule.name} on {sym} → {e}")

    if once:
        await evaluate_once()
        return

    while True:
        await evaluate_once()
        await asyncio.sleep(max(1, tick_interval))


def run_cli():
    p = argparse.ArgumentParser(description="AlertV2 — settings-driven sinks")
    p.add_argument(
        "--rules",
        default=str(alert_path_rules()),
        help="Rules YAML (default: settings)",
    )
    p.add_argument(
        "--out",
        default=str(alert_path_jsonl()),
        help="Alerts JSONL (default: settings)",
    )
    p.add_argument("--tick-interval", type=int, default=1)
    p.add_argument("--once", action="store_true")
    p.add_argument(
        "--debug",
        action="store_true",
        help="Print why crosses_* didn’t fire (last2 vs level)",
    )
    args = p.parse_args()

    asyncio.run(
        run_daemon(args.rules, args.out, args.tick_interval, args.once, args.debug)
    )


if __name__ == "__main__":
    run_cli()

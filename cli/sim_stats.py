#!/usr/bin/env python3
# queen/cli/sim_stats.py
"""Compute per-symbol sim statistics from a scan_signals Parquet.

Enhancements:
 - Counts forced-EOD closes as trades
 - Tracks skipped_adds per-row and aggregates per-trade and outside-trade
 - Prints a signal summary by sim_effective_decision (if available)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from queen.helpers.logger import log


def _to_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _load_scan_df(parquet_path: Path) -> pl.DataFrame:
    log.info(f"[SimStats] Loading parquet → {parquet_path}")
    df = pl.read_parquet(parquet_path)

    if "symbol" in df.columns:
        df = df.with_columns(pl.col("symbol").cast(pl.Utf8, strict=False))

    if "timestamp" in df.columns:
        df = df.sort(["symbol", "timestamp"])
    else:
        df = df.sort(["symbol"])
    return df


def _compute_symbol_stats(df_sym: pl.DataFrame) -> Dict[str, Any]:
    """Compute per-symbol totals: trades, win-rate, realized_pnl, max_drawdown,
    and total skipped_adds (all rows). Per-trade breakdown printed later.
    """
    rows = df_sym.to_dicts()

    trades = 0
    wins = 0
    last_side = "FLAT"
    last_realized = 0.0

    eq_peak = 0.0
    max_drawdown = 0.0

    total_skipped_adds = 0

    for row in rows:
        sim_side = (row.get("sim_side") or "FLAT").upper()
        realized = _to_float(row.get("sim_realized_pnl")) or 0.0
        total = _to_float(row.get("sim_total_pnl"))

        # drawdown tracking
        if total is not None:
            if total > eq_peak:
                eq_peak = total
            dd = total - eq_peak
            if dd < max_drawdown:
                max_drawdown = dd

        # accumulate skipped_adds from rows (per-row field should be integer)
        skipped_add = int(row.get("sim_skipped_add") or 0)
        total_skipped_adds += skipped_add

        # detect closed position LONG -> FLAT
        closed_position = last_side == "LONG" and sim_side == "FLAT"
        pnl_change = realized - last_realized
        sim_forced = bool(row.get("sim_forced_eod", False))

        if closed_position and (abs(pnl_change) > 1e-9 or sim_forced):
            trades += 1
            if pnl_change > 0:
                wins += 1

        last_side = sim_side
        last_realized = realized

    win_rate = (wins / trades * 100.0) if trades > 0 else 0.0

    symbol = rows[0].get("symbol") if rows else df_sym.select("symbol").to_series()[0]
    return {
        "symbol": symbol,
        "trades": trades,
        "win_rate": win_rate,
        "realized_pnl": last_realized,
        "max_drawdown": max_drawdown,
        "skipped_adds_total": total_skipped_adds,
    }


def _print_stats(df: pl.DataFrame) -> None:
    if df.is_empty():
        print("No rows in scan; nothing to summarise.")
        return

    # 1) Per-symbol stats
    stats: List[Dict[str, Any]] = []
    for sym, df_sym in df.group_by("symbol"):
        stats.append(_compute_symbol_stats(df_sym))

    out = pl.DataFrame(stats)
    print("\n=== Sim Stats (per symbol) ===")
    print(
        out.select(
            [
                "symbol",
                "trades",
                "win_rate",
                "realized_pnl",
                "max_drawdown",
                "skipped_adds_total",
            ]
        )
    )
    print("================================\n")

    # 2) Per-trade breakdown: group rows by sim_trade_id (non-null)
    trades_agg = None
    if "sim_trade_id" in df.columns:
        trades_df = df.filter(pl.col("sim_trade_id").is_not_null())
        if not trades_df.is_empty():
            # aggregate per trade
            # pnl_delta: realized_pnl at exit (last row of trade) minus realized_pnl just before entry (approximated)
            # We'll compute: final_realized - initial_realized (first realized in trade). For practical purposes,
            # since realized is cumulative, last - first will be per-trade realized delta.
            trades_agg = (
                trades_df.groupby(["symbol", "sim_trade_id"])
                .agg(
                    pl.first("sim_trade_id").alias("trade_id"),
                    (pl.col("sim_realized_pnl").last() - pl.col("sim_realized_pnl").first()).alias("pnl_delta"),
                    pl.sum("sim_skipped_add").alias("skipped_adds"),
                    pl.len("sim_trade_id").alias("rows"),
                )
                .sort(["symbol", "sim_trade_id"])
            )
            print("--- Trades per symbol (summary) ---")
            print(trades_agg)
            print()

    # 3) Compute skipped_adds_outside_trades per symbol:
    #    skipped_adds_outside_trades = total per-symbol skipped_adds - sum(skipped_adds per trade)
    if "skipped_adds_total" not in out.columns:
        # minor safety: rename our computed column
        out = out.rename({"skipped_adds_total": "skipped_adds_total"}) if "skipped_adds_total" in out.columns else out

    # build map of per-symbol sum of per-trade skipped_adds
    per_trade_skipped_map = {}
    if trades_agg is not None and not trades_agg.is_empty():
        trade_sums = trades_agg.groupby("symbol").agg(pl.sum("skipped_adds").alias("skipped_adds_in_trades"))
        for rec in trade_sums.to_dicts():
            per_trade_skipped_map[rec["symbol"]] = int(rec.get("skipped_adds_in_trades") or 0)

    # print per-symbol breakdown including outside-trades skipped adds
    print("--- Skipped adds breakdown (per symbol) ---")
    rows = []
    for rec in out.to_dicts():
        sym = rec["symbol"]
        total_skipped = int(rec.get("skipped_adds_total") or 0)
        in_trades = per_trade_skipped_map.get(sym, 0)
        outside = total_skipped - in_trades
        rows.append({"symbol": sym, "skipped_adds_total": total_skipped, "skipped_adds_in_trades": in_trades, "skipped_adds_outside_trades": outside})
    if rows:
        print(pl.DataFrame(rows).sort("symbol"))
    print()

    # 4) Signal summary by sim_effective_decision (if present)
    if "sim_effective_decision" in df.columns:
        try:
            summ = (
                df.groupby(["symbol", "sim_effective_decision"])
                .agg(pl.len().alias("len"))
                .sort(["symbol", "sim_effective_decision"])
            )
            print("=== Signal Summary (by sim_effective_decision) ===")
            print(summ)
            print()
        except Exception as e:
            log.exception(f"[SimStats] failed to produce sim_effective_decision summary: {e}")

    # 5) Optional: print debug decision stream sample
    print("\n--- Decision Stream Debug (sample) ---")
    wanted = [
        "timestamp",
        "decision",
        "sim_effective_decision",
        "sim_ignored_signal",
        "sim_trade_id",
        "sim_skipped_add",
        "sim_unit_size",
        "sim_pnl",
        "sim_total_pnl",
    ]
    cols = [c for c in wanted if c in df.columns]
    print(df.select(cols).head(50))
    print("================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute per-symbol simulation stats from a scan_signals Parquet."
    )
    parser.add_argument("--parquet", type=str, required=True)
    parser.add_argument("--symbol-filter", nargs="*", default=None)
    args = parser.parse_args()
    p = Path(args.parquet).expanduser().resolve()

    if not p.exists():
        print(f"[SimStats] Parquet not found: {p}")
        return

    df = _load_scan_df(p)

    # optional symbol filter
    if args.symbol_filter and "symbol" in df.columns:
        syms = [s.upper() for s in args.symbol_filter]
        df = df.filter(pl.col("symbol").str.to_uppercase().is_in(syms))

    if df.is_empty():
        print("[SimStats] No rows after symbol filter; nothing to summarise.")
        return

    _print_stats(df)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# ============================================================
# queen/cli/debug_decisions.py — v2.2
# ------------------------------------------------------------
# Two modes:
#
# 1) Demo mode (no --parquet):
#      Prints a synthetic debug flow to illustrate sim decisions.
#
# 2) Parquet mode (--parquet + --symbol):
#      Uses sim_stats._apply_date_filter + sim_stats._annotate_trades
#      to derive sim_trade_id, then prints row-by-row decision flow for
#      a given symbol and trade_id (or latest trade if trade_id omitted).
#
# New (v2.2):
#   • --show-guardrails:
#       For the selected trade, prints sim_guardrails (if present) per row
#       using queen.helpers.guardrail_debug.format_guardrails.
#
# Examples:
#
#   # Demo mode (no parquet)
#   python -m queen.cli.debug_decisions
#
#   # VOLTAMP, latest trade across full file
#   python -m queen.cli.debug_decisions \
#       --parquet /tmp/test.parquet \
#       --symbol VOLTAMP
#
#   # VOLTAMP, specific trade_id
#   python -m queen.cli.debug_decisions \
#       --parquet /tmp/test.parquet \
#       --symbol VOLTAMP \
#       --trade-id 1
#
#   # VOLTAMP, only trades within 2025-01-01 to 2025-01-02, with guardrails
#   python -m queen.cli.debug_decisions \
#       --parquet /tmp/test.parquet \
#       --symbol VOLTAMP \
#       --from 2025-01-01 \
#       --to   2025-01-02 \
#       --show-guardrails
# ============================================================

from __future__ import annotations

import argparse
from typing import Optional

import polars as pl

from queen.cli import (
    sim_stats as sim_mod,  # re-use _apply_date_filter + _annotate_trades
)
from queen.helpers.guardrail_debug import format_guardrails
from queen.helpers.io import read_parquet


# ----------------- demo mode -----------------
def _summarize_trade_geometry(rows: pl.DataFrame) -> None:
    """Given the per-row ladder for a single trade (single symbol + sim_trade_id),
    print a compact geometry summary: scale path, best/worst heat, and R stats.

    Important:
        • sim_pnl         → unrealized PnL for the *current* open position
        • sim_realized_pnl→ cumulative realized PnL across ALL trades

      For per-trade metrics, we must use:
        per_trade_realized = last(sim_realized_pnl) - first(sim_realized_pnl)

    """
    if rows.is_empty():
        print("[DebugDecisions] No rows to summarize.")
        return

    # Basic sanity: we expect one symbol/interval/trade_id
    symbol = rows["symbol"][0]
    interval = rows["interval"][0] if "interval" in rows.columns else "NA"

    # Position path
    qty = rows["sim_qty"]
    max_qty = float(qty.max())
    start_qty = float(qty[0])
    end_qty = float(qty[-1])

    # Count adds (increase in qty while still in position)
    adds = int(
        (
            (qty.diff() > 0)
            & (qty.shift(1).fill_null(0) > 0)  # we’re already in the trade
        ).sum()
    )

    # Entry / SL (best-effort)
    entry_price = rows["entry"].drop_nulls().drop_nans().first() if "entry" in rows.columns else None
    sl_price = rows["sl"].drop_nulls().drop_nans().first() if "sl" in rows.columns else None

    # Per-trade realized pnl: use delta of sim_realized_pnl within this trade
    if "sim_realized_pnl" in rows.columns:
        realized_start = float(rows["sim_realized_pnl"][0])
        realized_exit = float(rows["sim_realized_pnl"][-1])
        realized_trade = realized_exit - realized_start
    else:
        realized_start = 0.0
        realized_exit = 0.0
        realized_trade = 0.0

    # Open pnl path during trade (unrealized)
    pnl_series = rows["sim_pnl"] if "sim_pnl" in rows.columns else None
    best_open_pnl = float(pnl_series.max()) if pnl_series is not None else 0.0
    worst_open_pnl = float(pnl_series.min()) if pnl_series is not None else 0.0

    # R-multiples if we can compute risk
    best_R = None
    exit_R = None
    dd_R = None

    if entry_price is not None and sl_price is not None and max_qty > 0:
        risk_per_unit = abs(entry_price - sl_price)
        if risk_per_unit > 0:
            total_risk = risk_per_unit * max_qty
            best_R = best_open_pnl / total_risk
            exit_R = realized_trade / total_risk
            dd_R = worst_open_pnl / total_risk

    print("\n--- Trade Geometry Summary ---")
    print(f"Symbol / Interval : {symbol} / {interval}")
    print(f"Size path         : start={start_qty}, max={max_qty}, end={end_qty}, adds={adds}")
    print(f"Best open PnL     : {best_open_pnl:.2f}")
    print(f"Worst open PnL    : {worst_open_pnl:.2f}")
    print(f"Realized at exit  : {realized_trade:.2f}  "
          f"(cumulative {realized_exit:.2f}, start {realized_start:.2f})")

    if best_R is not None and exit_R is not None:
        heat_from_peak = best_R - exit_R
        print(f"Best open R       : {best_R:.2f}R")
        print(f"Exit R (per trade): {exit_R:.2f}R")
        print(f"Heat from peak    : {heat_from_peak:.2f}R given back")
        if dd_R is not None:
            print(f"Max intra-trade DD: {dd_R:.2f}R (open)")
    else:
        print("R stats           : (entry/SL/max_qty not sufficient to compute R)")

    print("------------------------------\n")

def _demo_flow() -> None:
    """Original demo debug flow (no parquet)."""
    print("\n=== Debug Decision Flow (DEMO) ===")
    rows = [
        # ts,        dec,        cmp,   side,   qty,   avg,   pnl,  realized, total
        ("2025-01-01T09:30:00", "BUY",        100.0, "LONG",  1, 100.0,   0.0,    0.0,   0.0),
        ("2025-01-01T09:40:00", "HOLD",       102.0, "LONG",  1, 100.0,   2.0,    0.0,   2.0),
        ("2025-01-01T09:50:00", "AVOID",      104.0, "LONG",  1, 100.0,   4.0,    0.0,   4.0),
        ("2025-01-01T10:00:00", "ADD",        103.0, "LONG",  2, 101.5,   3.0,    0.0,   3.0),
        ("2025-01-01T10:10:00", "EXIT",       106.0, "FLAT",  0,   0.0,   0.0,    9.0,   9.0),
        ("2025-01-01T10:20:00", "SELL",       105.0, "SHORT", 1, 105.0,   0.0,    9.0,   9.0),
        ("2025-01-01T10:30:00", "HOLD",       103.0, "SHORT", 1, 105.0,   2.0,    9.0,  11.0),
        ("2025-01-01T10:40:00", "AVOID",      102.0, "SHORT", 1, 105.0,   3.0,    9.0,  12.0),
        ("2025-01-01T10:50:00", "EXIT_SHORT", 104.0, "FLAT",  0,   0.0,   0.0,   10.0,  10.0),
    ]
    for ts, dec, cmp_, side, qty, avg, pnl, realized, total in rows:
        print(
            f"{ts}  dec={dec:>10}  cmp={cmp_:7.2f}  "
            f"sim_side={side:>5}  qty={qty:3d}  avg={avg:7.2f}  "
            f"pnl={pnl:7.2f}  realized={realized:7.2f}  total={total:7.2f}"
        )
    print("=================================\n")


# ----------------- parquet mode helpers -----------------


def _debug_from_parquet(
    parquet_path: str,
    symbol: str,
    trade_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    show_guardrails: bool = False,
) -> None:
    """Print row-by-row decision flow for a single trade from a parquet.

    Steps:
      • Load via queen.helpers.io.read_parquet
      • Apply date filter via sim_stats._apply_date_filter (if from/to given)
      • Annotate trades via sim_stats._annotate_trades
      • If trade_id missing → choose latest trade_id for that symbol in the filtered window
      • Print a compact ladder view for that trade
      • Optionally print per-row sim_guardrails (if present)
    """
    df = read_parquet(parquet_path)

    if df.is_empty():
        print(f"[DebugDecisions] No data in parquet: {parquet_path}")
        return

    if "sim_side" not in df.columns:
        print(
            "[DebugDecisions] parquet is missing 'sim_side' column. "
            "Ensure it is produced with simulator fields (sim_*)"
        )
        return

    # Optional date window (DRY: re-use sim_stats helper)
    if date_from or date_to:
        df = sim_mod._apply_date_filter(df, date_from, date_to)  # type: ignore[attr-defined]
        if df.is_empty():
            print(
                f"[DebugDecisions] No rows after date filter "
                f"from={date_from!r} to={date_to!r} in {parquet_path}"
            )
            return

    # Annotate with sim_trade_id using the same logic as sim_stats
    df = sim_mod._annotate_trades(df)  # type: ignore[attr-defined]

    # Filter by symbol first
    sym_df = df.filter(pl.col("symbol") == symbol)
    if sym_df.is_empty():
        print(f"[DebugDecisions] No rows found for symbol={symbol!r} in {parquet_path}")
        return

    # If trade_id is not provided, pick the latest trade for that symbol
    if trade_id is None:
        tid_series = sym_df["sim_trade_id"].drop_nulls()
        if tid_series.is_empty():
            print(
                f"[DebugDecisions] No closed trades (sim_trade_id) found "
                f"for symbol={symbol!r} in {parquet_path}"
            )
            return
        trade_id = int(tid_series.max())
        msg = (
            f"[DebugDecisions] Using latest sim_trade_id={trade_id} "
            f"for symbol={symbol!r}"
        )
        if date_from or date_to:
            msg += f" within window from={date_from!r}, to={date_to!r}"
        print(msg)

    # Now slice ONLY that trade
    rows = (
        df.filter(
            (pl.col("symbol") == symbol)
            & (pl.col("sim_trade_id") == trade_id)
        )
        .sort("timestamp")
    )

    if rows.is_empty():
        print(
            f"[DebugDecisions] No rows found for symbol={symbol!r}, "
            f"sim_trade_id={trade_id} in {parquet_path}"
        )
        return

    # Select a nice debug view
    cols = [
        "timestamp",
        "symbol",
        "interval",
        "decision",
        "cmp",
        "entry",
        "sl",
        "sim_side",
        "sim_qty",
        "sim_pnl",
        "sim_realized_pnl",
        "sim_total_pnl",
    ]
    cols_present = [c for c in cols if c in rows.columns]
    view = rows.select(cols_present)

    print(
        f"\n=== Debug Decision Flow (PARQUET) ===\n"
        f"symbol={symbol}, trade_id={trade_id}, parquet={parquet_path}\n"
    )
    print(view)
    _summarize_trade_geometry(view)

    # -------------------------
    # Optional: per-row guardrails
    # -------------------------
    if show_guardrails:
        if "sim_guardrails" not in rows.columns:
            print("\n[DebugDecisions] sim_guardrails column not found; "
                  "no guardrail reasons recorded in this parquet.\n")
        else:
            guard_cols = ["timestamp", "decision", "sim_guardrails"]
            guard_cols = [c for c in guard_cols if c in rows.columns]
            if guard_cols:
                print("\n=== Guardrails (per row) ===")
                for rec in rows.select(guard_cols).to_dicts():
                    reasons = rec.get("sim_guardrails")
                    formatted = format_guardrails(reasons)
                    if not formatted:
                        continue
                    ts = rec.get("timestamp")
                    dec = rec.get("decision", "")
                    print(f"{ts}  dec={dec:>10}  {formatted}")
                print("=====================================\n")

    print("=====================================\n")


# ----------------- CLI entrypoint -----------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Debug decision flow.\n\n"
            "• Without --parquet → show demo flow\n"
            "• With --parquet + --symbol → debug one real trade\n"
            "  (optionally narrowed by date window and trade_id,\n"
            "   and optionally printing per-row sim_guardrails)."
        )
    )
    parser.add_argument(
        "--parquet",
        type=str,
        default=None,
        help="Optional: path to scan/replay parquet with sim_* fields.",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Symbol to debug (required if --parquet is used).",
    )
    parser.add_argument(
        "--trade-id",
        type=int,
        default=None,
        help="Optional sim_trade_id. If omitted, latest trade for that symbol is used.",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        type=str,
        default=None,
        help="Optional start date (YYYY-MM-DD) for filtering rows.",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=str,
        default=None,
        help="Optional end date (YYYY-MM-DD) for filtering rows.",
    )
    parser.add_argument(
        "--show-guardrails",
        action="store_true",
        help=(
            "If set, print sim_guardrails reasons per bar "
            "for the selected trade (if the column is present)."
        ),
    )

    args = parser.parse_args()

    # Demo mode
    if not args.parquet:
        _demo_flow()
        return

    # Parquet mode requires symbol
    if not args.symbol:
        print("[DebugDecisions] When using --parquet, --symbol is required.")
        return

    _debug_from_parquet(
        parquet_path=args.parquet,
        symbol=args.symbol,
        trade_id=args.trade_id,
        date_from=args.date_from,
        date_to=args.date_to,
        show_guardrails=args.show_guardrails,
    )


if __name__ == "__main__":
    main()

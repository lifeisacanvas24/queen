#!/usr/bin/env python3
# ============================================================
# queen/cli/sim_stats.py — v2.2
# ------------------------------------------------------------
# Simulation stats + trade journal for scan_signals/replay parquet.
#
# Works with:
#   • New simulator wiring (sim_* fields only)
#   • WITHOUT requiring sim_trade_id in parquet
#
# How it works:
#   • Reads scan_signals/replay parquet via queen.helpers.io.read_parquet
#   • Optionally filters by date window: --from / --to (YYYY-MM-DD)
#   • Derives trade segments from sim_side transitions:
#         FLAT → LONG/SHORT → FLAT == one trade
#   • Computes:
#         - Overall stats (PnL, R)
#         - Per-symbol+interval stats
#         - Per-symbol+side stats (LONG vs SHORT)
#         - Per-trade journal table
#
# Columns USED if present:
#   • symbol (str)
#   • interval (str)            [optional; defaults to "NA"]
#   • timestamp (str/datetime)  [optional; for date filter + journal display]
#   • decision (str)            [optional; journal decoration]
#   • cmp (float)               [optional; fallback for entry/exit]
#   • entry (float)             [optional; preferred for R]
#   • sl (float)                [optional; preferred for R]
#   • sim_side (str: FLAT/LONG/SHORT)
#   • sim_qty (float)
#   • sim_pnl (float)
#   • sim_realized_pnl (float)
#   • sim_total_pnl (float)
# ============================================================

from __future__ import annotations

import argparse
from datetime import date, datetime, time
from typing import Dict, List, Optional

import polars as pl

from queen.helpers.io import read_parquet  # ✅ DRY IO

# ----------------- small helpers -----------------


def _ensure_required(df: pl.DataFrame) -> None:
    """Ensure core sim columns exist. Be lenient on optional fields."""
    required = ["symbol", "sim_side", "sim_qty", "sim_realized_pnl", "sim_pnl"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            "[SimStats] Missing required columns in DF: "
            f"{missing}. Ensure scan_signals/replay parquet is produced "
            "with simulator fields (sim_*)."
        )


def _with_row_index(df: pl.DataFrame) -> pl.DataFrame:
    """Attach a stable row index for ordering when timestamp is absent."""
    if "_row_idx" in df.columns:
        return df
    return df.with_columns(pl.arange(0, pl.len()).alias("_row_idx"))


def _ensure_timestamp(df: pl.DataFrame) -> pl.DataFrame:
    """Guarantee a 'timestamp' column exists for sorting/trade grouping.

    Priority:
      1) Use existing 'timestamp' as-is
      2) If 'ts' exists, rename to 'timestamp'
      3) Else synthesize a monotonic index as 'timestamp'
    """
    cols = set(df.columns)

    # Case 1: ideal, already present
    if "timestamp" in cols:
        return df

    # Case 2: some older tools used 'ts'
    if "ts" in cols:
        return df.rename({"ts": "timestamp"})

    # Case 3: last resort — synthetic index timestamp
    return df.with_columns(pl.int_range(0, df.height).alias("timestamp"))


def _sort_for_sim(df: pl.DataFrame) -> pl.DataFrame:
    """Sort by symbol, interval, then timestamp or row index."""
    df = _with_row_index(df)

    sort_keys: List[str] = ["symbol"]
    if "interval" in df.columns:
        sort_keys.append("interval")
    if "timestamp" in df.columns:
        sort_keys.append("timestamp")
    sort_keys.append("_row_idx")

    return df.sort(sort_keys)


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _apply_date_filter(
    df: pl.DataFrame,
    date_from: Optional[str],
    date_to: Optional[str],
) -> pl.DataFrame:
    """Filter rows by calendar date using the 'timestamp' column.

    - date_from / date_to are strings 'YYYY-MM-DD'
    - If timestamp missing or non-datetime-like → returns df unchanged.
    """
    if not date_from and not date_to:
        return df

    df = _ensure_timestamp(df)

    if "timestamp" not in df.columns:
        return df

    ts_col = df["timestamp"]

    # Normalize to a temporary datetime column
    if ts_col.dtype == pl.Utf8:
        df = df.with_columns(
            pl.col("timestamp")
            .str.strptime(pl.Datetime, strict=False, exact=False)
            .alias("_ts_dt")
        )
    elif ts_col.dtype == pl.Datetime:
        df = df.with_columns(pl.col("timestamp").alias("_ts_dt"))
    else:
        # Synthetic int index or something non-date-like; skip filtering
        return df

    start_d = _parse_date(date_from)
    end_d = _parse_date(date_to)

    cond = pl.lit(True)
    if start_d:
        start_dt = datetime.combine(start_d, time.min)
        cond = cond & (pl.col("_ts_dt") >= start_dt)
    if end_d:
        end_dt = datetime.combine(end_d, time.max)
        cond = cond & (pl.col("_ts_dt") <= end_dt)

    df = df.filter(cond).drop("_ts_dt")
    return df


# ----------------- trade annotation -----------------


def _annotate_trades(df: pl.DataFrame) -> pl.DataFrame:
    """Derive sim_trade_id purely from sim_side transitions.

    Logic:
      • prev_side = sim_side.shift(1)
      • trade_start = (prev_side == FLAT) & (sim_side != FLAT)
      • trade_end   = (prev_side != FLAT) & (sim_side == FLAT)
      • trade_seq   = cumulative sum of trade_start per (symbol, interval)
      • sim_trade_id:
            - == trade_seq while position is OPEN (sim_side != FLAT)
            - == trade_seq on the EXIT BAR (trade_end)
            - NULL elsewhere

    This way, the EXIT bar (where sim_realized_pnl jumps) is included
    in the same trade group, so PnL is correctly attributed.
    """
    df = _ensure_timestamp(df)
    df = _sort_for_sim(df)

    has_interval = "interval" in df.columns
    partition_keys = ["symbol"] + (["interval"] if has_interval else [])

    df = df.with_columns(
        pl.col("sim_side").shift(1).fill_null("FLAT").alias("_prev_side")
    )

    df = df.with_columns(
        (
            (pl.col("_prev_side") == "FLAT")
            & (pl.col("sim_side") != "FLAT")
        )
        .cast(pl.Int64)
        .alias("_trade_start"),
        (
            (pl.col("_prev_side") != "FLAT")
            & (pl.col("sim_side") == "FLAT")
        ).alias("_trade_end"),
    )

    df = df.with_columns(
        pl.col("_trade_start")
        .cum_sum()
        .over(partition_keys)
        .alias("_trade_seq")
    )

    df = df.with_columns(
        pl.when(
            (pl.col("sim_side") != "FLAT") | pl.col("_trade_end")
        )
        .then(pl.col("_trade_seq"))
        .otherwise(None)
        .alias("sim_trade_id")
    )

    # Realized delta per row (for per-trade PnL)
    df = df.with_columns(
        pl.col("sim_realized_pnl")
        .shift(1)
        .fill_null(0.0)
        .alias("_prev_realized")
    ).with_columns(
        (pl.col("sim_realized_pnl") - pl.col("_prev_realized")).alias(
            "sim_realized_delta"
        )
    )

    return df


# ----------------- trade extraction -----------------


def _extract_trades(df: pl.DataFrame) -> pl.DataFrame:
    """Return a per-trade DataFrame.

    Columns:
      • symbol
      • interval
      • trade_id
      • side
      • entry_ts / exit_ts (if timestamp present)
      • entry_price (best-effort)
      • exit_price (best-effort)
      • pnl_abs
      • max_upl
      • max_dd
      • R        (using entry, SL and max position size)
    """
    if "sim_trade_id" not in df.columns:
        df = _annotate_trades(df)

    trades_df = df.filter(pl.col("sim_trade_id").is_not_null())
    if trades_df.is_empty():
        return pl.DataFrame(
            {
                "symbol": [],
                "interval": [],
                "trade_id": [],
                "side": [],
                "entry_ts": [],
                "exit_ts": [],
                "entry_price": [],
                "exit_price": [],
                "pnl_abs": [],
                "max_upl": [],
                "max_dd": [],
                "R": [],
            }
        )

    # Ensure we have interval
    if "interval" not in trades_df.columns:
        trades_df = trades_df.with_columns(pl.lit("NA").alias("interval"))

    group_keys = ["symbol", "interval", "sim_trade_id"]

    # Timestamps (optional)
    if "timestamp" in trades_df.columns:
        entry_ts_expr = pl.col("timestamp").first().alias("entry_ts")
        exit_ts_expr = pl.col("timestamp").last().alias("exit_ts")
    else:
        entry_ts_expr = pl.lit(None).alias("entry_ts")
        exit_ts_expr = pl.lit(None).alias("exit_ts")

    # Entry / exit price
    has_entry = "entry" in trades_df.columns
    if has_entry:
        entry_px_expr = pl.col("entry").drop_nans().drop_nulls().first().alias(
            "entry_price"
        )
    else:
        entry_px_expr = pl.col("cmp").drop_nans().drop_nulls().first().alias(
            "entry_price"
        )

    exit_px_expr = pl.col("cmp").drop_nans().drop_nulls().last().alias("exit_price")

    # SL + max position size for R
    has_sl = "sl" in trades_df.columns
    if has_sl:
        sl_expr = pl.col("sl").drop_nans().drop_nulls().first().alias("_sl")
    else:
        sl_expr = pl.lit(None).alias("_sl")

    trades = (
        trades_df.group_by(group_keys)
        .agg(
            pl.col("sim_side").first().alias("side"),
            entry_ts_expr,
            exit_ts_expr,
            entry_px_expr,
            exit_px_expr,
            pl.col("sim_realized_delta").sum().alias("pnl_abs"),
            pl.col("sim_pnl").max().alias("max_upl"),
            pl.col("sim_pnl").min().alias("max_dd"),
            sl_expr,
            pl.col("sim_qty").max().alias("_max_qty"),
        )
        .sort(group_keys)
    )

    # Size-aware R multiple:
    #   risk_per_unit = |entry - SL|
    #   risk_total    = risk_per_unit * max_qty
    #   R             = pnl_abs / risk_total
    trades = trades.with_columns(
        pl.when(
            (pl.col("_sl").is_not_null())
            & (pl.col("entry_price").is_not_null())
            & (pl.col("_max_qty") > 0)
            & ((pl.col("entry_price") - pl.col("_sl")).abs() > 0)
        )
        .then(
            pl.col("pnl_abs")
            / (
                (pl.col("entry_price") - pl.col("_sl")).abs()
                * pl.col("_max_qty")
            )
        )
        .otherwise(None)
        .alias("R")
    ).drop(["_sl", "_max_qty"])

    trades = trades.rename({"sim_trade_id": "trade_id"})
    return trades


# ----------------- stats computation -----------------


def _compute_overall_stats(trades: pl.DataFrame) -> Dict[str, float]:
    if trades.is_empty():
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "gross_pnl": 0.0,
            "avg_pnl": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
            "avg_R": 0.0,
        }

    pnl = trades["pnl_abs"]
    wins_mask = pnl > 0
    losses_mask = pnl < 0

    trades_count = trades.height
    wins = int(wins_mask.sum())
    losses = int(losses_mask.sum())
    gross_pnl = float(pnl.sum())
    avg_pnl = float(pnl.mean()) if trades_count > 0 else 0.0
    max_win = float(pnl.filter(wins_mask).max() or 0.0)
    max_loss = float(pnl.filter(losses_mask).min() or 0.0)

    if "R" in trades.columns:
        valid_R = trades["R"].drop_nulls()
        avg_R = float(valid_R.mean()) if valid_R.len() > 0 else 0.0
    else:
        avg_R = 0.0

    return {
        "trades": trades_count,
        "wins": wins,
        "losses": losses,
        "gross_pnl": gross_pnl,
        "avg_pnl": avg_pnl,
        "max_win": max_win,
        "max_loss": max_loss,
        "avg_R": avg_R,
    }


def _compute_symbol_stats(trades: pl.DataFrame) -> pl.DataFrame:
    if trades.is_empty():
        return pl.DataFrame()

    return (
        trades.group_by(["symbol", "interval"])
        .agg(
            pl.len().alias("trades"),
            pl.col("pnl_abs").filter(pl.col("pnl_abs") > 0).len().alias("wins"),
            pl.col("pnl_abs").filter(pl.col("pnl_abs") < 0).len().alias("losses"),
            pl.col("pnl_abs").sum().alias("gross_pnl"),
            pl.col("pnl_abs").mean().alias("avg_pnl"),
            pl.col("pnl_abs").max().alias("max_win"),
            pl.col("pnl_abs").min().alias("max_loss"),
            pl.col("R").drop_nulls().mean().alias("avg_R"),
            pl.col("R").drop_nulls().max().alias("max_R"),
            pl.col("R").drop_nulls().min().alias("min_R"),
            pl.col("max_dd").min().alias("max_drawdown"),
        )
        .sort(["symbol", "interval"])
    )


def _compute_symbol_side_stats(trades: pl.DataFrame) -> pl.DataFrame:
    if trades.is_empty():
        return pl.DataFrame()

    return (
        trades.group_by(["symbol", "interval", "side"])
        .agg(
            pl.len().alias("trades"),
            pl.col("pnl_abs").filter(pl.col("pnl_abs") > 0).len().alias("wins"),
            pl.col("pnl_abs").filter(pl.col("pnl_abs") < 0).len().alias("losses"),
            pl.col("pnl_abs").sum().alias("gross_pnl"),
            pl.col("pnl_abs").mean().alias("avg_pnl"),
            pl.col("pnl_abs").max().alias("max_win"),
            pl.col("pnl_abs").min().alias("max_loss"),
            pl.col("R").drop_nulls().mean().alias("avg_R"),
            pl.col("R").drop_nulls().max().alias("max_R"),
            pl.col("R").drop_nulls().min().alias("min_R"),
        )
        .sort(["symbol", "interval", "side"])
    )


# ----------------- pretty printers -----------------


def _print_overall(overall: Dict[str, float]) -> None:
    print("\n=== Overall Simulation Stats ===")
    print(f"Total closed trades : {overall['trades']}")
    print(f"Gross realized PnL  : {round(overall['gross_pnl'], 2)}")
    print(f"Avg PnL / trade     : {round(overall['avg_pnl'], 2)}")
    print(f"Max win             : {round(overall['max_win'], 2)}")
    print(f"Max loss            : {round(overall['max_loss'], 2)}")
    print(f"Avg R / trade       : {round(overall['avg_R'], 2)}")
    print("================================")


def _print_table(title: str, df: pl.DataFrame) -> None:
    print(f"\n=== {title} ===")
    if df.is_empty():
        print("(no trades)")
        print("================================")
        return
    print(df)
    print("================================")


def _print_per_symbol(per_symbol: pl.DataFrame) -> None:
    _print_table("Per-Symbol Trade Stats", per_symbol)


def _print_per_symbol_side(per_symbol_side: pl.DataFrame) -> None:
    _print_table("Per-Symbol+Side Trade Stats", per_symbol_side)


def _print_trade_journal(trades: pl.DataFrame) -> None:
    if trades.is_empty():
        _print_table("Trade Journal (per trade)", trades)
        return

    cols = ["symbol", "interval", "trade_id", "side"]
    if "entry_ts" in trades.columns:
        cols.append("entry_ts")
    if "exit_ts" in trades.columns:
        cols.append("exit_ts")
    cols += ["entry_price", "exit_price", "pnl_abs", "R", "max_upl", "max_dd"]

    journal = trades.select([c for c in cols if c in trades.columns])
    _print_table("Trade Journal (per trade)", journal)


# ----------------- main orchestrator -----------------


def _run_stats(
    df: pl.DataFrame,
    side_filter: Optional[str] = None,
    symbol_filter: Optional[str] = None,
) -> None:
    """Compute and print all stats."""
    if df.is_empty():
        print("[SimStats] No data in parquet (empty DataFrame). Nothing to do.")
        return

    _ensure_required(df)

    # Annotate + extract trades
    df = _annotate_trades(df)
    trades = _extract_trades(df)

    # Filter by side if requested
    if side_filter in ("LONG", "SHORT"):
        trades = trades.filter(pl.col("side") == side_filter)

    # Filter by symbol if requested
    if symbol_filter:
        trades = trades.filter(pl.col("symbol") == symbol_filter)

    if trades.is_empty():
        print("No closed trades found for the given filters.")
        return

    overall = _compute_overall_stats(trades)
    per_symbol = _compute_symbol_stats(trades)
    per_symbol_side = _compute_symbol_side_stats(trades)

    _print_overall(overall)
    _print_per_symbol(per_symbol)
    _print_per_symbol_side(per_symbol_side)
    _print_trade_journal(trades)


# ----------------- CLI entrypoint -----------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute simulation stats from a scan_signals/replay parquet."
    )
    parser.add_argument(
        "--parquet",
        required=True,
        help="Path to parquet file produced by scan_signals or replay.",
    )
    parser.add_argument(
        "--side",
        type=str,
        choices=["LONG", "SHORT"],
        default=None,
        help="Optional filter: only include trades on this side (LONG or SHORT).",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Optional filter: only include trades for this symbol (e.g. VOLTAMP).",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        type=str,
        default=None,
        help="Optional date filter: start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=str,
        default=None,
        help="Optional date filter: end date (YYYY-MM-DD).",
    )

    args = parser.parse_args()

    df = read_parquet(args.parquet)
    df = _apply_date_filter(df, args.date_from, args.date_to)

    _run_stats(
        df,
        side_filter=args.side,
        symbol_filter=args.symbol,
    )


if __name__ == "__main__":
    main()

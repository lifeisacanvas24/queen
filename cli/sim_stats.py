# queen/cli/sim_stats.py
# Compute per-symbol sim statistics from a scan_signals Parquet and
# include trade-level breakdown. Uses sim_effective_decision for signal summary.

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    # Normalise symbol column to string (avoid list[str] weirdness)
    if "symbol" in df.columns:
        df = df.with_columns(pl.col("symbol").cast(pl.Utf8, strict=False))

    # Timestamp-based ordering if available
    if "timestamp" in df.columns:
        df = df.sort(["symbol", "timestamp"])
    else:
        df = df.sort(["symbol"])

    return df


def _compute_symbol_stats(df_sym: pl.DataFrame) -> Dict[str, Any]:
    """Compute trades, win-rate, realized PnL, max drawdown for one symbol.
    Also produce trade-level breakdown (list of trades).
    """
    rows = df_sym.to_dicts()

    trades = 0
    wins = 0
    last_side = "FLAT"
    last_realized = 0.0

    eq_peak = 0.0
    max_drawdown = 0.0

    # trade-level bookkeeping
    trades_detail: List[Dict[str, Any]] = []
    current_trade: Optional[Dict[str, Any]] = None

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

        # Trade open detection: row flagged sim_trade_open True (entry)
        if row.get("sim_trade_open", False):
            # start a new trade record
            current_trade = {
                "trade_id": row.get("sim_trade_id"),
                "entry_row_index": None,
                "exit_row_index": None,
                "entry_realized": float(row.get("sim_realized_pnl") or 0.0),
                "exit_realized": None,
                "skipped_adds": int(row.get("sim_trade_skipped_adds") or 0),
                "rows": [],
            }

        # If in a trade, append row context for later
        if current_trade is not None:
            current_trade["rows"].append(row)

        # Trade close detection: row flagged sim_trade_close True or LONG->FLAT transition
        if row.get("sim_trade_close", False):
            # finalize current trade
            if current_trade is None:
                # no explicit open row seen, create minimal trade record
                current_trade = {
                    "trade_id": row.get("sim_trade_id"),
                    "entry_row_index": None,
                    "exit_row_index": None,
                    "entry_realized": 0.0,
                    "exit_realized": float(row.get("sim_realized_pnl") or 0.0),
                    "skipped_adds": int(row.get("sim_trade_skipped_adds") or 0),
                    "rows": [row],
                }

            # populate exit realized
            current_trade["exit_realized"] = float(row.get("sim_realized_pnl") or 0.0)

            # compute pnl for trade = exit_realized - entry_realized
            try:
                pnl = current_trade["exit_realized"] - current_trade["entry_realized"]
            except Exception:
                pnl = 0.0

            current_trade["pnl"] = pnl
            trades_detail.append(current_trade)

            # increment trade counters (counts a trade even if forced EOD)
            trades += 1
            if pnl > 0:
                wins += 1

            # reset
            current_trade = None

        # Fallback LONG→FLAT detection: if last_side was LONG and now FLAT and no explicit flags
        if last_side == "LONG" and sim_side == "FLAT" and not row.get("sim_trade_close", False):
            # treat as close — count if simulated realized changed or forced flag present
            pnl_change = realized - last_realized
            sim_forced = bool(row.get("sim_forced_eod", False))
            if abs(pnl_change) > 1e-9 or sim_forced:
                # create a minimal trade record if not present
                # Use sim_trade_id if available
                t = {
                    "trade_id": row.get("sim_trade_id") or f"anon_{trades+1}",
                    "entry_row_index": None,
                    "exit_row_index": None,
                    "entry_realized": 0.0,
                    "exit_realized": float(realized),
                    "skipped_adds": int(row.get("sim_trade_skipped_adds") or 0),
                    "pnl": realized - 0.0,
                }
                trades_detail.append(t)
                trades += 1
                if t["pnl"] > 0:
                    wins += 1

        last_side = sim_side
        last_realized = realized

    win_rate = 0.0
    if trades > 0:
        win_rate = (wins / trades) * 100.0

    symbol = rows[0].get("symbol") if rows else df_sym.select("symbol").to_series()[0]

    # compute aggregate skipped_adds across trades for convenience
    total_skipped_adds = sum(int(t.get("skipped_adds", 0)) for t in trades_detail)

    # Provide lightweight trade summary list (trade_id, pnl, skipped_adds)
    trade_summary = [
        {
            "trade_id": t.get("trade_id"),
            "pnl": float(t.get("pnl") or 0.0),
            "skipped_adds": int(t.get("skipped_adds", 0)),
        }
        for t in trades_detail
    ]

    return {
        "symbol": symbol,
        "trades": trades,
        "win_rate": win_rate,
        "realized_pnl": last_realized,
        "max_drawdown": max_drawdown,
        "skipped_adds": total_skipped_adds,
        "trade_summary": trade_summary,
    }


def _print_stats(df: pl.DataFrame) -> None:
    if df.is_empty():
        print("No rows in scan; nothing to summarise.")
        return

    # Group by symbol and compute stats in Python (stateful)
    stats: List[Dict[str, Any]] = []
    for sym, df_sym in df.group_by("symbol"):
        stats.append(_compute_symbol_stats(df_sym))

    out_rows = []
    for s in stats:
        # flatten trade_summary count into a printable row
        out_rows.append(
            {
                "symbol": s["symbol"],
                "trades": s["trades"],
                "win_rate": s["win_rate"],
                "realized_pnl": s["realized_pnl"],
                "max_drawdown": s["max_drawdown"],
                "skipped_adds": s.get("skipped_adds", 0),
            }
        )

    out = pl.DataFrame(out_rows)

    # Pretty print summary table
    print("\n=== Sim Stats (per symbol) ===")
    print(
        out.select(
            [
                "symbol",
                "trades",
                "win_rate",
                "realized_pnl",
                "max_drawdown",
                "skipped_adds",
            ]
        )
    )
    print("================================\n")

    # Print trade-level breakdown for each symbol
    for s in stats:
        print(f"--- Trades for {s['symbol']} (count={s['trades']}) ---")
        if not s["trade_summary"]:
            print("  (no trades)")
            continue
        for t in s["trade_summary"]:
            print(
                f"  {t['trade_id']}: pnl={t['pnl']:.2f} skipped_adds={t['skipped_adds']}"
            )
        print()

    # Additionally print a quick signal summary grouped by sim_effective_decision
    # if column exists
    if "sim_effective_decision" in df.columns:
        print("=== Signal Summary (by sim_effective_decision) ===")
        # simple polars groupby for readable counts
        summary = (
            df.select(["symbol", "sim_effective_decision"])
            .with_columns(pl.col("sim_effective_decision").fill_null("UNKNOWN"))
            .group_by(["symbol", "sim_effective_decision"])
            .agg(pl.count().alias("len"))
            .sort(["symbol", "sim_effective_decision"])
        )
        print(summary)
        print("================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute per-symbol simulation stats from a scan_signals Parquet."
    )
    parser.add_argument(
        "--parquet",
        type=str,
        required=True,
        help="Path to scan_signals_*.parquet file.",
    )
    parser.add_argument(
        "--symbol-filter",
        nargs="*",
        default=None,
        help="Optional: limit stats to these symbols.",
    )

    args = parser.parse_args()
    p = Path(args.parquet).expanduser().resolve()

    if not p.exists():
        print(f"[SimStats] Parquet not found: {p}")
        return

    df = _load_scan_df(p)

    # Optional symbol filter
    if args.symbol_filter and "symbol" in df.columns:
        syms = [s.upper() for s in args.symbol_filter]
        df = df.filter(pl.col("symbol").str.to_uppercase().is_in(syms))

    if df.is_empty():
        print("[SimStats] No rows after symbol filter; nothing to summarise.")
        return

    _print_stats(df)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# ============================================================
# queen/cli/scan_signals.py — v1.6
# ------------------------------------------------------------
# Bulk signal scanner + Parquet inspector (with filters)
#
# v1.3:
#   • Optionally enrich rows via strategies.fusion.apply_strategies()
# v1.4:
#   • Interval & time_bucket surfaced for audits.
# v1.5:
#   • Supports both:
#       - historical intraday (with --from/--to)
#       - live intraday (no dates → today-only via fetch_unified)
#     using ReplayConfig(date_from=None, date_to=None).
# v1.6:
#   • Inspect-mode "replay toys":
#       - --phase-filter (time_bucket filter, e.g. LATE_SESSION)
#       - --min-score (score >= threshold)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from queen.cli.replay_actionable import ReplayConfig, replay_actionable
from queen.helpers.logger import log

# ----------------- helpers -----------------

def _drop_empty_struct_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Remove columns whose dtype is a Struct with *no child fields*.

    These typically come from engine-internal blobs that are always `{}` and
    cannot be written to Parquet (Polars raises:
      "Unable to write struct type with no child field to Parquet").
    They contain no information and are safe to drop for scan inspection.
    """
    drop_cols = [
        name
        for name, dtype in zip(df.columns, df.dtypes)
        # Polars Struct dtypes expose `.fields`; empty struct → fields == []
        if getattr(dtype, "fields", None) == []
    ]

    if drop_cols:
        df = df.drop(drop_cols)
        log.info(
            f"[ScanSignals] Dropped empty struct columns before Parquet write → {drop_cols}"
        )
    return df

def _default_out_path(
    date_from: Optional[str],
    date_to: Optional[str],
    interval_min: int,
) -> Path:
    base = Path("queen/data/runtime/dev")
    base.mkdir(parents=True, exist_ok=True)

    if date_from and date_to:
        tag = f"{date_from}_to_{date_to}" if date_from != date_to else date_from
    else:
        tag = "live_intraday"

    fname = f"scan_signals_{tag}_{interval_min}m.parquet"
    return (base / fname).expanduser().resolve()


def _build_rows(
    symbol: str,
    payload: Dict[str, Any],
    *,
    interval_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Flatten replay_actionable rows into a clean JSON-safe dict.

    Removes:
        • empty dict fields ({} causes Polars Struct([]) → Parquet error)
    Keeps:
        • everything else, including nested dicts like targets_state, tv_ctx, regime.
    """
    rows_raw = payload.get("rows") or []
    out: List[Dict[str, Any]] = []

    for r in rows_raw:
        row = dict(r)

        row.setdefault("symbol", symbol.upper())

        ts = row.get("timestamp")
        if ts is not None and not isinstance(ts, str):
            row["timestamp"] = str(ts)

        row.setdefault("decision", None)
        row.setdefault("bias", None)

        if interval_label is not None:
            row.setdefault("interval", interval_label)

        # ❗ CLEAN FIX: remove ONLY empty dicts — no hacks, no logic changes
        row = {k: v for k, v in row.items()
               if not (isinstance(v, dict) and not v)}

        out.append(row)

    return out

def _print_decision_summary(df: pl.DataFrame) -> None:
    if df.is_empty():
        print("No rows in scan (empty DataFrame).")
        return

    if "decision" in df.columns:
        df = df.with_columns(pl.col("decision").cast(pl.Utf8, strict=False))
    if "symbol" in df.columns:
        df = df.with_columns(pl.col("symbol").cast(pl.Utf8, strict=False))

    summary = (
        df.group_by("symbol", "decision")
        .len()
        .sort(["symbol", "decision"])
    )

    print("\n=== Signal Summary (symbol × decision × len) ===")
    print(summary)
    print("===============================================\n")


def _print_playbook_summary(df: pl.DataFrame) -> None:
    """Extra summary: symbol × playbook × action_tag × len."""
    if df.is_empty() or "playbook" not in df.columns:
        return

    f = df.with_columns(
        [
            pl.col("symbol").cast(pl.Utf8, strict=False),
            pl.col("playbook").cast(pl.Utf8, strict=False),
        ]
    )

    has_action_tag = "action_tag" in f.columns
    if has_action_tag:
        f = f.with_columns(pl.col("action_tag").cast(pl.Utf8, strict=False))

    group_keys = ["symbol", "playbook"] + (["action_tag"] if has_action_tag else [])
    summary = (
        f.group_by(group_keys)
        .len()
        .sort(group_keys)
    )

    title_suffix = " × action_tag" if has_action_tag else ""
    print(f"\n=== Playbook Summary (symbol × playbook{title_suffix} × len) ===")
    print(summary)
    print("===============================================\n")


async def _scan_symbols(
    symbols: List[str],
    *,
    date_from: Optional[str],
    date_to: Optional[str],
    interval_min: int,
    book: str,
    warmup: int,
) -> pl.DataFrame:
    all_rows: List[Dict[str, Any]] = []
    interval_label = f"{interval_min}m"

    for sym in symbols:
        cfg = ReplayConfig(
            symbol=sym,
            date_from=date_from,
            date_to=date_to,
            interval_min=interval_min,
            book=book,
            warmup=warmup,
            final_only=False,
            pos_mode="auto",      # 🔥 enable synthetic long-only sim
            auto_side="long",     # (future-proof; v1 uses long-only)
        )

        log.info(
            f"[ScanSignals] Scanning {sym} {date_from}→{date_to} "
            f"@ {interval_min}m (book={book}, warmup={warmup})"
        )

        try:
            payload = await replay_actionable(cfg)
        except Exception as e:
            log.exception(f"[ScanSignals] replay_actionable failed for {sym} → {e}")
            continue

        rows = _build_rows(sym, payload, interval_label=interval_label)
        all_rows.extend(rows)

    if not all_rows:
        return pl.DataFrame()

    df = pl.DataFrame(all_rows)
    if "timestamp" in df.columns:
        df = df.sort(["symbol", "timestamp"])
    else:
        df = df.sort(["symbol"])
    return df


# ----------------- CLI -----------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan signals over a date range and/or inspect a scan parquet."
    )

    # Inspect mode
    parser.add_argument(
        "--inspect",
        type=str,
        default=None,
        help="Path to an existing Parquet file to inspect instead of scanning.",
    )
    parser.add_argument(
        "--symbol-filter",
        nargs="*",
        default=None,
        help="In inspect mode: limit detailed dump to these symbols.",
    )
    parser.add_argument(
        "--decision-filter",
        nargs="*",
        default=None,
        help="In inspect mode: limit detailed dump to these decisions.",
    )
    parser.add_argument(
        "--phase-filter",
        nargs="*",
        default=None,
        help="In inspect mode: limit rows to these time_bucket values (e.g. LATE_SESSION).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="In inspect mode: limit rows to score >= this value.",
    )
    parser.add_argument(
        "--show-rows",
        action="store_true",
        help="In inspect mode: after summary, print filtered detailed rows.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=100,
        help="Cap for detailed rows printed in inspect mode.",
    )

    # Scan arguments
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Symbols (space-separated) for scan mode.",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        required=False,
        help="From date (YYYY-MM-DD) for scan mode (historical intraday).",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        required=False,
        help="To date (YYYY-MM-DD, inclusive) for scan mode (historical intraday).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Intraday interval in minutes (default: 15).",
    )
    parser.add_argument(
        "--book",
        type=str,
        default="all",
        help="Book name for positions (default: all).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=25,
        help=(
            "Minimum bars before emitting rows (default: 25). "
            "For live intraday, use 5–10 to avoid empty scans."
        ),
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional explicit parquet output path for scan mode.",
    )

    args = parser.parse_args()

    # 1) Inspect mode
    if args.inspect:
        p = Path(args.inspect).expanduser().resolve()
        if not p.exists():
            print(f"[ScanSignals] Parquet not found: {p}")
            return
        print(f"[ScanSignals] Inspecting existing parquet → {p}")
        df = pl.read_parquet(p)

        # Summaries are always on full DF (unfiltered), so you see the whole picture
        _print_decision_summary(df)
        _print_playbook_summary(df)

        if args.show_rows:
            f = df

            # Symbol filter
            if args.symbol_filter:
                syms = [s.upper() for s in args.symbol_filter]
                f = f.filter(pl.col("symbol").str.to_uppercase().is_in(syms))

            # Decision filter
            if args.decision_filter and "decision" in f.columns:
                decs = [d.upper() for d in args.decision_filter]
                f = f.with_columns(
                    pl.col("decision").cast(pl.Utf8, strict=False)
                )
                f = f.filter(pl.col("decision").str.to_uppercase().is_in(decs))

            # Phase / time_bucket filter
            if args.phase_filter and "time_bucket" in f.columns:
                phases = [ph.upper() for ph in args.phase_filter]
                f = f.with_columns(
                    pl.col("time_bucket").cast(pl.Utf8, strict=False)
                )
                f = f.filter(pl.col("time_bucket").str.to_uppercase().is_in(phases))

            # Min-score filter
            if args.min_score is not None and "score" in f.columns:
                f = f.filter(pl.col("score") >= args.min_score)

            # Sort + project wanted columns
            if "timestamp" in f.columns:
                f = f.sort(["symbol", "timestamp"])
            else:
                f = f.sort(["symbol"])

            wanted = [
                    "timestamp",
                    "symbol",
                    "interval",
                    "time_bucket",
                    "decision",
                    "bias",
                    "trade_status",
                    "score",
                    "cmp",
                    "trend_bias",
                    "trend_score",
                    "vwap_zone",
                    "cpr_ctx",
                    "tv_override",
                    "tv_reason",
                    "playbook",
                    "action_tag",
                    "action_reason",
                    "risk_mode",
                    "notes",
                    "drivers",

                    # 🔥 Auto-position v1 (synthetic long-only sim)
                    "sim_side",
                    "sim_qty",
                    "sim_avg",
                    "sim_pnl",
                    "sim_pnl_pct",
                    "sim_realized_pnl",
                    "sim_total_pnl",
                ]
            cols = [c for c in wanted if c in f.columns]
            f = f.select(cols).head(args.max_rows)

            print("\n=== Detailed rows (filtered) ===")
            print(f)
            print("================================\n")

        return

    # 2) Scan mode
    if not args.symbols and not args.inspect:
        parser.error(
            "Scan mode requires: --symbols ... (or use --inspect <parquet> to only read)."
        )

    symbols: List[str] = [s.upper() for s in (args.symbols or [])]
    date_from: Optional[str] = args.date_from
    date_to: Optional[str] = args.date_to
    interval_min: int = int(args.interval)
    book: str = args.book
    warmup: int = int(args.warmup)

    async def _run():
        df = await _scan_symbols(
            symbols,
            date_from=date_from,
            date_to=date_to,
            interval_min=interval_min,
            book=book,
            warmup=warmup,
        )

        if df.is_empty():
            print("[ScanSignals] No rows produced (empty DF); nothing to write.")
            return

        # 🔍 Clean up engine-internal empty struct blobs before Parquet
        df = _drop_empty_struct_columns(df)

        out_path = (
            Path(args.out).expanduser().resolve()
            if args.out
            else _default_out_path(date_from, date_to, interval_min)
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out_path)
        log.info(f"[ScanSignals] Wrote {df.height} rows → {out_path}")

        # Print summaries on freshly scanned DF too
        _print_decision_summary(df)
        _print_playbook_summary(df)

    asyncio.run(_run())


if __name__ == "__main__":
    main()

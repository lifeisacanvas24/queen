#!/usr/bin/env python3
# ============================================================
# queen/cli/replay_actionable.py — v3.3
# ------------------------------------------------------------
# Historical intraday actionable replay (dev analysis tool)
#
# Principles:
#   • EXACT same pipeline as live:
#         DF → build_actionable_row → strategies → output
#   • Replay is only a *lens*, not a different engine.
#   • Supports synthetic position simulation via build_actionable_row
#     with:
#         pos_mode = "flat" | "live" | "auto"
#         auto_side = "long" | "short" | "both"
#
# Semantics (as agreed):
#   • AVOID = entry filter, NEVER exits an existing position
#   • HOLD  = maintain current position (no open/close/add)
#   • Long side:
#         BUY       → open / add long
#         ADD       → add to long
#         EXIT      → close long
#   • Short side:
#         SELL      → open / add short
#         ADD_SHORT → add to short
#         EXIT_SHORT→ close short
#   • EOD:
#         In intraday auto-mode, last bar can force EXIT/EXIT_SHORT
#         via eod_force=True passed into build_actionable_row.
#
# Notes:
#   • There is NO legacy internal simulator here anymore.
#     All sim logic (trade_id, trail, skipped_adds, explicit
#     short/long semantics, etc.) lives in queen/services/actionable_row.py.
# ============================================================

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import polars as pl

from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers.candles import ensure_sorted
from queen.helpers.logger import log
from queen.services.actionable_row import build_actionable_row


# ------------------------------------------------------------
# ReplayConfig — fully forward compatible
# ------------------------------------------------------------
@dataclass
class ReplayConfig:
    symbol: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    interval_min: int = 15
    book: str = "all"

    # Bars
    warmup: int = 25
    final_only: bool = False

    # Position mode
    #   "flat" → no sim, just decisions
    #   "live" → use positions_map as starting state (portfolio-aware)
    #   "auto" → synthetic sim (long / short / both) for intraday what-if
    pos_mode: str = "flat"         # "flat" | "live" | "auto"

    # Auto-sim bias:
    #   "long"  → only long-side decisions (BUY/ADD/EXIT)
    #   "short" → only short-side decisions (SELL/ADD_SHORT/EXIT_SHORT)
    #   "both"  → both vocabularies allowed (engine chooses)
    auto_side: str = "both"        # "long" | "short" | "both"

    # Position map — only used if pos_mode == "live"
    positions_map: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------
# JSON-safe row helper
# ------------------------------------------------------------
def _json_safe_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            continue
        if isinstance(v, (list, dict, float, int, str, bool)):
            out[k] = v
        else:
            # Best-effort JSONable coercion; fail silently per-field.
            try:
                out[k] = json.loads(json.dumps(v))
            except Exception:
                pass
    return out


# ------------------------------------------------------------
# Historical intraday fetcher (unified)
# ------------------------------------------------------------
async def _fetch_intraday_range(cfg: ReplayConfig) -> pl.DataFrame:
    """Fetch intraday candles using the same unified fetcher as live.

    Returns:
        Polars DataFrame with at least:
            - timestamp
            - open, high, low, close, volume
            - (any other engine-required fields)

    """
    iv = f"{cfg.interval_min}m"

    # Historical mode
    if cfg.date_from and cfg.date_to:
        df = await fetch_unified(
            cfg.symbol,
            mode="intraday",
            from_date=cfg.date_from,
            to_date=cfg.date_to,
            interval=iv,
            start=cfg.date_from,
            end=cfg.date_to,
        )
        return ensure_sorted(df) if not df.is_empty() else df

    # Live intraday (default: today-only)
    df = await fetch_unified(
        cfg.symbol,
        mode="intraday",
        interval=iv,
        from_date=None,
        to_date=None,
    )
    return ensure_sorted(df) if not df.is_empty() else df


# ------------------------------------------------------------
# Main replay function — unified pipeline
# ------------------------------------------------------------
async def replay_actionable(cfg: ReplayConfig) -> Dict[str, Any]:
    """Replay intraday candles through the exact same pipeline as live.

    DF → build_actionable_row → (strategies, sim) → actionable rows
    """
    df = await _fetch_intraday_range(cfg)
    if df.is_empty():
        log.info(
            f"[ReplayActionable] No data for {cfg.symbol} "
            f"{cfg.date_from}→{cfg.date_to} @ {cfg.interval_min}m"
        )
        return {
            "symbol": cfg.symbol,
            "interval": f"{cfg.interval_min}m",
            "from": cfg.date_from,
            "to": cfg.date_to,
            "book": cfg.book,
            "count": 0,
            "rows": [],
        }

    rows: List[Dict[str, Any]] = []
    interval_str = f"{cfg.interval_min}m"
    n = df.height

    # Warmup logic: ensure at least some bars to seed indicators
    effective_warmup = cfg.warmup
    if effective_warmup >= n:
        effective_warmup = max(1, n)

    # Simulator state is carried across slices so that
    # build_actionable_row can maintain:
    #   • trade_id
    #   • trailing stops
    #   • pyramid (ADD/ADD_SHORT) history
    #   • FLAT/LONG/SHORT sim-side and PnL
    sim_state: Dict[str, Any] | None = None

    for i in range(n):
        # Skip until warmup bars are available
        if i + 1 < effective_warmup:
            continue

        df_slice = df.slice(0, i + 1)

        # Intraday-only philosophy: in pos_mode="auto" we treat the last
        # bar as "EOD", and ask build_actionable_row to flatten if any
        # synthetic position is still open.
        eod_force = bool(cfg.pos_mode == "auto" and i == n - 1)

        # Let build_actionable_row handle:
        #   • decision (BUY/ADD/EXIT/SELL/ADD_SHORT/EXIT_SHORT/HOLD/AVOID)
        #   • sim semantics (long vs short)
        #   • PnL state (sim_side, sim_qty, sim_avg, sim_pnl, ...)
        row, sim_state = build_actionable_row(
            symbol=cfg.symbol,
            df=df_slice,
            interval=interval_str,
            book=cfg.book,
            pos_mode=cfg.pos_mode,
            auto_side=cfg.auto_side,
            positions_map=cfg.positions_map,
            cmp_anchor=None,
            sim_state=sim_state,
            eod_force=eod_force,
        )

        # Ensure timestamp is present
        try:
            ts_val = df_slice["timestamp"].tail(1).item()
            if ts_val is not None:
                row.setdefault("timestamp", ts_val)
        except Exception:
            # If timestamp is missing, we still return data; callers like
            # scan_signals / sim_stats will fail loudly if they require it.
            pass

        rows.append(_json_safe_row(row))

    if cfg.final_only and rows:
        rows = [rows[-1]]

    return {
        "symbol": cfg.symbol,
        "interval": interval_str,
        "from": cfg.date_from,
        "to": cfg.date_to,
        "book": cfg.book,
        "count": len(rows),
        "rows": rows,
    }


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Historical Intraday actionable replay (same pipeline as live)."
    )

    parser.add_argument("--symbol", required=True)
    parser.add_argument("--from", dest="date_from")
    parser.add_argument("--to", dest="date_to")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--book", type=str, default="all")
    parser.add_argument("--warmup", type=int, default=25)
    parser.add_argument("--final-only", action="store_true")

    # Position modes
    parser.add_argument(
        "--pos-mode",
        type=str,
        choices=["flat", "live", "auto"],
        default="flat",
    )
    parser.add_argument(
        "--auto-side",
        type=str,
        choices=["long", "short", "both"],
        default="both",
        help='Auto-sim side bias: "long", "short", or "both".',
    )

    args = parser.parse_args()

    cfg = ReplayConfig(
        symbol=args.symbol,
        date_from=args.date_from,
        date_to=args.date_to,
        interval_min=args.interval,
        book=args.book,
        warmup=args.warmup,
        final_only=args.final_only,
        pos_mode=args.pos_mode,
        auto_side=args.auto_side,
    )

    async def _run() -> None:
        payload = await replay_actionable(cfg)
        print(json.dumps(payload, ensure_ascii=False))

    asyncio.run(_run())


if __name__ == "__main__":
    main()

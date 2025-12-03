#!/usr/bin/env python3
# ============================================================
# queen/cli/replay_actionable.py — v3.1 (Forward-Compatible)
# ------------------------------------------------------------
# Historical intraday actionable replay (dev analysis tool)
#
# Principles:
#   • EXACTLY same pipeline as live:
#         DF → build_actionable_row → strategies → output
#   • Replay is only a *lens*, not a different engine.
#   • Supports synthetic position simulation (pos_mode="auto")
#   • Supports pos_mode="flat" | "live" | "auto"
#
# v3.1:
#   • Adds external long-only auto-position sim (Option A + EXIT):
#       - ENTRY: flat + BUY → open 1x LONG at cmp
#       - EXIT:  LONG + (EXIT/AVOID or exit-like trade_status) → book PnL & flatten
#       - No ADD / scaling yet (kept intentionally simple for audit-first behaviour)
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
    pos_mode: str = "flat"         # "flat" | "live" | "auto"
    auto_side: str = "long"        # "long" | "both"

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
            try:
                out[k] = json.loads(json.dumps(v))
            except Exception:
                # skip non-serializable junk
                pass
    return out


# ------------------------------------------------------------
# Auto-position simulation (Option A + EXIT)
# ------------------------------------------------------------
def _apply_auto_position_sim(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Long-only, audit-first auto-position simulation (Option A + EXIT).

    Rules:
      • ENTRY:
          - If we are flat and decision == "BUY" and cmp exists
          - → Open 1x LONG at cmp.
      • NO ADD / SCALE (v1):
          - We do not increase size on ADD yet. One clean unit only.
      • EXIT:
          - If we are LONG and:
                decision in {"EXIT", "AVOID"} OR
                trade_status in {"EXIT", "FORCE_EXIT", "STOPPED_OUT"}
            → Book PnL into sim_realized_pnl and flatten.
      • PNL:
          - sim_pnl, sim_pnl_pct: unrealised PnL on the *current open* position.
          - sim_realized_pnl: cumulative closed PnL.
          - sim_total_pnl = sim_realized_pnl + (sim_pnl or 0).

    Assumptions:
      • rows are sorted by time ascending for a single (symbol, interval).
      • each row has at least: cmp, decision (and optionally trade_status).
    """
    side: str | None = None   # None or "LONG"
    qty: float = 0.0
    avg: float | None = None
    realized: float = 0.0

    for row in rows:
        cmp_val = row.get("cmp")
        decision = (row.get("decision") or "").upper()
        trade_status = (row.get("trade_status") or "").upper()

        # -----------------------------
        # 1) ENTRY: flat → BUY
        # -----------------------------
        if side is None and decision == "BUY" and cmp_val is not None:
            try:
                px = float(cmp_val)
            except Exception:
                px = None

            if px is not None:
                side = "LONG"
                qty = 1.0
                avg = px

        # -----------------------------
        # 2) EXIT: LONG → flat
        # -----------------------------
        exit_signal = decision in {"EXIT", "AVOID"} or trade_status in {
            "EXIT",
            "FORCE_EXIT",
            "STOPPED_OUT",
        }

        if side == "LONG" and exit_signal and cmp_val is not None and avg is not None:
            try:
                px = float(cmp_val)
            except Exception:
                px = None

            if px is not None:
                unreal = (px - avg) * qty
                realized += unreal

            # flatten position
            side = None
            qty = 0.0
            avg = None

        # -----------------------------
        # 3) Unrealised PnL if in position
        # -----------------------------
        sim_pnl: float | None = None
        sim_pnl_pct: float | None = None

        if side == "LONG" and cmp_val is not None and avg is not None:
            try:
                px = float(cmp_val)
            except Exception:
                px = None

            if px is not None:
                sim_pnl = (px - avg) * qty
                try:
                    sim_pnl_pct = (px - avg) / avg * 100.0
                except Exception:
                    sim_pnl_pct = None

        sim_total = realized + (sim_pnl or 0.0)

        # -----------------------------
        # 4) Surface into row
        # -----------------------------
        row["sim_side"] = side
        row["sim_qty"] = qty if side is not None else 0.0
        row["sim_avg"] = avg
        row["sim_pnl"] = sim_pnl
        row["sim_pnl_pct"] = sim_pnl_pct
        row["sim_realized_pnl"] = realized
        row["sim_total_pnl"] = sim_total

    return rows


# ------------------------------------------------------------
# Historical intraday fetcher (unified)
# ------------------------------------------------------------
async def _fetch_intraday_range(cfg: ReplayConfig) -> pl.DataFrame:
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

    # Live intraday (default)
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
    df = await _fetch_intraday_range(cfg)
    if df.is_empty():
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

    effective_warmup = cfg.warmup
    if effective_warmup >= n:
        effective_warmup = max(1, n)

    sim_state: Dict[str, Any] | None = None

    for i in range(n):
        # skip until warmup bars are available
        if i + 1 < effective_warmup:
            continue

        df_slice = df.slice(0, i + 1)

        # intraday-only philosophy: force exit on LAST bar in auto-mode
        eod_force = bool(cfg.pos_mode == "auto" and i == n - 1)

        try:
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
        except Exception as e:
            log.exception(f"[Replay] {cfg.symbol} slice {i} failed → {e}")
            continue

        # Ensure timestamp is present
        try:
            ts_val = df_slice["timestamp"].tail(1).item()
            if ts_val is not None:
                row.setdefault("timestamp", ts_val)
        except Exception:
            pass

        rows.append(_json_safe_row(row))

    # ❌ REMOVE: external _apply_auto_position_sim — Option A already ran inline
    # if cfg.pos_mode == "auto" and rows:
    #     rows = _apply_auto_position_sim(rows)

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
        description="Historical Intraday actionable replay (forward-compatible)."
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
        choices=["long", "both"],
        default="long",
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

    async def _run():
        payload = await replay_actionable(cfg)
        print(json.dumps(payload, ensure_ascii=False))

    asyncio.run(_run())


if __name__ == "__main__":
    main()

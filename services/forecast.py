#!/usr/bin/env python3
# ============================================================
# queen/services/forecast.py — v0.9 (next-session tactical plan)
# ============================================================
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List


from queen.helpers.logger import log
from queen.settings.settings import PATHS
from queen.helpers.market import MARKET_TZ, next_working_day
from queen.daemons.live_engine import MonitorConfig, _one_pass  # reuse indicator math
from queen.helpers.portfolio import position_for, compute_pnl

RUNTIME_DIR: Path = PATHS["RUNTIME"]
ARCHIVE_DIR: Path = PATHS.get("ARCHIVE", RUNTIME_DIR.parent / "archive")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

PLAN_FILE = RUNTIME_DIR / "next_session_plan.json"


@dataclass
class ForecastOptions:
    interval_min: int = 15  # reuse same bar size used by live engine
    view: str = "compact"


def _infer_next_session_date(now_ist: datetime) -> date:
    return next_working_day(now_ist.date())

def _advice_for(symbol: str, cmp_price: float, score: float, row: Dict, book: str = "all") -> Dict:
    """
    Produce simple, transparent advice using holdings + score.
    Returns dict with {position, pnl_abs, pnl_pct, advice}.
    """
    pos = position_for(symbol, book=book)
    pnl_abs = pnl_pct = None
    if pos:
        res = compute_pnl(cmp_price, pos)
        if res:
            pnl_abs, pnl_pct = res

    # Defaults
    advice = "Avoid fresh entry"

    # If no position
    if not pos:
        if score >= 7:
            advice = f"Consider BUY on strength (above VWAP/CPR) | SL {row.get('sl')}"
        elif score >= 5:
            advice = "Watch for momentum confirmation (reclaim VWAP/EMA50)"
        else:
            advice = "Avoid fresh entry"

    # If holding
    else:
        # strong gain but momentum cooling
        if (pnl_pct is not None and pnl_pct >= 10) and score < 5:
            advice = "BOOK partial profits (25–50%); trail SL to CPR/VWAP"
        # small gain + strong score → add
        elif (pnl_pct is not None and pnl_pct >= 0) and score >= 7:
            advice = "ADD on pullbacks to VWAP/EMA20 with tight SL"
        # underwater + weak momentum
        elif (pnl_pct is not None and pnl_pct <= -5) and score <= 3:
            advice = "REDUCE risk or exit on VWAP failure; reassess"
        else:
            advice = "HOLD; trail SL under CPR/EMA20"

    return {
        "position": pos,
        "pnl_abs": round(pnl_abs, 2) if pnl_abs is not None else None,
        "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "advice": advice,
    }

def _row_to_plan(row: Dict) -> Dict:
    cmp_ = float(row.get("cmp") or 0.0)
    rsi = row.get("rsi")
    vwap = row.get("vwap")
    atr = row.get("atr")
    obv = (row.get("obv") or "Flat").title()
    summary = row.get("summary") or "Neutral"

    score = 0
    if rsi is not None:
        score += 2 if rsi >= 60 else (1 if rsi >= 55 else 0)
    if vwap is not None and cmp_ > vwap:
        score += 2
    if "Above VWAP/CPR" in summary:
        score += 3
    if obv == "Rising":
        score += 2
    if atr:
        score += 1
    score = min(score, 10)

    setup = ("📈 Bullish breakout forming" if score >= 8
                 else "⚖️ Consolidation / Momentum setup" if score >= 5
                 else "🔻 Weak momentum / Pullback")

    # ✅ always compute advice_pack
    advice_pack = _advice_for(row["symbol"], cmp_, score, row, book="all")  # <-- always
    return {
        "symbol": row["symbol"],
        "cmp": cmp_,
        "rsi": round(rsi, 1) if rsi is not None else None,
        "vwap": vwap,
        "atr": atr,
        "obv": obv,
        "summary": summary,
        "targets": row.get("targets", []),
        "sl": row.get("sl"),
        "score": score,
        "setup": setup,
        "bias": "Long" if score >= 6 else ("Neutral" if score >= 4 else "Weak"),
        "position": advice_pack["position"],
        "pnl_abs": advice_pack["pnl_abs"],
        "pnl_pct": advice_pack["pnl_pct"],
        "advice": advice_pack["advice"],
    }

async def build_next_session_plan(symbols: List[str], opt: ForecastOptions | None = None) -> Dict:
    """Run one indicator pass and synthesize a next-session plan JSON."""
    opt = opt or ForecastOptions()
    cfg = MonitorConfig(symbols=symbols, interval_min=opt.interval_min, view=opt.view)

    rows = await _one_pass(cfg)  # DRY: uses your technicals/core
    plan_rows = [_row_to_plan(r) for r in rows]

    now_ist = datetime.now(MARKET_TZ)
    next_sess = _infer_next_session_date(now_ist)

    payload = {
        "generated_at": now_ist.isoformat(),
        "next_session": next_sess.isoformat(),
        "symbols": symbols,
        "rows": plan_rows,
        "summary": {
            "count": len(plan_rows),
            "avg_score": round(sum(r["score"] for r in plan_rows) / max(1, len(plan_rows)), 2)
            if plan_rows else 0.0,
            "bias": (
                "Positive" if plan_rows and (sum(1 for r in plan_rows if r["score"] >= 6) > len(plan_rows) / 2)
                else "Balanced" if plan_rows else "N/A"
            ),
        },
    }

    # write runtime file
    PLAN_FILE.write_text(json.dumps(payload, indent=2))
    log.info(f"[forecast] wrote {PLAN_FILE}")

    # archive snapshot tagged to next session
    archive_file = ARCHIVE_DIR / f"forecast_{next_sess.strftime('%Y%m%d')}.json"
    archive_file.write_text(json.dumps(plan_rows, indent=2))
    log.info(f"[forecast] archived rows → {archive_file.name}")

    return payload


# -------- Optional manual runner (handy for quick checks) --------
if __name__ == "__main__":
    import asyncio
    import sys
    syms = sys.argv[1:] or ["NETWEB", "GODFRYPHLP", "FORCEMOT"]
    asyncio.run(build_next_session_plan(syms))

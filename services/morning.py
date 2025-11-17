#!/usr/bin/env python3
# ============================================================
# queen/services/morning.py — v1.0 (pre-market briefing, DRY + io.py)
# ============================================================
from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple

from queen.helpers.io import read_json, write_json
from queen.helpers.logger import log
from queen.helpers.market import MARKET_TZ, last_working_day
from queen.settings.settings import PATHS

RUNTIME_DIR: Path = PATHS["RUNTIME"]
ARCHIVE_DIR: Path = PATHS["ARCHIVES"]
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

HIGH_SIG = RUNTIME_DIR / "high_signals.json"
MORNING_FLAG = RUNTIME_DIR / "morning_done.txt"


def _archive_yesterday_signals(now_ist: datetime) -> Tuple[int, Path | None]:
    """Archive runtime/high_signals.json → archives/high_signals_YYYY-MM-DD.json (yesterday’s trading day)."""
    if not HIGH_SIG.exists():
        return 0, None

    y_td = last_working_day(now_ist.date() - timedelta(days=1))
    dest = ARCHIVE_DIR / f"high_signals_{y_td}.json"

    try:
        dest.write_text(HIGH_SIG.read_text())
        write_json(HIGH_SIG, [])  # clear for the new session
        log.info(f"[morning] archived high_signals → {dest.name}")
        return 1, dest
    except Exception as e:
        log.warning(f"[morning] archive failed: {e}")
        return 0, None


def _trend_last_n(n: int = 5) -> List[Tuple[str, float]]:
    files = sorted(ARCHIVE_DIR.glob("high_signals_*.json"))[-n:]
    out: List[Tuple[str, float]] = []
    for f in files:
        rows = read_json(f, default=[])
        scores = [s.get("score") for s in rows if isinstance(s.get("score"), (int, float))]
        if scores:
            out.append((f.stem.replace("high_signals_", ""), round(mean(scores), 2)))
    return out


def _weekly_gauge(n: int = 7) -> float:
    files = sorted(ARCHIVE_DIR.glob("high_signals_*.json"))[-n:]
    bag: List[float] = []
    for f in files:
        rows = read_json(f, default=[])
        scores = [s.get("score") for s in rows if isinstance(s.get("score"), (int, float))]
        if scores:
            bag.append(mean(scores))
    return round(mean(bag), 1) if bag else 0.0


def run_morning_briefing() -> Dict:
    """DRY pre-market routine:
    - archives yesterday’s high_signals
    - returns summary, last-N trend, weekly gauge
    - one-per-day guard (MORNING_FLAG)
    """
    now_ist = datetime.now(MARKET_TZ)
    today = now_ist.date()

    # one-per-day
    if MORNING_FLAG.exists() and MORNING_FLAG.read_text().strip() == str(today):
        log.info("[morning] already completed today")
        # still return current snapshot for UI widgets
        return build_briefing_payload(now_ist)

    # only do archive/reset in 09:00–09:15 window
    if time(9, 0) <= now_ist.time() < time(9, 15):
        _archive_yesterday_signals(now_ist)

    payload = build_briefing_payload(now_ist)
    MORNING_FLAG.write_text(str(today))
    log.info("[morning] briefing complete")
    return payload


def build_briefing_payload(now_ist: datetime) -> Dict:
    today_signals = read_json(HIGH_SIG, default=[])
    top5 = sorted(today_signals, key=lambda x: x.get("score", 0), reverse=True)[:5]
    trend5 = _trend_last_n(5)
    weekly = _weekly_gauge(7)

    return {
        "generated_at": now_ist.isoformat(),
        "today_top": top5,
        "trend_5": trend5,          # list of (YYYY-MM-DD, avg_score)
        "weekly_strength": weekly,  # 0..10
        "status": "ok",
    }


# -------- Optional manual runner --------
if __name__ == "__main__":
    out = run_morning_briefing()
    print(json.dumps(out, indent=2))

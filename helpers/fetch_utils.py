#!/usr/bin/env python3
# ============================================================
# queen/helpers/fetch_utils.py — v1.0 (Shared Fetch DX helpers)
# ============================================================
from __future__ import annotations

from datetime import date, datetime

from queen.helpers.logger import log
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

'''def warn_if_same_day_eod(from_date: str | None, to_date: str | None) -> None:
    """Emit a helpful warning if the request includes today's EOD."""
    if not from_date or not to_date:
        return
    try:
        today_ist = datetime.now(tz=IST).date()
        f = date.fromisoformat(from_date)
        t = date.fromisoformat(to_date)
        if t >= today_ist:
            log.warning(
                "[EOD] You requested today's daily candle but EOD may not be published yet. "
                "Use --mode intraday for live data, or re-run after market close."
            )
    except Exception:
        # Best-effort warning: never fail the caller
        return
'''

def warn_if_same_day_eod(from_date: str | date | None, to_date: str | date | None) -> None:
    if not from_date or not to_date:
        return
    try:
        today_ist = datetime.now(tz=IST).date()
        f = from_date if isinstance(from_date, date) else date.fromisoformat(str(from_date))
        t = to_date if isinstance(to_date, date) else date.fromisoformat(str(to_date))
        if t >= today_ist:
            log.warning(
                "[EOD] You requested today's daily candle but EOD may not be published yet. "
                "Use --mode intraday for live data, or re-run after market close."
            )
    except Exception:
        return

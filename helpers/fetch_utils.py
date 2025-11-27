#!/usr/bin/env python3
# ============================================================
# queen/helpers/fetch_utils.py — v1.0 (Shared Fetch DX helpers)
# ============================================================
from __future__ import annotations

from datetime import date, datetime

from queen.helpers.logger import log
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def ensure_datetime(value: datetime | None, *, tz: ZoneInfo | None = None) -> datetime | None:
    """
    Strict normalizer for datetime inputs.

    - Accepts only `datetime` or `None`.
    - Returns a timezone-aware datetime in the given tz (default: IST).
    - Raises TypeError for any other type (str, date, etc.).

    This is meant for NEW code paths so we keep them type-clean from day one.
    """
    if value is None:
        return None

    if not isinstance(value, datetime):
        raise TypeError(
            f"ensure_datetime expects a datetime or None, got {type(value)!r} with value={value!r}"
        )

    tz = tz or IST
    return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)


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

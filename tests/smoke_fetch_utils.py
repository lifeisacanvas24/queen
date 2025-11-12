#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_fetch_utils.py — v1.0
# ============================================================
from __future__ import annotations

from datetime import date

from queen.helpers.fetch_utils import warn_if_same_day_eod


def main():
    # Should be no-op on missing args
    warn_if_same_day_eod(None, None)

    # Should not throw on valid past range
    warn_if_same_day_eod("2024-01-01", "2024-01-02")

    # Should warn (but never throw) when to_date is today
    today = date.today().isoformat()
    warn_if_same_day_eod("2024-01-01", today)

    print("✅ smoke_fetch_utils: passed")

if __name__ == "__main__":
    main()
